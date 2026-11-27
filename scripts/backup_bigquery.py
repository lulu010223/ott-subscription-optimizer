
from pathlib import Path
from datetime import datetime

import pyarrow.parquet as pq

from google.cloud import bigquery


PROJECT_ID = "lulu260902"
DATASET_ID = "ott_optimizer"
LOCATION = "asia-northeast3"

BACKUP_DIR = (
    Path(__file__).resolve().parents[1] / "backups"
)

TABLES = [
    "content_embeddings",
    "content_analysis",
    "ott_plans",
    "bundle_catalog",
]


def backup_table(client, table_name, output_dir):

    table_id = f"{PROJECT_ID}.{DATASET_ID}.{table_name}"

    output_path = output_dir / f"{table_name}.parquet"
    temp_path = output_dir / f"{table_name}.parquet.tmp"

    print(f"\n===== {table_name} =====")
    print("BigQuery 데이터 조회 중...")

    query = f"SELECT * FROM `{table_id}`"

    rows = client.query(
        query,
        location=LOCATION,
    ).result()

    expected_count = rows.total_rows

    # BigQuery Storage API를 사용하지 않고 조회
    arrow_table = rows.to_arrow(
        create_bqstorage_client=False,
    )

    print(f"조회 완료: {arrow_table.num_rows:,}개")

    # Parquet 파일 저장
    pq.write_table(
        arrow_table,
        temp_path,
        compression="snappy",
    )

    # 저장된 파일 재조회
    saved_table = pq.read_table(temp_path)

    if saved_table.num_rows != expected_count:
        raise ValueError(
            f"행 수 불일치: {table_name}"
        )

    if not saved_table.schema.equals(
        arrow_table.schema,
        check_metadata=False,
    ):
        raise ValueError(
            f"스키마 불일치: {table_name}"
        )

    if not saved_table.equals(arrow_table):
        raise ValueError(
            f"데이터 불일치: {table_name}"
        )

    # 검증 완료 후 최종 파일명으로 변경
    temp_path.replace(output_path)

    file_size = output_path.stat().st_size / (1024 ** 2)

    print(f"저장 위치: {output_path}")
    print(f"파일 크기: {file_size:.2f} MiB")
    print(f"행 수 검증: 통과")
    print(f"스키마 검증: 통과")
    print(f"데이터 일치 검증: 통과")

    return {
        "table": table_name,
        "rows": saved_table.num_rows,
        "size_mib": file_size,
    }


def main():

    client = bigquery.Client(project=PROJECT_ID)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_dir = BACKUP_DIR / timestamp
    output_dir.mkdir(parents=True, exist_ok=False)

    results = []

    for table_name in TABLES:
        result = backup_table(
            client,
            table_name,
            output_dir,
        )

        results.append(result)

    print("\n========== 백업 결과 ==========")

    for result in results:
        print(
            f"{result['table']}: "
            f"{result['rows']:,}개 / "
            f"{result['size_mib']:.2f} MiB"
        )

    total_size = sum(
        result["size_mib"]
        for result in results
    )

    print(f"\n백업 완료: {len(results)}/{len(TABLES)}개")
    print(f"전체 용량: {total_size:.2f} MiB")
    print(f"백업 디렉터리: {output_dir}")

    print("===============================")


if __name__ == "__main__":
    main()
