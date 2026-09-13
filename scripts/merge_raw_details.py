import json
import glob
import os

INPUT_PATTERN = (
    "data/raw/details/"
    "details_contents_full_20260902_213730/"
    "batches/batch_*.json"
)

OUTPUT_PATH = "data/processed/raw_merged/details_merged.json"


def main():
    files = sorted(glob.glob(INPUT_PATTERN))

    print(f"배치 파일 수: {len(files)}")

    merged_contents = []
    seen_keys = set()
    duplicate_keys = []

    total_success = 0
    total_failure = 0

    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            batch = json.load(f)

        total_success += batch.get("success_count", 0)
        total_failure += batch.get("failure_count", 0)

        for item in batch.get("contents", []):
            key = (item["media_type"], item["tmdb_id"])

            if key in seen_keys:
                duplicate_keys.append(key)
                continue

            seen_keys.add(key)
            merged_contents.append(item)

    output = {
        "source_batch_count": len(files),
        "success_count": total_success,
        "failure_count": total_failure,
        "content_count": len(merged_contents),
        "duplicate_count": len(duplicate_keys),
        "contents": merged_contents,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\n[통합 결과]")
    print("success_count:", total_success)
    print("failure_count:", total_failure)
    print("통합 콘텐츠 수:", len(merged_contents))
    print("중복 수:", len(duplicate_keys))
    print("저장 경로:", OUTPUT_PATH)

    if duplicate_keys:
        print("\n[중복 예시]")
        print(duplicate_keys[:10])


if __name__ == "__main__":
    main()