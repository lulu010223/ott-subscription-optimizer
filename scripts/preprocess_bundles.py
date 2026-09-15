import csv
from pathlib import Path

INPUT_PATH = Path("data/raw/ott_plans/ott_bundles_20260913.csv")

BUNDLES_OUTPUT = Path("data/processed/ott_bundles.csv")
PROVIDERS_OUTPUT = Path("data/processed/bundle_providers.csv")

BUNDLE_IDS = {
    "TVING × Wavve Double Ad-supported Standard": "tving_wavve_ad_standard",
    "TVING × Wavve Double Slim": "tving_wavve_slim",
    "TVING × Wavve Double Basic": "tving_wavve_basic",
    "TVING × Wavve Double Standard": "tving_wavve_standard",
    "TVING × Wavve Double Premium": "tving_wavve_premium",
    "Disney+ × TVING Bundle": "disney_tving",
    "Disney+ × TVING × Wavve Bundle": "disney_tving_wavve",
}


def main():
    BUNDLES_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    bundles = []
    bundle_providers = []

    with INPUT_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            bundle_name = row["bundle_name"].strip()

            if bundle_name not in BUNDLE_IDS:
                raise ValueError(f"알 수 없는 bundle_name: {bundle_name}")

            bundle_id = BUNDLE_IDS[bundle_name]

            providers = [
                value.strip()
                for value in row["included_providers"].split("|")
            ]

            plan_tiers = [
                value.strip()
                for value in row["plan_tier"].split("|")
            ]

            # provider와 plan_tier가 반드시 1:1 대응해야 함
            if len(providers) != len(plan_tiers):
                raise ValueError(
                    f"{bundle_name}: provider와 plan_tier 개수가 다릅니다."
                )

            bundles.append({
                "bundle_id": bundle_id,
                "bundle_name": bundle_name,
                "monthly_price": int(row["monthly_price"]),
                "ads": row["ads"].strip().upper(),
                "collected_at": row["collected_at"].strip(),
            })

            for provider, plan_tier in zip(providers, plan_tiers):
                prefix = f"{provider} "

                if not plan_tier.startswith(prefix):
                  raise ValueError(
                    f"{bundle_name}: "
                    f"plan_tier '{plan_tier}'가 "
                    f"provider '{provider}'와 일치하지 않습니다."
                )

                plan_name = plan_tier[len(prefix):].strip()

                bundle_providers.append({
                    "bundle_id": bundle_id,
                    "provider": provider,
                    "plan_name": plan_name,
                })

    with BUNDLES_OUTPUT.open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "bundle_id",
                "bundle_name",
                "monthly_price",
                "ads",
                "collected_at",
            ],
        )
        writer.writeheader()
        writer.writerows(bundles)

    with PROVIDERS_OUTPUT.open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "bundle_id",
                "provider",
                "plan_name",
            ],
        )
        writer.writeheader()
        writer.writerows(bundle_providers)

    print("[OTT 번들 전처리 결과]")
    print("번들 수:", len(bundles))
    print("Bundle-Provider 관계 수:", len(bundle_providers))
    print("ott_bundles:", BUNDLES_OUTPUT)
    print("bundle_providers:", PROVIDERS_OUTPUT)


if __name__ == "__main__":
    main()