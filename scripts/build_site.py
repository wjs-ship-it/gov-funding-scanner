#!/usr/bin/env python3
"""크롤링 데이터를 웹사이트용 JSON으로 변환."""
import json
import os
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_FILE = os.path.join(PROJECT_DIR, "data", "previous.jsonl")
PUBLIC_DIR = os.path.join(PROJECT_DIR, "public")
OUTPUT_FILE = os.path.join(PUBLIC_DIR, "data.json")

REGION_INCLUDE = {"서울", "경기", "수도권"}
REGION_EXCLUDE = {
    "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
    "충청북", "충청남", "전라북", "전라남", "경상북", "경상남",
}


def _matches_region(item):
    text = f"{item.get('title', '')} {item.get('org', '')} {item.get('category', '')} {item.get('program', '')}"
    if any(r in text for r in REGION_INCLUDE):
        return True
    if any(r in text for r in REGION_EXCLUDE):
        return False
    return True


def _is_active(item):
    deadline = item.get("deadline", "")
    if not deadline:
        return True
    try:
        return datetime.strptime(deadline, "%Y-%m-%d").date() >= datetime.now().date()
    except ValueError:
        return True


def main():
    if not os.path.exists(DATA_FILE):
        print(f"[build_site] {DATA_FILE} 없음", file=sys.stderr)
        return

    items = []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if _matches_region(item) and _is_active(item):
                items.append(item)

    items.sort(key=lambda x: x.get("deadline") or "9999-99-99")

    output = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": len(items),
        "items": items,
    }

    os.makedirs(PUBLIC_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[build_site] {len(items)}건 → {OUTPUT_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()
