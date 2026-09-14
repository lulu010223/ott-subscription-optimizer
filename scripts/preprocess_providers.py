import csv
import json
import os

INPUT_PATH = "data/processed/raw_merged/details_merged.json"
OUTPUT_PATH = "data/processed/content_providers.csv"

PROVIDER_NORMALIZATION = {
    8: "Netflix",
    1796: "Netflix",
    337: "Disney+",
    356: "Wavve",
    1883: "TVING",
    97: "Watcha",
}

TARGET_PROVIDER_IDS = set(PROVIDER_NORMALIZATION.keys())


def main():
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    seen_keys = set()

    duplicate_count = 0
    no_provider_count = 0
    non_target_provider_count = 0

    for item in data["contents"]:
        tmdb_id = item["tmdb_id"]
        media_type = item["media_type"]
        raw = item["raw_response"]

        provider_data = raw.get("watch/providers") or {}
        results = provider_data.get("results") or {}
        kr_data = results.get("KR") or {}

        flatrate = kr_data.get("flatrate") or []

        target_found = False

        for provider in flatrate:
            provider_id = provider.get("provider_id")
            provider_name = provider.get("provider_name")

            if provider_id not in TARGET_PROVIDER_IDS:
                non_target_provider_count += 1
                continue

            target_found = True

            normalized_provider = PROVIDER_NORMALIZATION[provider_id]

            key = (
              media_type,
              tmdb_id,
              normalized_provider,
              )

            if key in seen_keys:
                duplicate_count += 1
                continue

            seen_keys.add(key)

            rows.append({
              "tmdb_id": tmdb_id,
              "media_type": media_type,
              "normalized_provider": normalized_provider,
              "region": "KR",
              "monetization_type": "flatrate",
              })

        if not target_found:
            no_provider_count += 1

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    fieldnames = [
      "tmdb_id",
      "media_type",
      "normalized_provider",
      "region",
      "monetization_type",
      ]

    with open(OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("[Provider 정규화 결과]")
    print("전체 콘텐츠 수:", len(data["contents"]))
    print("Provider 관계 수:", len(rows))
    print("대상 OTT 없는 콘텐츠 수:", no_provider_count)
    print("대상 외 Provider 제외 수:", non_target_provider_count)
    print("복합키 중복 수:", duplicate_count)
    print("저장 경로:", OUTPUT_PATH)


if __name__ == "__main__":
    main()