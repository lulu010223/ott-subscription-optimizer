
import argparse
import hashlib
import json
import math
import time
from datetime import datetime, timezone

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


def fetch_pending_contents(bq_client, limit):
    """아직 임베딩하지 않았거나 원본이 변경된 콘텐츠 조회."""
    query = f"""
    SELECT
      c.tmdb_id,
      c.media_type,
      c.title,
      c.genres,
      c.keywords,
      c.overview
    FROM `{SOURCE_TABLE}` AS c
    ORDER BY c.media_type, c.tmdb_id
    LIMIT @limit
    """

    config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("limit", "INT64", limit)
        ]
    )

    return list(bq_client.query(query, job_config=config).result())



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

    """선택한 콘텐츠에 대해 기존 임베딩 메타데이터 조회."""
    if not rows:
        return {}

    keys = [
        {"tmdb_id": row.tmdb_id, "media_type": row.media_type}
        for row in rows
    ]

    query = f"""
    SELECT tmdb_id, media_type, source_hash,
           model_name, embedding_dimension
    FROM `{TARGET_TABLE}`
    WHERE STRUCT(tmdb_id, media_type) IN UNNEST(@keys)
    """

    config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter(
                "keys",
                "STRUCT<tmdb_id INT64, media_type STRING>",
                keys,
            )
        ]
    )

    existing = bq_client.query(query, job_config=config).result()
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


def save_embedding(bq_client, record):
    """BigQuery MERGE로 콘텐츠별 임베딩 갱신."""
    query = f"""
    MERGE `{TARGET_TABLE}` AS T
    USING (
      SELECT
        @tmdb_id AS tmdb_id,
        @media_type AS media_type,
        @embedding AS embedding,
        @model_name AS model_name,
        @dimension AS embedding_dimension,
        @source_hash AS source_hash,
        @embedded_at AS embedded_at
    ) AS S
    ON T.tmdb_id = S.tmdb_id
       AND T.media_type = S.media_type
    WHEN MATCHED THEN UPDATE SET
      embedding = S.embedding,
      model_name = S.model_name,
      embedding_dimension = S.embedding_dimension,
      source_hash = S.source_hash,
      embedded_at = S.embedded_at
    WHEN NOT MATCHED THEN INSERT (
      tmdb_id, media_type, embedding, model_name,
      embedding_dimension, source_hash, embedded_at
    ) VALUES (
      S.tmdb_id, S.media_type, S.embedding, S.model_name,
      S.embedding_dimension, S.source_hash, S.embedded_at
    )
    """

    params = [
        bigquery.ScalarQueryParameter(
            "tmdb_id", "INT64", record["tmdb_id"]
        ),
        bigquery.ScalarQueryParameter(
            "media_type", "STRING", record["media_type"]
        ),
        bigquery.ArrayQueryParameter(
            "embedding", "FLOAT64", record["embedding"]
        ),
        bigquery.ScalarQueryParameter(
            "model_name", "STRING", record["model_name"]
        ),
        bigquery.ScalarQueryParameter(
            "dimension", "INT64", record["embedding_dimension"]
        ),
        bigquery.ScalarQueryParameter(
            "source_hash", "STRING", record["source_hash"]
        ),
        bigquery.ScalarQueryParameter(
            "embedded_at", "TIMESTAMP", record["embedded_at"]
        ),
    ]

    job_config = bigquery.QueryJobConfig(query_parameters=params)
    bq_client.query(query, job_config=job_config).result()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    if args.limit < 1 or args.limit > 10:
        parser.error("현재 테스트 단계에서는 1~10개만 허용합니다.")

    bq_client = bigquery.Client(project=PROJECT_ID)
    ai_client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location="us-central1", 
    )  

    contents = fetch_pending_contents(bq_client, args.limit)
    existing = fetch_existing_hashes(bq_client, contents)

    print(f"조회한 콘텐츠: {len(contents)}개")

    created = 0
    skipped = 0

    for index, content in enumerate(contents, start=1):
        text = build_embedding_text(content)
        source_hash = make_source_hash(text)
        key = (content.tmdb_id, content.media_type)
        old = existing.get(key)

        if (
            old
            and old.source_hash == source_hash
            and old.model_name == MODEL_NAME
            and old.embedding_dimension == DIMENSION
        ):
            print(f"[{index}] SKIP: {content.title}")
            skipped += 1
            continue

        vector = create_embedding(ai_client, text)

        record = {
            "tmdb_id": content.tmdb_id,
            "media_type": content.media_type,
            "embedding": vector,
            "model_name": MODEL_NAME,
            "embedding_dimension": DIMENSION,
            "source_hash": source_hash,
            "embedded_at": datetime.now(timezone.utc),
        }

        save_embedding(bq_client, record)
        created += 1
        print(f"[{index}] SAVED: {content.title} ({len(vector)}차원)")

    print(
        f"\n완료: 신규/갱신 {created}개, "
        f"재사용 {skipped}개"
    )


if __name__ == "__main__":
    main()
