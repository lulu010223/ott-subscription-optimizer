import os
import time
from datetime import date, timedelta

import requests
from dotenv import load_dotenv


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

# TMDB 실제 제한은 500페이지지만 여유를 둠
MAX_SAFE_PAGES = 450

START_DATE = date(1900, 1, 1)
END_DATE = date.today()

REQUEST_DELAY = 0.25
MAX_RETRIES = 5


HEADERS = {
    "accept": "application/json",
    "Authorization": f"Bearer {TMDB_ACCESS_TOKEN}",
}


def request_tmdb(url, params):
    """
    TMDB API 요청 함수.

    처리 대상:
    - 정상 응답 200
    - Rate Limit 429
    - 5xx 서버 오류
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

            # 정상 응답
            if response.status_code == 200:
                time.sleep(REQUEST_DELAY)
                return response.json()

            # Rate Limit
            if response.status_code == 429:
                wait_time = 2 ** attempt

                print(
                    f"  429 Rate Limit "
                    f"→ {wait_time}초 후 재시도 "
                    f"({attempt + 1}/{MAX_RETRIES})"
                )

                time.sleep(wait_time)
                continue

            # TMDB 서버 오류
            if 500 <= response.status_code < 600:
                wait_time = 2 ** attempt

                print(
                    f"  TMDB 서버 오류 {response.status_code} "
                    f"→ {wait_time}초 후 재시도 "
                    f"({attempt + 1}/{MAX_RETRIES})"
                )

                time.sleep(wait_time)
                continue

            # 그 외 HTTP 오류
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


def get_date_params(media_type, start_date, end_date):
    """
    Movie / TV 타입에 맞는 날짜 필터 반환.
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
    해당 날짜 범위의 전체 콘텐츠를 받지 않고
    page=1만 요청해서 total_pages / total_results 확인.
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
        "total_pages": data.get("total_pages", 0),
        "total_results": data.get("total_results", 0),
    }


def split_date_range(start_date, end_date):
    """
    날짜 범위를 서로 겹치지 않는 두 구간으로 분할.
    """

    total_days = (end_date - start_date).days

    mid_date = start_date + timedelta(
        days=total_days // 2
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
    depth=0,
):
    """
    total_pages가 MAX_SAFE_PAGES 이하가 될 때까지
    날짜 범위를 재귀적으로 분할.
    """

    info = get_partition_info(
        provider_id,
        media_type,
        start_date,
        end_date,
    )

    total_pages = info["total_pages"]
    total_results = info["total_results"]

    indent = "  " * depth

    print(
        f"{indent}"
        f"{start_date} ~ {end_date}"
        f" | results={total_results:,}"
        f" | pages={total_pages}"
    )

    # 안전한 페이지 수이면 최종 partition 확정
    if total_pages <= MAX_SAFE_PAGES:
        return [
            {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_pages": total_pages,
                "total_results": total_results,
            }
        ]

    # 하루 단위인데도 450페이지 초과 시 방어
    if start_date >= end_date:
        raise RuntimeError(
            f"단일 날짜 {start_date}의 결과가 "
            f"{MAX_SAFE_PAGES}페이지를 초과합니다."
        )

    left, right = split_date_range(
        start_date,
        end_date,
    )

    left_partitions = build_partitions(
        provider_id,
        media_type,
        left[0],
        left[1],
        depth + 1,
    )

    right_partitions = build_partitions(
        provider_id,
        media_type,
        right[0],
        right[1],
        depth + 1,
    )

    return (
        left_partitions
        + right_partitions
    )


def print_final_partitions(partitions):
    """
    실제 전체 수집에 사용할 최종 partition만 출력.
    """

    print()
    print("-" * 70)
    print("FINAL PARTITIONS")
    print("-" * 70)

    for index, partition in enumerate(
        partitions,
        start=1,
    ):
        print(
            f"[{index}] "
            f"{partition['start_date']} "
            f"~ {partition['end_date']}"
            f" | results={partition['total_results']:,}"
            f" | pages={partition['total_pages']}"
        )


def main():

    if not TMDB_ACCESS_TOKEN:
        raise RuntimeError(
            ".env에서 TMDB_ACCESS_TOKEN을 찾을 수 없습니다."
        )

    all_plans = {}

    for provider_id, provider_name in TARGET_PROVIDERS.items():

        all_plans[provider_name] = {}

        for media_type in MEDIA_TYPES:

            print()
            print("=" * 70)
            print(
                f"{provider_name} / "
                f"{media_type.upper()}"
            )
            print("=" * 70)

            partitions = build_partitions(
                provider_id,
                media_type,
                START_DATE,
                END_DATE,
            )

            all_plans[provider_name][media_type] = partitions

            expected_results = sum(
                partition["total_results"]
                for partition in partitions
            )

            print_final_partitions(
                partitions
            )

            print()
            print(
                f"최종 partition: {len(partitions)}개"
                f" | 예상 결과 합계: {expected_results:,}"
            )

    print()
    print("=" * 70)
    print("DRY RUN SUMMARY")
    print("=" * 70)

    for provider_name, media_data in all_plans.items():

        for media_type, partitions in media_data.items():

            total_results = sum(
                partition["total_results"]
                for partition in partitions
            )

            max_pages = max(
                partition["total_pages"]
                for partition in partitions
            )

            print(
                f"{provider_name:10}"
                f" | {media_type:5}"
                f" | partitions={len(partitions):2}"
                f" | results={total_results:,}"
                f" | max_pages={max_pages}"
            )


if __name__ == "__main__":
    main()