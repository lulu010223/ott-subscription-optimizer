import json
import time
from pathlib import Path
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
import os

load_dotenv()

TMDB_ACCESS_TOKEN = os.getenv("TMDB_ACCESS_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {TMDB_ACCESS_TOKEN}",
    "accept": "application/json",
}

DETAILS_ROOT = Path("data/raw/details")

failed_files = list(DETAILS_ROOT.rglob("failed_contents.json"))

if not failed_files:
    raise FileNotFoundError("failed_contents.json을 찾을 수 없습니다.")

FAILED_FILE = failed_files[0]
OUTPUT_DIR = FAILED_FILE.parent

RETRY_SUCCESS_FILE = OUTPUT_DIR / "retry_success.json"
RETRY_FAILED_FILE = OUTPUT_DIR / "retry_failed.json"


def fetch_detail(item):
    tmdb_id = item["tmdb_id"]
    media_type = item["media_type"]

    url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}"

    params = {
        "language": "ko-KR",
        "append_to_response": "keywords,watch/providers",
    }

    response = requests.get(
        url,
        headers=HEADERS,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    return {
        "tmdb_id": tmdb_id,
        "media_type": media_type,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "raw_response": response.json(),
    }


with open(FAILED_FILE, "r", encoding="utf-8") as f:
    failed_items = json.load(f)

print(f"재수집 대상: {len(failed_items)}건\n")

success = []
failed = []

for index, item in enumerate(failed_items, start=1):

    print(
        f"[{index}/{len(failed_items)}] "
        f"{item['media_type'].upper()} "
        f"{item['tmdb_id']} "
        f"{item.get('title', '')}"
    )

    try:
        result = fetch_detail(item)
        success.append(result)

        print("  ✅ 성공")

    except Exception as e:

        failed.append({
            "tmdb_id": item["tmdb_id"],
            "media_type": item["media_type"],
            "title": item.get("title"),
            "error_type": type(e).__name__,
            "error_message": str(e),
            "failed_at": datetime.now(timezone.utc).isoformat(),
        })

        print(f"  ❌ 실패: {e}")

    time.sleep(0.25)


with open(RETRY_SUCCESS_FILE, "w", encoding="utf-8") as f:
    json.dump(success, f, ensure_ascii=False, indent=2)

with open(RETRY_FAILED_FILE, "w", encoding="utf-8") as f:
    json.dump(failed, f, ensure_ascii=False, indent=2)


print("\n==============================")
print("재수집 완료")
print("==============================")
print(f"성공: {len(success)}")
print(f"실패: {len(failed)}")
print(f"성공 파일: {RETRY_SUCCESS_FILE}")
print(f"실패 파일: {RETRY_FAILED_FILE}")