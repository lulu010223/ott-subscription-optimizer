import csv
import json
import os

INPUT_PATH = "data/processed/raw_merged/details_merged.json"
OUTPUT_PATH = "data/processed/contents.csv"


def normalize_content(item):
    media_type = item["media_type"]
    raw = item["raw_response"]

    if media_type == "movie":
        title = raw.get("title")
        original_title = raw.get("original_title")
        release_date = raw.get("release_date")
    else:
        title = raw.get("name")
        original_title = raw.get("original_name")
        release_date = raw.get("first_air_date")

    return {
        "tmdb_id": item["tmdb_id"],
        "media_type": media_type,
        "title": title,
        "original_title": original_title,
        "overview": raw.get("overview"),
        "release_date": release_date,
        "original_language": raw.get("original_language"),
        "popularity": raw.get("popularity"),
        "vote_average": raw.get("vote_average"),
        "vote_count": raw.get("vote_count"),
        "poster_path": raw.get("poster_path"),
    }


def main():
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = [normalize_content(item) for item in data["contents"]]

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    fieldnames = [
        "tmdb_id",
        "media_type",
        "title",
        "original_title",
        "overview",
        "release_date",
        "original_language",
        "popularity",
        "vote_average",
        "vote_count",
        "poster_path",
    ]

    with open(OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("[정제 결과]")
    print("콘텐츠 수:", len(rows))
    print("Movie 수:", sum(1 for r in rows if r["media_type"] == "movie"))
    print("TV 수:", sum(1 for r in rows if r["media_type"] == "tv"))
    print("저장 경로:", OUTPUT_PATH)


if __name__ == "__main__":
    main()