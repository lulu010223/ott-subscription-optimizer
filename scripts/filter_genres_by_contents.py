import csv

CONTENTS_PATH = "data/processed/contents.csv"
GENRES_PATH = "data/processed/content_genres.csv"
OUTPUT_PATH = "data/processed/content_genres_filtered.csv"


# 최종 contents의 복합키
valid_content_keys = set()

with open(CONTENTS_PATH, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)

    for row in reader:
        valid_content_keys.add(
            (row["media_type"], row["tmdb_id"])
        )


original_count = 0
filtered_count = 0
excluded_count = 0

with open(GENRES_PATH, "r", encoding="utf-8-sig") as src:
    reader = csv.DictReader(src)
    fieldnames = reader.fieldnames

    with open(
        OUTPUT_PATH,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as dst:

        writer = csv.DictWriter(dst, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            original_count += 1

            key = (row["media_type"], row["tmdb_id"])

            if key in valid_content_keys:
                writer.writerow(row)
                filtered_count += 1
            else:
                excluded_count += 1


print("[Genre 필터링 결과]")
print("최종 contents 수:", len(valid_content_keys))
print("기존 장르 관계 수:", original_count)
print("필터링 후 장르 관계 수:", filtered_count)
print("제외된 장르 관계 수:", excluded_count)
print("저장 경로:", OUTPUT_PATH)