import json
import os
import time
from datetime import datetime

import requests
from dotenv import load_dotenv


load_dotenv()

TMDB_ACCESS_TOKEN = os.getenv("TMDB_ACCESS_TOKEN")

BASE_URL = "https://api.themoviedb.org/3"

HEADERS = {
    "Authorization": f"Bearer {TMDB_ACCESS_TOKEN}",
    "accept": "application/json",
}

PROVIDERS = {
    "Netflix": 8,
    "Disney+": 337,
    "TVING": 1883,
    "Wavve": 356,
    "Watcha": 97,
}

MEDIA_TYPES = ["movie", "tv"]

# 로컬 테스트용
# OTT × media_type 조합마다 최대 30개씩 수집
ITEMS_PER_QUERY = 30

OUTPUT_DIR = "data/raw/contents"


def request_tmdb(url, params, max_retries=3):
    """
    TMDB API 요청.
    429 등의 일시적인 오류 발생 시 재시도.
    """
    for attempt in range(max_retries):
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=30,
        )

        if response.status_code == 429:
            wait_time = 2 ** attempt
            print(f"Rate limit 발생 → {wait_time}초 후 재시도")
            time.sleep(wait_time)
            continue

        response.raise_for_status()
        return response.json()

    raise RuntimeError("TMDB API 요청 재시도 횟수를 초과했습니다.")


def collect_provider_contents(provider_name, provider_id, media_type):
    """
    특정 OTT / Movie 또는 TV 조합의 콘텐츠를
    ITEMS_PER_QUERY만큼 수집.
    """

    url = f"{BASE_URL}/discover/{media_type}"

    collected = []
    page = 1

    while len(collected) < ITEMS_PER_QUERY:
        params = {
            "language": "ko-KR",
            "region": "KR",
            "watch_region": "KR",
            "with_watch_providers": provider_id,
            "with_watch_monetization_types": "flatrate",
            "sort_by": "popularity.desc",
            "page": page,
        }

        data = request_tmdb(url, params)

        results = data.get("results", [])

        if not results:
            break

        for item in results:
            # movie / tv를 구분할 수 있도록 직접 추가
            item["media_type"] = media_type

            # 어떤 Provider 조회에서 발견됐는지 기록
            item["collected_from_provider_id"] = provider_id
            item["collected_from_provider"] = provider_name

            collected.append(item)

            if len(collected) >= ITEMS_PER_QUERY:
                break

        if page >= data.get("total_pages", 1):
            break

        page += 1

        # API에 너무 빠르게 요청하지 않도록 짧은 간격
        time.sleep(0.1)

    return collected


def main():
    if not TMDB_ACCESS_TOKEN:
        raise ValueError(
            "TMDB_ACCESS_TOKEN을 찾을 수 없습니다. "
            ".env 파일을 확인해주세요."
        )

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # key = (media_type, tmdb_id)
    unique_contents = {}

    print("=== TMDB 로컬 테스트 수집 시작 ===\n")

    for provider_name, provider_id in PROVIDERS.items():
        for media_type in MEDIA_TYPES:

            print(
                f"[수집] {provider_name} / "
                f"{media_type.upper()}"
            )

            contents = collect_provider_contents(
                provider_name,
                provider_id,
                media_type,
            )

            for item in contents:
                key = (
                    item["media_type"],
                    item["id"],
                )

                if key not in unique_contents:
                    # 처음 발견된 콘텐츠
                    item["source_providers"] = [
                        {
                            "provider_id": provider_id,
                            "provider_name": provider_name,
                        }
                    ]

                    unique_contents[key] = item

                else:
                    # 이미 다른 OTT에서 발견된 콘텐츠
                    provider_info = {
                        "provider_id": provider_id,
                        "provider_name": provider_name,
                    }

                    existing = unique_contents[key][
                        "source_providers"
                    ]

                    if provider_info not in existing:
                        existing.append(provider_info)

            print(
                f"  → {len(contents)}건 조회 / "
                f"현재 고유 콘텐츠 {len(unique_contents)}건\n"
            )

    output_data = {
        "metadata": {
            "collected_at": datetime.now().isoformat(),
            "region": "KR",
            "monetization_type": "flatrate",
            "providers": PROVIDERS,
            "items_per_query": ITEMS_PER_QUERY,
            "unique_content_count": len(unique_contents),
        },
        "contents": list(unique_contents.values()),
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_path = os.path.join(
        OUTPUT_DIR,
        f"contents_test_{timestamp}.json",
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output_data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print("=" * 50)
    print("수집 완료")
    print(f"고유 콘텐츠 수: {len(unique_contents):,}")
    print(f"저장 위치: {output_path}")


if __name__ == "__main__":
    main()