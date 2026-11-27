import uuid
import argparse
import hashlib
import json
import math
import time
from datetime import datetime, timezone, timedelta

from google import genai
from google.genai import types
from google.cloud import bigquery

PROJECT_ID = "lulu260902"
DATASET_ID = "ott_optimizer"
MODEL_NAME = "gemini-embedding-001"
DIMENSION = 768
TASK_TYPE = "SEMANTIC_SIMILARITY"

SOURCE_TABLE = f"{PROJECT_ID}.{DATASET_ID}.content_analysis"
TARGET_TABLE = f"{PROJECT_ID}.{DATASET_ID}.content_embeddings"

FETCH_BATCH_SIZE = 500
SAVE_BATCH_SIZE = 100


def build_embedding_text(row):
    """콘텐츠 정보를 임베딩 입력 텍스트로 변환."""
    parts = [
        f"Title: {row.title or ''}",
        f"Media type: {row.media_type}",
        f"Genres: {', '.join(sorted(row.genres or []))}",
        f"Keywords: {', '.join(sorted(row.keywords or []))}",
    ]

    if row.overview and row.overview.strip():
        parts.append(f"Overview: {row.overview.strip()}")

    return "\n".join(parts)


def make_source_hash(text):
    """텍스트 및 임베딩 설정이 같은지 확인하는 해시."""
    payload = json.dumps(
        {
            "text": text,
            "model": MODEL_NAME,
            "dimension": DIMENSION,
            "task_type": TASK_TYPE,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()



def fetch_pending_contents(
    bq_client,
    limit,
    last_media_type=None,
    last_tmdb_id=None,
):
    """마지막 콘텐츠 식별자를 기준으로 다음 콘텐츠 조회."""

    query = f"""
    SELECT
      c.tmdb_id,
      c.media_type,
      c.title,
      c.genres,
      c.keywords,
      c.overview
    FROM `{SOURCE_TABLE}` AS c
    WHERE (
      @last_media_type IS NULL
      OR c.media_type > @last_media_type
      OR (
        c.media_type = @last_media_type
        AND c.tmdb_id > @last_tmdb_id
      )
    )
    ORDER BY c.media_type, c.tmdb_id
    LIMIT @limit
    """

    config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "limit", "INT64", limit
            ),
            bigquery.ScalarQueryParameter(
                "last_media_type", "STRING", last_media_type
            ),
            bigquery.ScalarQueryParameter(
                "last_tmdb_id", "INT64", last_tmdb_id
            ),
        ]
    )

    return list(
        bq_client.query(
            query,
            job_config=config
        ).result()
    )


def fetch_existing_hashes(bq_client, rows):
    """선택한 콘텐츠의 기존 임베딩 메타데이터 조회."""
    if not rows:
        return {}

    keys = [
        f"{row.tmdb_id}:{row.media_type}"
        for row in rows
    ]

    query = f"""
    SELECT
        tmdb_id,
        media_type,
        source_hash,
        model_name,
        embedding_dimension
    FROM `{TARGET_TABLE}`
    WHERE CONCAT(
        CAST(tmdb_id AS STRING),
        ':',
        media_type
    ) IN UNNEST(@keys)
    """

    config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter(
                "keys",
                "STRING",
                keys,
            )
        ]
    )

    existing = bq_client.query(
        query,
        job_config=config
    ).result()

    return {
        (row.tmdb_id, row.media_type): row
        for row in existing
    }

    
