import csv
import os

CONTENTS_PATH = "data/processed/contents.csv"
PROVIDERS_PATH = "data/processed/content_providers.csv"
OUTPUT_PATH = "data/processed/contents_filtered.csv"


# 1. Provider가 존재하는 콘텐츠의 복합키 수집
valid_content_keys = set()

with open(PROVIDERS_PATH, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)

    for row in reader:
        valid_content_keys.add(
            (row["media_type"], row["tmdb_id"])
        )


# 2. contents.csv에서 해당 콘텐츠만 유지
original_count = 0
filtered_count = 0
excluded_count = 0

with open(CONTENTS_PATH, "r", encoding="utf-8-sig") as src:
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


print("[Contents 필터링 결과]")
print("기존 콘텐츠 수:", original_count)
print("Provider 기준 콘텐츠 수:", len(valid_content_keys))
print("필터링 후 콘텐츠 수:", filtered_count)
print("제외 콘텐츠 수:", excluded_count)
print("저장 경로:", OUTPUT_PATH)