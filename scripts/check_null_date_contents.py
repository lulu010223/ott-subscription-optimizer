import os
import time

import requests
from dotenv import load_dotenv


load_dotenv()

TMDB_ACCESS_TOKEN = os.getenv("TMDB_ACCESS_TOKEN")

BASE_URL = "https://api.themoviedb.org/3"

TARGET_PROVIDERS = {
    356: "Wavve",
    97: "Watcha",
}

REGION = "KR"
MONETIZATION_TYPE = "flatrate"

REQUEST_DELAY = 0.25
MAX_RETRIES = 5

HEADERS = {
    "accept": "application/json",
    "Authorization": f"Bearer {TMDB_ACCESS_TOKEN}",
}


def request_tmdb(url, params):

    for attempt in range(MAX_RETRIES):

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
            print(f"429 Rate Limit → {wait_time}초 대기")
            time.sleep(wait_time)
            continue

        response.raise_for_status()

    raise RuntimeError("TMDB API 재시도 횟수를 초과했습니다.")


def get_count(provider_id, use_date_filter):

    url = f"{BASE_URL}/discover/movie"

    params = {
        "language": "ko-KR",
        "region": REGION,
        "watch_region": REGION,
        "with_watch_providers": provider_id,
        "with_watch_monetization_types": MONETIZATION_TYPE,
        "sort_by": "popularity.desc",
        "page": 1,
    }

    if use_date_filter:
        params["primary_release_date.gte"] = "1900-01-01"
        params["primary_release_date.lte"] = "2026-09-02"

    data = request_tmdb(url, params)

    return data.get("total_results", 0)


def main():

    if not TMDB_ACCESS_TOKEN:
        raise RuntimeError(
            ".env에서 TMDB_ACCESS_TOKEN을 찾을 수 없습니다."
        )

    print("=== 날짜 필터 영향 검증 ===")

    for provider_id, provider_name in TARGET_PROVIDERS.items():

        total_without_date = get_count(
            provider_id,
            use_date_filter=False,
        )

        total_with_date = get_count(
            provider_id,
            use_date_filter=True,
        )

        difference = total_without_date - total_with_date

        print()
        print(provider_name)
        print(f"날짜 필터 없음 : {total_without_date:,}")
        print(f"날짜 필터 있음 : {total_with_date:,}")
        print(f"차이           : {difference:,}")


if __name__ == "__main__":
    main()