def create_embedding(ai_client, text):
    """Vertex AI 임베딩 생성. 일시적 오류는 재시도."""
    for attempt in range(3):
        try:
            response = ai_client.models.embed_content(
                model=MODEL_NAME,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type=TASK_TYPE,
                    output_dimensionality=DIMENSION,
                    auto_truncate=True,
                ),
            )

            vector = response.embeddings[0].values

            if len(vector) != DIMENSION:
                raise ValueError(
                    f"임베딩 차원 오류: {len(vector)}"
                )

            if not all(math.isfinite(x) for x in vector):
                raise ValueError("임베딩에 유효하지 않은 숫자 포함")

            return vector

        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def save_embeddings_batch(bq_client, records):
    """임베딩을 스테이징 테이블에 적재한 후 일괄 MERGE."""

    if not records:
        return

    # 1. 고유한 스테이징 테이블 이름 생성
    staging_table = (
        f"{PROJECT_ID}.{DATASET_ID}."
        f"_embedding_staging_{uuid.uuid4().hex}"
    )

    # 2. 스테이징 테이블 스키마 정의
    schema = [
        bigquery.SchemaField(
            "tmdb_id", "INT64", mode="REQUIRED"
        ),
        bigquery.SchemaField(
            "media_type", "STRING", mode="REQUIRED"
        ),
        bigquery.SchemaField(
            "embedding", "FLOAT64", mode="REPEATED"
        ),
        bigquery.SchemaField("model_name", "STRING"),
        bigquery.SchemaField("embedding_dimension", "INT64"),
        bigquery.SchemaField("source_hash", "STRING"),
        bigquery.SchemaField("embedded_at", "TIMESTAMP"),
    ]

    table = bigquery.Table(staging_table, schema=schema)

    # 비정상 종료에 대비한 자동 만료 설정
    table.expires = (
        datetime.now(timezone.utc) + timedelta(hours=24)
    )

    try:
        # 3. 스테이징 테이블 생성
        bq_client.create_table(table)

        json_records = [
            {
                **record,
                "embedded_at": record["embedded_at"].isoformat(),
            }
            for record in records
        ]

        load_config = bigquery.LoadJobConfig(
            schema=schema,
            write_disposition=(
                bigquery.WriteDisposition.WRITE_TRUNCATE
            ),
        )

        # 4. 임베딩 일괄 적재
        load_job = bq_client.load_table_from_json(
            json_records,
            staging_table,
            job_config=load_config,
            location="asia-northeast3",
        )

        load_job.result()

        # 5. 최종 테이블에 일괄 MERGE
        query = f"""
        MERGE `{TARGET_TABLE}` AS T
        USING `{staging_table}` AS S

        ON T.tmdb_id = S.tmdb_id
           AND T.media_type = S.media_type

        WHEN MATCHED THEN UPDATE SET
          embedding = S.embedding,
          model_name = S.model_name,
          embedding_dimension = S.embedding_dimension,
          source_hash = S.source_hash,
          embedded_at = S.embedded_at

        WHEN NOT MATCHED THEN INSERT (
          tmdb_id,
          media_type,
          embedding,
          model_name,
          embedding_dimension,
          source_hash,
          embedded_at
        )
        VALUES (
          S.tmdb_id,
          S.media_type,
          S.embedding,
          S.model_name,
          S.embedding_dimension,
          S.source_hash,
          S.embedded_at
        )
        """

        bq_client.query(
            query,
            location="asia-northeast3",
        ).result()

        print(f"[BATCH SAVED] {len(records)}개 저장 완료")

    finally:
        # 6. 스테이징 테이블 삭제
        bq_client.delete_table(
            staging_table,
            not_found_ok=True,
        )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="최대 조회 콘텐츠 수",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=SAVE_BATCH_SIZE,
        help="임베딩 저장 배치 크기",
    )

    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit은 1 이상이어야 합니다.")

    if args.batch_size < 1:
        parser.error("--batch-size는 1 이상이어야 합니다.")

    bq_client = bigquery.Client(project=PROJECT_ID)

    ai_client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location="us-central1",
    )

    start_time = time.monotonic()

    processed = 0
    created = 0
    skipped = 0

    last_media_type = None
    last_tmdb_id = None

    records = []

    print(f"최대 조회 콘텐츠: {args.limit:,}개")
    print(f"조회 배치 크기: {FETCH_BATCH_SIZE}개")
    print(f"저장 배치 크기: {args.batch_size}개")

    def flush_batch():
        nonlocal created

        if records:
            save_embeddings_batch(bq_client, records)
            created += len(records)
            records.clear()

    try:
        while processed < args.limit:

            remaining = args.limit - processed

            fetch_size = min(
                FETCH_BATCH_SIZE,
                remaining,
            )

            contents = fetch_pending_contents(
                bq_client,
                fetch_size,
                last_media_type,
                last_tmdb_id,
            )

            if not contents:
                break

            existing = fetch_existing_hashes(
                bq_client,
                contents,
            )

            print(f"\n[PAGE] 콘텐츠 {len(contents)}개 조회")

            for content in contents:

                text = build_embedding_text(content)
                source_hash = make_source_hash(text)

                key = (
                    content.tmdb_id,
                    content.media_type,
                )

                old = existing.get(key)

                if (
                    old
                    and old.source_hash == source_hash
                    and old.model_name == MODEL_NAME
                    and old.embedding_dimension == DIMENSION
                ):
                    skipped += 1
                    processed += 1

                    print(
                        f"[{processed}/{args.limit}] "
                        f"SKIP: {content.title}"
                    )

                    continue

                try:
                    vector = create_embedding(
                        ai_client,
                        text,
                    )

                except (Exception, KeyboardInterrupt):
                    # 임베딩 생성 중 오류 발생 시
                    # 지금까지 생성한 결과 저장 시도
                    flush_batch()
                    raise

                record = {
                    "tmdb_id": content.tmdb_id,
                    "media_type": content.media_type,
                    "embedding": vector,
                    "model_name": MODEL_NAME,
                    "embedding_dimension": DIMENSION,
                    "source_hash": source_hash,
                    "embedded_at": datetime.now(timezone.utc),
                }

                records.append(record)
                processed += 1

                print(
                    f"[{processed}/{args.limit}] "
                    f"GENERATED: {content.title}"
                )

                if len(records) >= args.batch_size:
                    flush_batch()

            # 페이지의 잔여 임베딩 저장
            flush_batch()

            # 다음 페이지 조회 기준 갱신
            last_media_type = contents[-1].media_type
            last_tmdb_id = contents[-1].tmdb_id

    finally:
        elapsed = time.monotonic() - start_time

        print("\n========== 실행 결과 ==========")
        print(f"처리 콘텐츠: {processed:,}개")
        print(f"신규/갱신 저장: {created:,}개")
        print(f"기존 재사용: {skipped:,}개")
        print(f"미저장 임베딩: {len(records):,}개")
        print(f"소요 시간: {elapsed:.2f}초")
        print("==============================")


if __name__ == "__main__":
    main()
