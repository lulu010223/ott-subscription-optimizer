import os
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


def get_content_count(media_type, provider_id):
    url = f"{BASE_URL}/discover/{media_type}"

    params = {
        "language": "ko-KR",
        "region": "KR",
        "watch_region": "KR",
        "with_watch_providers": provider_id,
        "with_watch_monetization_types": "flatrate",
        "page": 1,
    }

    response = requests.get(
        url,
        headers=HEADERS,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()

    return data["total_results"]


def main():
    print("=== KR OTT 콘텐츠 규모 확인 ===\n")

    total_all = 0

    for provider_name, provider_id in PROVIDERS.items():
        movie_count = get_content_count("movie", provider_id)
        tv_count = get_content_count("tv", provider_id)
        total = movie_count + tv_count

        total_all += total

        print(f"[{provider_name}]")
        print(f"Movie : {movie_count:,}")
        print(f"TV    : {tv_count:,}")
        print(f"합계   : {total:,}")
        print("-" * 30)

    print(f"\nOTT별 단순 합계: {total_all:,}")
    print("※ 동일 콘텐츠가 여러 OTT에 존재할 수 있으므로 실제 고유 콘텐츠 수와는 다름.")


if __name__ == "__main__":
    main()