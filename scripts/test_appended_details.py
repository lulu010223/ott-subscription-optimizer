import glob
import os
import time

import requests
from dotenv import load_dotenv


load_dotenv()

TMDB_ACCESS_TOKEN = os.getenv("TMDB_ACCESS_TOKEN")

BASE_URL = "https://api.themoviedb.org/3"

TEST_LIMIT = 10

TARGET_PROVIDERS = {
    8: "Netflix",
    1796: "Netflix",
    337: "Disney+",
    356: "Wavve",
    1883: "TVING",
    97: "Watcha",
}

REGION = "KR"

REQUEST_DELAY = 0.25
MAX_RETRIES = 5

HEADERS = {
    "accept": "application/json",
    "Authorization": f"Bearer {TMDB_ACCESS_TOKEN}",
}


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
                wait_time = 2 ** attempt

                print(
                    f"  429 Rate Limit → "
                    f"{wait_time}초 후 재시도 "
                    f"({attempt + 1}/{MAX_RETRIES})"
                )

                time.sleep(wait_time)
                continue

            if 500 <= response.status_code < 600:
                wait_time = 2 ** attempt

                print(
                    f"  TMDB 서버 오류 {response.status_code} → "
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
                f"  네트워크 오류: {type(error).__name__} → "
                f"{wait_time}초 후 재시도 "
                f"({attempt + 1}/{MAX_RETRIES})"
            )

            time.sleep(wait_time)

    raise RuntimeError(
        f"TMDB API 요청 실패: {MAX_RETRIES}회 재시도 후 중단"
    )


def load_test_contents():
    """
    가장 최근 contents_full_*.json에서
    Movie 5개 + TV 5개를 선택.
    """

    files = sorted(
        glob.glob(
            "data/raw/contents/contents_full_*.json"
        ),
        reverse=True,
    )

    if not files:
        raise RuntimeError(
            "data/raw/contents/ 경로에서 "
            "contents_full_*.json 파일을 찾을 수 없습니다."
        )

    input_file = files[0]

    import json

    with open(
        input_file,
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    contents = data["contents"]

    movies = [
        item
        for item in contents
        if item.get("media_type") == "movie"
    ][:5]

    tvs = [
        item
        for item in contents
        if item.get("media_type") == "tv"
    ][:5]

    selected = movies + tvs

    print(f"입력 파일: {input_file}")
    print(
        f"테스트 대상: Movie {len(movies)}개 "
        f"+ TV {len(tvs)}개 "
        f"= 총 {len(selected)}개"
    )

    return selected


def fetch_appended_details(
    tmdb_id,
    media_type,
):
    """
    Details 요청에 keywords와 watch/providers를 함께 붙임.
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


def extract_keywords(
    data,
    media_type,
):
    """
    Movie와 TV의 keywords 응답 구조 차이 처리.
    """

    keywords_data = data.get(
        "keywords",
        {},
    )

    if media_type == "movie":
        return keywords_data.get(
            "keywords",
            [],
        )

    return keywords_data.get(
        "results",
        [],
    )


def extract_kr_providers(data):
    """
    KR 지역의 flatrate provider만 추출.
    대상 OTT 5종으로 제한.
    """

    watch_data = data.get(
        "watch/providers",
        {},
    )

    kr_data = (
        watch_data
        .get("results", {})
        .get(REGION, {})
    )

    flatrate = kr_data.get(
        "flatrate",
        [],
    )

    providers = []

    seen_normalized = set()

    for provider in flatrate:

        provider_id = provider.get(
            "provider_id"
        )

        if provider_id not in TARGET_PROVIDERS:
            continue

        normalized_provider = (
            TARGET_PROVIDERS[
                provider_id
            ]
        )

        # Netflix와 Netflix 광고형처럼
        # normalized provider가 같으면 출력상 중복 제거
        if normalized_provider in seen_normalized:
            continue

        seen_normalized.add(
            normalized_provider
        )

        providers.append(
            {
                "provider_id":
                    provider_id,
                "provider_name":
                    provider.get(
                        "provider_name"
                    ),
                "normalized_provider":
                    normalized_provider,
            }
        )

    return providers


def get_title(
    data,
    media_type,
):
    if media_type == "movie":
        return data.get(
            "title"
        )

    return data.get(
        "name"
    )


def main():

    if not TMDB_ACCESS_TOKEN:
        raise RuntimeError(
            ".env에서 TMDB_ACCESS_TOKEN을 "
            "찾을 수 없습니다."
        )

    contents = load_test_contents()

    print()
    print("=" * 70)
    print("append_to_response 로컬 테스트")
    print("=" * 70)

    success_count = 0

    for index, item in enumerate(
        contents,
        start=1,
    ):

        tmdb_id = item["id"]
        media_type = item["media_type"]

        try:
            data = fetch_appended_details(
                tmdb_id,
                media_type,
            )

            title = get_title(
                data,
                media_type,
            )

            genres = data.get(
                "genres",
                [],
            )

            keywords = extract_keywords(
                data,
                media_type,
            )

            providers = extract_kr_providers(
                data
            )

            print()
            print(
                f"[{index}/{len(contents)}] "
                f"{media_type.upper()} "
                f"/ TMDB ID {tmdb_id}"
            )

            print(
                f"  제목       : {title}"
            )

            print(
                f"  장르       : {len(genres)}개"
            )

            print(
                f"  키워드     : {len(keywords)}개"
            )

            print(
                f"  KR Provider: {len(providers)}개"
            )

            if providers:
                provider_names = [
                    provider[
                        "normalized_provider"
                    ]
                    for provider in providers
                ]

                print(
                    "               "
                    + ", ".join(
                        provider_names
                    )
                )

            success_count += 1

        except Exception as error:

            print()
            print(
                f"[{index}/{len(contents)}] "
                f"{media_type.upper()} "
                f"/ TMDB ID {tmdb_id}"
            )

            print(
                f"  오류: "
                f"{type(error).__name__}: "
                f"{error}"
            )

    print()
    print("=" * 70)
    print("테스트 완료")
    print("=" * 70)

    print(
        f"성공: "
        f"{success_count}/{len(contents)}"
    )


if __name__ == "__main__":
    main()