import glob
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from google.cloud import storage


# =========================================================
# 환경 설정
# =========================================================

load_dotenv()

TMDB_ACCESS_TOKEN = os.getenv("TMDB_ACCESS_TOKEN")

BASE_URL = "https://api.themoviedb.org/3"

BUCKET_NAME = "ott-optimizer-data"

REGION = "KR"

TARGET_PROVIDERS = {
    8: "Netflix",
    1796: "Netflix",
    337: "Disney+",
    356: "Wavve",
    1883: "TVING",
    97: "Watcha",
}

BATCH_SIZE = 100
REQUEST_DELAY = 0.25
MAX_RETRIES = 5

HEADERS = {
    "accept": "application/json",
    "Authorization": f"Bearer {TMDB_ACCESS_TOKEN}",
}


# =========================================================
# 공통 함수
# =========================================================

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def request_tmdb(url, params):
    """
    TMDB API 요청.
    429 / 5xx / 네트워크 오류 발생 시 재시도.
    """

    for attempt in range(MAX_RETRIES):

        try:
            response = requests.get(
                url,
                headers=HEADERS,
                params=params,
                timeout=30,
            )

            if response.status_code == 200:
                time.sleep(REQUEST_DELAY)
                return response.json()

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")

                if retry_after:
                    wait_time = int(retry_after)
                else:
                    wait_time = 2 ** attempt

                print(
                    f"    429 Rate Limit → "
                    f"{wait_time}초 후 재시도 "
                    f"({attempt + 1}/{MAX_RETRIES})"
                )

                time.sleep(wait_time)
                continue

            if 500 <= response.status_code < 600:
                wait_time = 2 ** attempt

                print(
                    f"    TMDB 서버 오류 {response.status_code} → "
                    f"{wait_time}초 후 재시도 "
                    f"({attempt + 1}/{MAX_RETRIES})"
                )

                time.sleep(wait_time)
                continue

            response.raise_for_status()

        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ) as error:

            wait_time = 2 ** attempt

            print(
                f"    네트워크 오류 "
                f"{type(error).__name__} → "
                f"{wait_time}초 후 재시도 "
                f"({attempt + 1}/{MAX_RETRIES})"
            )

            time.sleep(wait_time)

    raise RuntimeError(
        f"TMDB API 요청 실패: {MAX_RETRIES}회 재시도 후 중단"
    )


# =========================================================
# 입력 Raw 파일
# =========================================================

def find_latest_contents_file():
    files = sorted(
        glob.glob(
            "data/raw/contents/contents_full_*.json"
        ),
        reverse=True,
    )

    if not files:
        raise RuntimeError(
            "contents_full_*.json 파일을 찾을 수 없습니다."
        )

    return files[0]


