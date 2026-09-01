import os
import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("TMDB_ACCESS_TOKEN")

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "accept": "application/json",
}

titles = [
    "오징어 게임",
    "무빙",
    "더 글로리",
    "인터스텔라",
    "선재 업고 튀어",
    "환승연애",
    "유미의 세포들",
    "시맨틱 에러",
]

for title in titles:
    # 1. 작품 검색
    search_url = "https://api.themoviedb.org/3/search/multi"

    search_params = {
        "query": title,
        "language": "ko-KR",
    }

    search_response = requests.get(
        search_url,
        headers=headers,
        params=search_params,
        timeout=10,
    )

    search_response.raise_for_status()

    results = search_response.json().get("results", [])

    if not results:
        print(f"\n{title}: 검색 결과 없음")
        continue

    content = results[0]

    tmdb_id = content["id"]
    media_type = content["media_type"]
    found_title = content.get("title") or content.get("name")

    print("\n" + "=" * 50)
    print(f"검색어: {title}")
    print(f"결과: {found_title}")
    print(f"TMDB ID: {tmdb_id}")
    print(f"Type: {media_type}")

    # 2. Watch Provider 조회
    if media_type not in ["movie", "tv"]:
        print("Watch Provider 조회 대상 아님")
        continue

    provider_url = (
        f"https://api.themoviedb.org/3/"
        f"{media_type}/{tmdb_id}/watch/providers"
    )

    provider_response = requests.get(
        provider_url,
        headers=headers,
        timeout=10,
    )

    provider_response.raise_for_status()

    kr_data = (
        provider_response.json()
        .get("results", {})
        .get("KR")
    )

    if not kr_data:
        print("한국 제공 정보 없음")
        continue

    providers = kr_data.get("flatrate", [])

    if not providers:
        print("한국 구독형 OTT 정보 없음")
        continue

    print("KR flatrate:")

    for provider in providers:
        print(
            f"- {provider['provider_id']} "
            f"{provider['provider_name']}"
        )