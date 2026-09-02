import glob
import json
import os
import time

import requests
from dotenv import load_dotenv


load_dotenv()

TMDB_ACCESS_TOKEN = os.getenv("TMDB_ACCESS_TOKEN")

BASE_URL = "https://api.themoviedb.org/3"

HEADERS = {
    "Authorization": f"Bearer {TMDB_ACCESS_TOKEN}",
    "accept": "application/json",
}

# Movie / TV가 섞이도록 최대 10개 테스트
TEST_LIMIT = 10

# 현재 프로젝트에서 분석할 OTT
TARGET_PROVIDERS = {
    8: "Netflix",
    1796: "Netflix",
    337: "Disney+",
    356: "Wavve",
    1883: "TVING",
    97: "Watcha",
}

OUTPUT_DIR = "data/raw/details"


def request_tmdb(endpoint, params=None, max_retries=3):
    url = f"{BASE_URL}{endpoint}"

    if params is None:
        params = {}

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

    raise RuntimeError(
        f"TMDB API 요청 실패: {endpoint}"
    )


def get_latest_contents_file():
    files = glob.glob(
        "data/raw/contents/contents_test_*.json"
    )

    if not files:
        raise FileNotFoundError(
            "기존 테스트 콘텐츠 JSON을 찾을 수 없습니다."
        )

    return max(files, key=os.path.getmtime)


def load_test_contents():
    filepath = get_latest_contents_file()

    print(f"입력 파일: {filepath}\n")

    with open(filepath, "r", encoding="utf-8") as file:
        data = json.load(file)

    contents = data["contents"]

    # Movie와 TV가 모두 포함되도록 선택
    movies = [
        item for item in contents
        if item["media_type"] == "movie"
    ]

    tvs = [
        item for item in contents
        if item["media_type"] == "tv"
    ]

    half = TEST_LIMIT // 2

    selected = (
        movies[:half]
        + tvs[:TEST_LIMIT - half]
    )

    return selected


def get_details(tmdb_id, media_type):
    return request_tmdb(
        f"/{media_type}/{tmdb_id}",
        params={
            "language": "ko-KR",
        },
    )


def get_keywords(tmdb_id, media_type):
    data = request_tmdb(
        f"/{media_type}/{tmdb_id}/keywords"
    )

    # Movie API → "keywords"
    # TV API → "results"
    if media_type == "movie":
        return data.get("keywords", [])

    return data.get("results", [])


def get_watch_providers(tmdb_id, media_type):
    data = request_tmdb(
        f"/{media_type}/{tmdb_id}/watch/providers"
    )

    kr_data = data.get(
        "results",
        {},
    ).get(
        "KR",
        {},
    )

    flatrate = kr_data.get(
        "flatrate",
        [],
    )

    providers = []

    for provider in flatrate:
        provider_id = provider["provider_id"]

        # 프로젝트 대상 OTT만 저장
        if provider_id in TARGET_PROVIDERS:
            providers.append(
                {
                    "provider_id": provider_id,
                    "provider_name": provider[
                        "provider_name"
                    ],
                    "normalized_provider":
                        TARGET_PROVIDERS[provider_id],
                    "monetization_type": "flatrate",
                    "region": "KR",
                }
            )

    return providers


def collect_content_details(item):
    tmdb_id = item["id"]
    media_type = item["media_type"]

    details = get_details(
        tmdb_id,
        media_type,
    )

    keywords = get_keywords(
        tmdb_id,
        media_type,
    )

    providers = get_watch_providers(
        tmdb_id,
        media_type,
    )

    # Movie / TV 필드명이 다르므로 통일
    title = (
        details.get("title")
        if media_type == "movie"
        else details.get("name")
    )

    original_title = (
        details.get("original_title")
        if media_type == "movie"
        else details.get("original_name")
    )

    release_date = (
        details.get("release_date")
        if media_type == "movie"
        else details.get("first_air_date")
    )

    result = {
        "content": {
            "tmdb_id": tmdb_id,
            "media_type": media_type,
            "title": title,
            "original_title": original_title,
            "overview": details.get("overview"),
            "release_date": release_date,
            "original_language": details.get(
                "original_language"
            ),
            "popularity": details.get("popularity"),
            "vote_average": details.get(
                "vote_average"
            ),
            "vote_count": details.get(
                "vote_count"
            ),
            "poster_path": details.get(
                "poster_path"
            ),
        },

        "genres": [
            {
                "tmdb_id": tmdb_id,
                "media_type": media_type,
                "genre_id": genre["id"],
                "genre_name": genre["name"],
            }
            for genre in details.get(
                "genres",
                [],
            )
        ],

        "keywords": [
            {
                "tmdb_id": tmdb_id,
                "media_type": media_type,
                "keyword_id": keyword["id"],
                "keyword_name": keyword["name"],
            }
            for keyword in keywords
        ],

        "providers": [
            {
                "tmdb_id": tmdb_id,
                "media_type": media_type,
                **provider,
            }
            for provider in providers
        ],
    }

    return result


def main():
    if not TMDB_ACCESS_TOKEN:
        raise ValueError(
            "TMDB_ACCESS_TOKEN을 찾을 수 없습니다. "
            ".env 파일을 확인해주세요."
        )

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True,
    )

    test_contents = load_test_contents()

    results = []

    print(
        "=== 콘텐츠 상세 데이터 로컬 테스트 ===\n"
    )

    for index, item in enumerate(
        test_contents,
        start=1,
    ):
        tmdb_id = item["id"]
        media_type = item["media_type"]

        print(
            f"[{index}/{len(test_contents)}] "
            f"{media_type.upper()} / "
            f"TMDB ID {tmdb_id}"
        )

        result = collect_content_details(item)

        results.append(result)

        print(
            f"  제목      : "
            f"{result['content']['title']}"
        )
        print(
            f"  장르      : "
            f"{len(result['genres'])}개"
        )
        print(
            f"  키워드    : "
            f"{len(result['keywords'])}개"
        )
        print(
            f"  Provider  : "
            f"{len(result['providers'])}개"
        )
        print()

        time.sleep(0.1)

    output_path = os.path.join(
        OUTPUT_DIR,
        "content_details_test.json",
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            results,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print("=" * 50)
    print("상세 데이터 수집 테스트 완료")
    print(f"테스트 콘텐츠 수: {len(results)}")
    print(f"저장 위치: {output_path}")


if __name__ == "__main__":
    main()