def load_contents(input_file):
    with open(
        input_file,
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    return data["contents"]


# =========================================================
# 상세 데이터 API
# =========================================================

def fetch_content_details(
    tmdb_id,
    media_type,
):
    """
    Details + Keywords + Watch Providers를
    한 번의 API 요청으로 수집.
    """

    url = (
        f"{BASE_URL}/"
        f"{media_type}/"
        f"{tmdb_id}"
    )

    params = {
        "language": "ko-KR",
        "append_to_response": "keywords,watch/providers",
    }

    return request_tmdb(
        url,
        params,
    )


# =========================================================
# 저장
# =========================================================

def save_json(
    path,
    data,
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = path.with_suffix(
        path.suffix + ".tmp"
    )

    with open(
        temp_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    temp_path.replace(path)


def upload_to_gcs(
    storage_client,
    local_path,
    gcs_path,
):
    bucket = storage_client.bucket(
        BUCKET_NAME
    )

    blob = bucket.blob(
        gcs_path
    )

    blob.upload_from_filename(
        str(local_path)
    )


# =========================================================
# Checkpoint
# =========================================================

def load_checkpoint(
    checkpoint_path,
):
    if not checkpoint_path.exists():
        return {
            "next_index": 0,
            "completed_batches": 0,
            "success_count": 0,
            "failure_count": 0,
        }

    with open(
        checkpoint_path,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def save_checkpoint(
    checkpoint_path,
    checkpoint,
):
    save_json(
        checkpoint_path,
        checkpoint,
    )


# =========================================================
# Batch 처리
# =========================================================

def process_batch(
    contents,
    start_index,
    end_index,
):
    success_records = []
    failed_records = []

    for index in range(
        start_index,
        end_index,
    ):

        item = contents[index]

        tmdb_id = item["id"]
        media_type = item["media_type"]

        title = (
            item.get("title")
            or item.get("name")
            or ""
        )

        print(
            f"[{index + 1}/{len(contents)}] "
            f"{media_type.upper()} "
            f"{tmdb_id} "
            f"{title}"
        )

        try:
            raw_response = fetch_content_details(
                tmdb_id,
                media_type,
            )

            success_records.append(
                {
                    "tmdb_id": tmdb_id,
                    "media_type": media_type,
                    "fetched_at": now_iso(),
                    "raw_response": raw_response,
                }
            )

        except Exception as error:

            print(
                f"    ❌ 실패: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            failed_records.append(
                {
                    "tmdb_id": tmdb_id,
                    "media_type": media_type,
                    "title": title,
                    "error_type":
                        type(error).__name__,
                    "error_message":
                        str(error),
                    "failed_at":
                        now_iso(),
                }
            )

    return (
        success_records,
        failed_records,
    )


# =========================================================
# Main
# =========================================================

def main():

    if not TMDB_ACCESS_TOKEN:
        raise RuntimeError(
            ".env에서 TMDB_ACCESS_TOKEN을 찾을 수 없습니다."
        )

    input_file = find_latest_contents_file()

    contents = load_contents(
        input_file
    )

    input_stem = Path(
        input_file
    ).stem

    run_name = (
        f"details_{input_stem}"
    )

    output_dir = (
        Path("data/raw/details")
        / run_name
    )

    batch_dir = (
        output_dir
        / "batches"
    )

    checkpoint_path = (
        output_dir
        / "checkpoint.json"
    )

    failed_path = (
        output_dir
        / "failed_contents.json"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    batch_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    checkpoint = load_checkpoint(
        checkpoint_path
    )

    start_index = checkpoint[
        "next_index"
    ]

    storage_client = storage.Client()

    total_contents = len(contents)

    print("=" * 70)
    print("TMDB 전체 상세정보 수집")
    print("=" * 70)

    print(
        f"입력 파일   : {input_file}"
    )

    print(
        f"전체 콘텐츠 : "
        f"{total_contents:,}개"
    )

    print(
        f"Batch 크기  : "
        f"{BATCH_SIZE}개"
    )

    print(
        f"시작 위치   : "
        f"{start_index:,}"
    )

    print(
        f"로컬 저장   : "
        f"{output_dir}"
    )

    print(
        f"GCS 저장    : "
        f"gs://{BUCKET_NAME}/raw/details/{run_name}/"
    )

    print("=" * 70)

    if start_index >= total_contents:
        print("이미 전체 수집이 완료되어 있습니다.")
        return

    existing_failures = []

    if failed_path.exists():
        with open(
            failed_path,
            "r",
            encoding="utf-8",
        ) as file:
            existing_failures = (
                json.load(file)
            )

    start_time = time.time()

    batch_number = (
        checkpoint[
            "completed_batches"
        ]
        + 1
    )

    for batch_start in range(
        start_index,
        total_contents,
        BATCH_SIZE,
    ):

        batch_end = min(
            batch_start + BATCH_SIZE,
            total_contents,
        )

        print()
        print(
            "=" * 70
        )

        print(
            f"Batch {batch_number} "
            f"({batch_start + 1:,}"
            f" ~ "
            f"{batch_end:,})"
        )

        print(
            "=" * 70
        )

        (
            success_records,
            failed_records,
        ) = process_batch(
            contents,
            batch_start,
            batch_end,
        )

        batch_payload = {
            "batch_number":
                batch_number,
            "source_file":
                input_file,
            "batch_start_index":
                batch_start,
            "batch_end_index":
                batch_end,
            "success_count":
                len(success_records),
            "failure_count":
                len(failed_records),
            "collected_at":
                now_iso(),
            "contents":
                success_records,
        }

        batch_filename = (
            f"batch_"
            f"{batch_number:05d}.json"
        )

        batch_path = (
            batch_dir
            / batch_filename
        )

        save_json(
            batch_path,
            batch_payload,
        )

        # GCS batch 업로드
        gcs_batch_path = (
            f"raw/details/"
            f"{run_name}/"
            f"batches/"
            f"{batch_filename}"
        )

        upload_to_gcs(
            storage_client,
            batch_path,
            gcs_batch_path,
        )

        # 실패 데이터 누적
        if failed_records:

            existing_failures.extend(
                failed_records
            )

            save_json(
                failed_path,
                existing_failures,
            )

            gcs_failed_path = (
                f"raw/details/"
                f"{run_name}/"
                f"failed_contents.json"
            )

            upload_to_gcs(
                storage_client,
                failed_path,
                gcs_failed_path,
            )

        # checkpoint 갱신
        checkpoint[
            "next_index"
        ] = batch_end

        checkpoint[
            "completed_batches"
        ] = batch_number

        checkpoint[
            "success_count"
        ] += len(
            success_records
        )

        checkpoint[
            "failure_count"
        ] += len(
            failed_records
        )

        checkpoint[
            "updated_at"
        ] = now_iso()

        save_checkpoint(
            checkpoint_path,
            checkpoint,
        )

        gcs_checkpoint_path = (
            f"raw/details/"
            f"{run_name}/"
            f"checkpoint.json"
        )

        upload_to_gcs(
            storage_client,
            checkpoint_path,
            gcs_checkpoint_path,
        )

        elapsed = (
            time.time()
            - start_time
        )

        print()
        print(
            f"✅ Batch {batch_number} 저장 완료"
        )

        print(
            f"성공: "
            f"{len(success_records)}"
            f" / 실패: "
            f"{len(failed_records)}"
        )

        print(
            f"전체 진행: "
            f"{batch_end:,}"
            f" / "
            f"{total_contents:,}"
        )

        print(
            f"누적 성공: "
            f"{checkpoint['success_count']:,}"
        )

        print(
            f"누적 실패: "
            f"{checkpoint['failure_count']:,}"
        )

        print(
            f"현재 실행시간: "
            f"{elapsed / 60:.1f}분"
        )

        batch_number += 1

    total_elapsed = (
        time.time()
        - start_time
    )

    print()
    print("=" * 70)
    print("전체 상세정보 수집 완료")
    print("=" * 70)

    print(
        f"총 콘텐츠 : "
        f"{total_contents:,}"
    )

    print(
        f"성공      : "
        f"{checkpoint['success_count']:,}"
    )

    print(
        f"실패      : "
        f"{checkpoint['failure_count']:,}"
    )

    print(
        f"실행 시간 : "
        f"{total_elapsed / 60:.1f}분"
    )

    print(
        f"Local     : "
        f"{output_dir}"
    )

    print(
        f"GCS       : "
        f"gs://{BUCKET_NAME}/raw/details/{run_name}/"
    )


if __name__ == "__main__":
    main()