import csv
from pathlib import Path

BUNDLE_PROVIDERS_PATH = Path("data/processed/bundle_providers.csv")
OTT_PLANS_PATH = Path("data/processed/ott_plans.csv")


def main():
    # bundle_providers 로드
    with BUNDLE_PROVIDERS_PATH.open(
        "r", encoding="utf-8-sig", newline=""
    ) as f:
        bundle_providers = list(csv.DictReader(f))

    # ott_plans 로드
    with OTT_PLANS_PATH.open(
        "r", encoding="utf-8-sig", newline=""
    ) as f:
        ott_plans = list(csv.DictReader(f))

    # ott_plans의 자연키
    plan_keys = {
        (row["provider"].strip(), row["plan_name"].strip())
        for row in ott_plans
    }

    # bundle_providers 복합키
    relation_keys = [
        (row["bundle_id"].strip(), row["provider"].strip())
        for row in bundle_providers
    ]

    # ott_plans에 존재하지 않는 (provider, plan_name)
    invalid_plan_refs = []

    for row in bundle_providers:
        key = (
            row["provider"].strip(),
            row["plan_name"].strip(),
        )

        if key not in plan_keys:
            invalid_plan_refs.append({
                "bundle_id": row["bundle_id"],
                "provider": row["provider"],
                "plan_name": row["plan_name"],
            })

    print("[Bundle-Provider 정규화 검증]")
    print("관계 수:", len(bundle_providers))
    print("복합키 중복:", len(relation_keys) - len(set(relation_keys)))
    print("ott_plans에 없는 요금제 참조:", len(invalid_plan_refs))

    if invalid_plan_refs:
        print("\n[잘못된 요금제 참조]")
        for row in invalid_plan_refs:
            print(
                f"- {row['bundle_id']} | "
                f"{row['provider']} | "
                f"{row['plan_name']}"
            )

    if (
        len(bundle_providers) == 15
        and len(relation_keys) == len(set(relation_keys))
        and not invalid_plan_refs
    ):
        print("\n[최종 판정]")
        print("PASS")
        print("모든 Bundle-Provider 관계가 ott_plans와 정상 연결됩니다.")
    else:
        print("\n[최종 판정]")
        print("FAIL")


if __name__ == "__main__":
    main()
    