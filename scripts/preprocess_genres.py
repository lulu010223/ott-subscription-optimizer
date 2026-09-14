import csv
import json
import os

INPUT_PATH = "data/processed/raw_merged/details_merged.json"
OUTPUT_PATH = "data/processed/content_genres.csv"


def main():
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    seen_keys = set()
    duplicate_count = 0
    no_genre_count = 0

    for item in data["contents"]:
        tmdb_id = item["tmdb_id"]
        media_type = item["media_type"]
        raw = item["raw_response"]

        genres = raw.get("genres") or []

        if not genres:
            no_genre_count += 1
            continue

        for genre in genres:
            genre_id = genre.get("id")
            genre_name = genre.get("name")

            key = (media_type, tmdb_id, genre_id)

            if key in seen_keys:
                duplicate_count += 1
                continue

            seen_keys.add(key)

            rows.append({
                "tmdb_id": tmdb_id,
                "media_type": media_type,
                "genre_id": genre_id,
                "genre_name": genre_name,
            })

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    fieldnames = [
        "tmdb_id",
        "media_type",
        "genre_id",
        "genre_name",
    ]

    with open(OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("[장르 정규화 결과]")
    print("전체 콘텐츠 수:", len(data["contents"]))
    print("장르 관계 수:", len(rows))
    print("장르 없는 콘텐츠 수:", no_genre_count)
    print("복합키 중복 수:", duplicate_count)
    print("저장 경로:", OUTPUT_PATH)


if __name__ == "__main__":
    main()