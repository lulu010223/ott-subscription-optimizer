import csv
import json
import os

INPUT_PATH = "data/processed/raw_merged/details_merged.json"
OUTPUT_PATH = "data/processed/content_keywords.csv"


def main():
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    seen_keys = set()

    duplicate_count = 0
    no_keyword_count = 0

    for item in data["contents"]:
        tmdb_id = item["tmdb_id"]
        media_type = item["media_type"]
        raw = item["raw_response"]

        keyword_data = raw.get("keywords") or {}

        if media_type == "movie":
            keywords = keyword_data.get("keywords") or []
        elif media_type == "tv":
            keywords = keyword_data.get("results") or []
        else:
            keywords = []

        if not keywords:
            no_keyword_count += 1
            continue

        for keyword in keywords:
            keyword_id = keyword.get("id")
            keyword_name = keyword.get("name")

            key = (media_type, tmdb_id, keyword_id)

            if key in seen_keys:
                duplicate_count += 1
                continue

            seen_keys.add(key)

            rows.append({
                "tmdb_id": tmdb_id,
                "media_type": media_type,
                "keyword_id": keyword_id,
                "keyword_name": keyword_name,
            })

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    fieldnames = [
        "tmdb_id",
        "media_type",
        "keyword_id",
        "keyword_name",
    ]

    with open(OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("[키워드 정규화 결과]")
    print("전체 콘텐츠 수:", len(data["contents"]))
    print("키워드 관계 수:", len(rows))
    print("키워드 없는 콘텐츠 수:", no_keyword_count)
    print("복합키 중복 수:", duplicate_count)
    print("저장 경로:", OUTPUT_PATH)


if __name__ == "__main__":
    main()