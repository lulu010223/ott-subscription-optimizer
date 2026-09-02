import json
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv
from google.cloud import storage


load_dotenv()

TMDB_ACCESS_TOKEN = os.getenv("TMDB_ACCESS_TOKEN")

BASE_URL = "https://api.themoviedb.org/3"

TARGET_PROVIDERS = {
    8: "Netflix",
    337: "Disney+",
    1883: "TVING",
    356: "Wavve",
    97: "Watcha",
}

MEDIA_TYPES = ["movie", "tv"]

REGION = "KR"
MONETIZATION_TYPE = "flatrate"

MAX_SAFE_PAGES = 450

START_DATE = date(1900, 1, 1)
END_DATE = date.today()

REQUEST_DELAY = 0.25
MAX_RETRIES = 5

BUCKET_NAME = "ott-optimizer-data"

LOCAL_OUTPUT_DIR = Path("data/raw/contents")

HEADERS = {
    "accept": "application/json",
    "Authorization": f"Bearer {TMDB_ACCESS_TOKEN}",
}


def request_tmdb(url, params):
    """
    TMDB API 요청.

    재시도 대상:
    - 429 Rate Limit
    - 5xx Server Error
    - ConnectionError
    - Timeout
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
                wait_time = 2 ** attempt

                print(
                    f"  429 Rate Limit "
                    f"→ {wait_time}초 후 재시도 "
                    f"({attempt + 1}/{MAX_RETRIES})"
                )

                time.sleep(wait_time)
                continue

            if 500 <= response.status_code < 600:
                wait_time = 2 ** attempt

                print(
                    f"  TMDB 서버 오류 {response.status_code} "
                    f"→ {wait_time}초 후 재시도 "
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
                f"  네트워크 오류: {type(error).__name__} "
                f"→ {wait_time}초 후 재시도 "
                f"({attempt + 1}/{MAX_RETRIES})"
            )

            time.sleep(wait_time)

    raise RuntimeError(
        f"TMDB API 요청 실패: {MAX_RETRIES}회 재시도 후 중단"
    )


def get_date_params(
    media_type,
    start_date,
    end_date,
):
    """
    Movie / TV에 맞는 날짜 필터 생성.
    """

    if media_type == "movie":
        return {
            "primary_release_date.gte": start_date.isoformat(),
            "primary_release_date.lte": end_date.isoformat(),
        }

    if media_type == "tv":
        return {
            "first_air_date.gte": start_date.isoformat(),
            "first_air_date.lte": end_date.isoformat(),
        }

    raise ValueError(
        f"지원하지 않는 media_type: {media_type}"
    )


def get_partition_info(
    provider_id,
    media_type,
    start_date,
    end_date,
):
    """
    page=1만 요청하여
    total_pages / total_results 확인.
    """

    url = f"{BASE_URL}/discover/{media_type}"

    params = {
        "language": "ko-KR",
        "region": REGION,
        "watch_region": REGION,
        "with_watch_providers": provider_id,
        "with_watch_monetization_types": MONETIZATION_TYPE,
        "sort_by": "popularity.desc",
        "page": 1,
    }

    params.update(
        get_date_params(
            media_type,
            start_date,
            end_date,
        )
    )

    data = request_tmdb(
        url,
        params,
    )

    return {
        "total_pages": data.get(
            "total_pages",
            0,
        ),
        "total_results": data.get(
            "total_results",
            0,
        ),
    }


def split_date_range(
    start_date,
    end_date,
):
    """
    날짜 범위를 겹치지 않게 2분할.
    """

    total_days = (
        end_date - start_date
    ).days

    mid_date = (
        start_date
        + timedelta(
            days=total_days // 2
        )
    )

    left = (
        start_date,
        mid_date,
    )

    right = (
        mid_date + timedelta(days=1),
        end_date,
    )

    return left, right


def build_partitions(
    provider_id,
    media_type,
    start_date,
    end_date,
):
    """
    모든 최종 partition이
    MAX_SAFE_PAGES 이하가 될 때까지
    날짜 범위를 재귀적으로 분할.
    """

    info = get_partition_info(
        provider_id,
        media_type,
        start_date,
        end_date,
    )

    total_pages = info["total_pages"]

    if total_pages <= MAX_SAFE_PAGES:
        return [
            {
                "start_date": start_date,
                "end_date": end_date,
                "total_pages": total_pages,
                "total_results": info[
                    "total_results"
                ],
            }
        ]

    if start_date >= end_date:
        raise RuntimeError(
            f"{start_date} 하루의 결과가 "
            f"{MAX_SAFE_PAGES}페이지를 초과합니다."
        )

    left, right = split_date_range(
        start_date,
        end_date,
    )

    return (
        build_partitions(
            provider_id,
            media_type,
            left[0],
            left[1],
        )
        + build_partitions(
            provider_id,
            media_type,
            right[0],
            right[1],
        )
    )


def collect_partition(
    provider_id,
    provider_name,
    media_type,
    partition,
):
    """
    하나의 최종 partition 전체 페이지 수집.
    """

    start_date = partition["start_date"]
    end_date = partition["end_date"]

    url = f"{BASE_URL}/discover/{media_type}"

    base_params = {
        "language": "ko-KR",
        "region": REGION,
        "watch_region": REGION,
        "with_watch_providers": provider_id,
        "with_watch_monetization_types": MONETIZATION_TYPE,
        "sort_by": "popularity.desc",
    }

    base_params.update(
        get_date_params(
            media_type,
            start_date,
            end_date,
        )
    )

    collected_items = []

    # 실제 수집 직전에 다시 total_pages 확인
    first_params = base_params.copy()
    first_params["page"] = 1

    first_data = request_tmdb(
        url,
        first_params,
    )

    total_pages = first_data.get(
        "total_pages",
        0,
    )

    if total_pages > 500:
        raise RuntimeError(
            f"{provider_name} / {media_type} "
            f"{start_date} ~ {end_date}: "
            f"수집 직전 total_pages={total_pages}. "
            "TMDB 500페이지 제한을 초과했습니다."
        )

    first_results = first_data.get(
        "results",
        [],
    )

    collected_items.extend(
        first_results
    )

    for page in range(
        2,
        total_pages + 1,
    ):

        params = base_params.copy()
        params["page"] = page

        data = request_tmdb(
            url,
            params,
        )

        collected_items.extend(
            data.get(
                "results",
                [],
            )
        )

        if (
            page % 50 == 0
            or page == total_pages
        ):
            print(
                f"    page "
                f"{page}/{total_pages}"
            )

    return collected_items


def normalize_item(
    item,
    media_type,
    provider_id,
    provider_name,
):
    """
    Discover 결과에 프로젝트용 메타데이터 추가.
    """

    normalized = dict(item)

    normalized["media_type"] = (
        media_type
    )

    normalized[
        "collected_from_provider_id"
    ] = provider_id

    normalized[
        "collected_from_provider"
    ] = provider_name

    normalized["source_providers"] = [
        {
            "provider_id": provider_id,
            "provider_name": provider_name,
        }
    ]

    return normalized


def merge_content(
    content_map,
    item,
):
    """
    (media_type, tmdb_id) 기준 중복 제거.

    여러 OTT에 존재하는 경우
    source_providers만 누적.
    """

    key = (
        item["media_type"],
        item["id"],
    )

    if key not in content_map:
        content_map[key] = item
        return

    existing = content_map[key]

    existing_provider_ids = {
        provider["provider_id"]
        for provider
        in existing[
            "source_providers"
        ]
    }

    for provider in item[
        "source_providers"
    ]:

        if (
            provider["provider_id"]
            not in existing_provider_ids
        ):
            existing[
                "source_providers"
            ].append(
                provider
            )


def collect_all_contents():
    """
    모든 OTT × Movie/TV 전체 수집.
    """

    content_map = {}

    collection_stats = []

    for (
        provider_id,
        provider_name,
    ) in TARGET_PROVIDERS.items():

        for media_type in MEDIA_TYPES:

            print()
            print("=" * 70)
            print(
                f"{provider_name} / "
                f"{media_type.upper()}"
            )
            print("=" * 70)

            print(
                "Partition 계산 중..."
            )

            partitions = build_partitions(
                provider_id,
                media_type,
                START_DATE,
                END_DATE,
            )

            print(
                f"최종 partition: "
                f"{len(partitions)}개"
            )

            provider_media_count = 0

            for index, partition in enumerate(
                partitions,
                start=1,
            ):

                print()
                print(
                    f"  [{index}/"
                    f"{len(partitions)}] "
                    f"{partition['start_date']} "
                    f"~ "
                    f"{partition['end_date']}"
                )

                print(
                    f"    예상 results="
                    f"{partition['total_results']:,}"
                    f" / pages="
                    f"{partition['total_pages']}"
                )

                items = collect_partition(
                    provider_id,
                    provider_name,
                    media_type,
                    partition,
                )

                provider_media_count += (
                    len(items)
                )

                print(
                    f"    실제 수집: "
                    f"{len(items):,}건"
                )

                for raw_item in items:

                    item = normalize_item(
                        raw_item,
                        media_type,
                        provider_id,
                        provider_name,
                    )

                    merge_content(
                        content_map,
                        item,
                    )

            collection_stats.append(
                {
                    "provider_id":
                        provider_id,
                    "provider_name":
                        provider_name,
                    "media_type":
                        media_type,
                    "collected_count":
                        provider_media_count,
                    "partition_count":
                        len(partitions),
                }
            )

            print()
            print(
                f"{provider_name} / "
                f"{media_type}: "
                f"{provider_media_count:,}건 완료"
            )

            print(
                f"현재 전체 unique 콘텐츠: "
                f"{len(content_map):,}"
            )

    return (
        list(
            content_map.values()
        ),
        collection_stats,
    )


def save_local_json(
    contents,
    collection_stats,
):
    """
    로컬 Raw JSON 저장.
    """

    LOCAL_OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    filename = (
        f"contents_full_{timestamp}.json"
    )

    output_path = (
        LOCAL_OUTPUT_DIR
        / filename
    )

    payload = {
        "metadata": {
            "collected_at":
                datetime.now().isoformat(),
            "region":
                REGION,
            "monetization_type":
                MONETIZATION_TYPE,
            "start_date":
                START_DATE.isoformat(),
            "end_date":
                END_DATE.isoformat(),
            "max_safe_pages":
                MAX_SAFE_PAGES,
            "providers":
                TARGET_PROVIDERS,
            "media_types":
                MEDIA_TYPES,
            "unique_content_count":
                len(contents),
            "collection_stats":
                collection_stats,
        },
        "contents": contents,
    }

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            payload,
            file,
            ensure_ascii=False,
            indent=2,
        )

    return output_path


def upload_to_gcs(
    local_path,
):
    """
    생성된 Raw JSON을
    Cloud Storage에 업로드.
    """

    client = storage.Client()

    bucket = client.bucket(
        BUCKET_NAME
    )

    destination_blob = (
        f"raw/contents/"
        f"{local_path.name}"
    )

    blob = bucket.blob(
        destination_blob
    )

    blob.upload_from_filename(
        str(local_path)
    )

    return (
        f"gs://"
        f"{BUCKET_NAME}/"
        f"{destination_blob}"
    )


def main():

    if not TMDB_ACCESS_TOKEN:
        raise RuntimeError(
            ".env에서 "
            "TMDB_ACCESS_TOKEN을 "
            "찾을 수 없습니다."
        )

    print()
    print("=" * 70)
    print("TMDB 전체 Raw 콘텐츠 수집 시작")
    print("=" * 70)

    print(
        f"수집 기간: "
        f"{START_DATE} ~ {END_DATE}"
    )

    print(
        f"대상 OTT: "
        f"{', '.join(TARGET_PROVIDERS.values())}"
    )

    print(
        f"Media Types: "
        f"{', '.join(MEDIA_TYPES)}"
    )

    print()

    start_time = time.time()

    contents, collection_stats = (
        collect_all_contents()
    )

    print()
    print("=" * 70)
    print("전체 API 수집 완료")
    print("=" * 70)

    print(
        f"Unique Contents: "
        f"{len(contents):,}"
    )

    print()
    print("로컬 JSON 저장 중...")

    output_path = save_local_json(
        contents,
        collection_stats,
    )

    print(
        f"저장 완료: "
        f"{output_path}"
    )

    print()
    print(
        "Cloud Storage 업로드 중..."
    )

    gcs_path = upload_to_gcs(
        output_path
    )

    elapsed = time.time() - start_time

    print(
        f"업로드 완료: "
        f"{gcs_path}"
    )

    print()
    print("=" * 70)
    print("전체 수집 작업 완료")
    print("=" * 70)

    print(
        f"Unique Contents : "
        f"{len(contents):,}"
    )

    print(
        f"실행 시간       : "
        f"{elapsed / 60:.1f}분"
    )

    print(
        f"Local           : "
        f"{output_path}"
    )

    print(
        f"Cloud Storage   : "
        f"{gcs_path}"
    )


if __name__ == "__main__":
    main()