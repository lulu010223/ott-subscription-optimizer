import csv
from pathlib import Path
from collections import Counter

BASE = Path("data/processed")

FILES = {
    "contents": BASE / "contents.csv",
    "genres": BASE / "content_genres.csv",
    "keywords": BASE / "content_keywords.csv",
    "providers": BASE / "content_providers.csv",
    "plans": BASE / "ott_plans.csv",
    "bundles": BASE / "ott_bundles.csv",
    "bundle_providers": BASE / "bundle_providers.csv",
}

TARGET_PROVIDERS = {
    "Netflix",
    "Disney+",
    "TVING",
    "Wavve",
    "Watcha",
}


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def check_duplicate_keys(rows, fields):
    keys = [tuple(row[field] for field in fields) for row in rows]
    return len(keys) - len(set(keys))


def check_missing(rows, fields):
    missing = Counter()

    for row in rows:
        for field in fields:
            value = row.get(field)

            if value is None or value.strip() == "":
                missing[field] += 1

    return missing


def main():
    print("=" * 60)
    print("Processed Data 최종 검증")
    print("=" * 60)

    # --------------------------------------------------
    # 0. 파일 존재 여부
    # --------------------------------------------------
    print("\n[1. 파일 존재 여부]")

    missing_files = []

    for name, path in FILES.items():
        if path.exists():
            print(f"PASS  {name}: {path}")
        else:
            print(f"FAIL  {name}: {path}")
            missing_files.append(str(path))

    if missing_files:
        print("\n필수 파일이 없어 검증을 중단합니다.")
        return

    # --------------------------------------------------
    # 데이터 로드
    # --------------------------------------------------
    contents = read_csv(FILES["contents"])
    genres = read_csv(FILES["genres"])
    keywords = read_csv(FILES["keywords"])
    providers = read_csv(FILES["providers"])
    plans = read_csv(FILES["plans"])
    bundles = read_csv(FILES["bundles"])
    bundle_providers = read_csv(FILES["bundle_providers"])

    # --------------------------------------------------
    # 1. contents
    # --------------------------------------------------
    print("\n[2. contents 검증]")

    content_keys = {
        (row["media_type"], row["tmdb_id"])
        for row in contents
    }

    content_duplicate = check_duplicate_keys(
        contents,
        ["media_type", "tmdb_id"],
    )

    content_missing = check_missing(
        contents,
        [
            "tmdb_id",
            "media_type",
            "title",
            "original_title",
            "release_date",
            "original_language",
            "popularity",
            "vote_average",
            "vote_count",
        ],
    )

    movie_count = sum(
        1 for row in contents
        if row["media_type"] == "movie"
    )

    tv_count = sum(
        1 for row in contents
        if row["media_type"] == "tv"
    )

    print("전체 콘텐츠:", len(contents))
    print("Movie:", movie_count)
    print("TV:", tv_count)
    print("복합키 중복:", content_duplicate)
    print("필수값 결측:", sum(content_missing.values()))

    # --------------------------------------------------
    # 2. 관계 테이블 orphan / duplicate 검증
    # --------------------------------------------------
    print("\n[3. 관계 테이블 검증]")

    relation_configs = [
        (
            "content_genres",
            genres,
            ["media_type", "tmdb_id", "genre_id"],
        ),
        (
            "content_keywords",
            keywords,
            ["media_type", "tmdb_id", "keyword_id"],
        ),
        (
            "content_providers",
            providers,
            ["media_type", "tmdb_id", "normalized_provider"],
        ),
    ]

    orphan_counts = {}

    for name, rows, key_fields in relation_configs:
        duplicates = check_duplicate_keys(rows, key_fields)

        orphans = [
            row for row in rows
            if (row["media_type"], row["tmdb_id"])
            not in content_keys
        ]

        orphan_counts[name] = len(orphans)

        print(
            f"{name}: "
            f"{len(rows)}행 / "
            f"중복 {duplicates} / "
            f"orphan {len(orphans)}"
        )

    # --------------------------------------------------
    # 3. Provider 검증
    # --------------------------------------------------
    print("\n[4. Provider 검증]")

    provider_names = {
        row["normalized_provider"]
        for row in providers
    }

    invalid_providers = provider_names - TARGET_PROVIDERS

    contents_with_provider = {
        (row["media_type"], row["tmdb_id"])
        for row in providers
    }

    contents_without_provider = (
        content_keys - contents_with_provider
    )

    print("Provider 종류:", sorted(provider_names))
    print("대상 외 Provider:", sorted(invalid_providers))
    print("Provider 없는 contents:", len(contents_without_provider))

    # --------------------------------------------------
    # 4. OTT 요금제 검증
    # --------------------------------------------------
    print("\n[5. OTT 요금제 검증]")

    plan_duplicates = check_duplicate_keys(
        plans,
        ["provider", "plan_name"],
    )

    plan_missing = check_missing(
        plans,
        [
            "provider",
            "plan_name",
            "monthly_price",
            "ads",
            "simultaneous_streams",
            "max_quality",
            "collected_at",
        ],
    )

    plan_providers = {
        row["provider"]
        for row in plans
    }

    invalid_plan_provider = (
        plan_providers - TARGET_PROVIDERS
    )

    invalid_prices = [
        row for row in plans
        if not row["monthly_price"].isdigit()
        or int(row["monthly_price"]) <= 0
    ]

    invalid_streams = [
        row for row in plans
        if not row["simultaneous_streams"].isdigit()
        or int(row["simultaneous_streams"]) <= 0
    ]

    invalid_ads = [
        row for row in plans
        if row["ads"] not in {"TRUE", "FALSE"}
    ]

    print("요금제 수:", len(plans))
    print("Provider:", sorted(plan_providers))
    print("복합키 중복:", plan_duplicates)
    print("결측:", sum(plan_missing.values()))
    print("대상 외 Provider:", sorted(invalid_plan_provider))
    print("가격 형식 오류:", len(invalid_prices))
    print("동시접속 형식 오류:", len(invalid_streams))
    print("ads 형식 오류:", len(invalid_ads))

    # --------------------------------------------------
    # 5. 번들 검증
    # --------------------------------------------------
    print("\n[6. OTT Bundle 검증]")

    bundle_ids = {
        row["bundle_id"]
        for row in bundles
    }

    bundle_relation_ids = {
        row["bundle_id"]
        for row in bundle_providers
    }

    bundle_duplicates = check_duplicate_keys(
        bundles,
        ["bundle_id"],
    )

    bundle_provider_duplicates = check_duplicate_keys(
        bundle_providers,
        ["bundle_id", "provider"],
    )

    unknown_bundle_ids = (
        bundle_relation_ids - bundle_ids
    )

    bundles_without_provider = (
        bundle_ids - bundle_relation_ids
    )

    bundle_provider_names = {
        row["provider"]
        for row in bundle_providers
    }

    invalid_bundle_providers = (
        bundle_provider_names - TARGET_PROVIDERS
    )

    # bundle provider가 실제 ott_plans Provider와도 일치하는지
    providers_without_plan = (
        bundle_provider_names - plan_providers
    )

    print("번들 수:", len(bundles))
    print("Bundle-Provider 관계 수:", len(bundle_providers))
    print("bundle_id 중복:", bundle_duplicates)
    print(
        "bundle-provider 복합키 중복:",
        bundle_provider_duplicates,
    )
    print(
        "존재하지 않는 bundle_id 참조:",
        sorted(unknown_bundle_ids),
    )
    print(
        "Provider 관계 없는 번들:",
        sorted(bundles_without_provider),
    )
    print(
        "대상 외 Bundle Provider:",
        sorted(invalid_bundle_providers),
    )
    print(
        "요금제가 없는 Bundle Provider:",
        sorted(providers_without_plan),
    )

    # --------------------------------------------------
    # 6. 최종 판정
    # --------------------------------------------------
    print("\n" + "=" * 60)
    print("[최종 판정]")

    errors = []

    if len(contents) != 33859:
        errors.append(
            f"contents 수가 33859가 아님: {len(contents)}"
        )

    if content_duplicate:
        errors.append("contents 복합키 중복 존재")

    if sum(content_missing.values()):
        errors.append("contents 필수값 결측 존재")

    if any(orphan_counts.values()):
        errors.append("관계 테이블 orphan 존재")

    if invalid_providers:
        errors.append("대상 외 Provider 존재")

    if contents_without_provider:
        errors.append("Provider 없는 contents 존재")

    if plan_duplicates:
        errors.append("요금제 복합키 중복 존재")

    if sum(plan_missing.values()):
        errors.append("요금제 결측 존재")

    if invalid_plan_provider:
        errors.append("대상 외 요금제 Provider 존재")

    if invalid_prices:
        errors.append("잘못된 요금제 가격 존재")

    if invalid_streams:
        errors.append("잘못된 동시접속 수 존재")

    if invalid_ads:
        errors.append("잘못된 ads 값 존재")

    if bundle_duplicates:
        errors.append("bundle_id 중복 존재")

    if bundle_provider_duplicates:
        errors.append("Bundle-Provider 중복 존재")

    if unknown_bundle_ids:
        errors.append("잘못된 bundle_id 참조 존재")

    if bundles_without_provider:
        errors.append("Provider 관계 없는 번들 존재")

    if invalid_bundle_providers:
        errors.append("대상 외 Bundle Provider 존재")

    if providers_without_plan:
        errors.append("요금제가 없는 Bundle Provider 존재")

    if errors:
        print("FAIL")

        for error in errors:
            print("-", error)
    else:
        print("PASS")
        print("모든 processed 데이터 검증을 통과했습니다.")

    print("=" * 60)


if __name__ == "__main__":
    main()