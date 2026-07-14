#!/usr/bin/env python3
"""정부 지원사업 알리미.

매일 cron으로 실행: 크롤링 → 이전 데이터와 diff → 신규 공고만 디스코드 전송.
  python3 alert.py
"""
import json
import os
import sys
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")
PREV_FILE = os.path.join(DATA_DIR, "previous.jsonl")

DISCORD_CHANNEL_ID = "1526403743300714579"

sys.path.insert(0, SCRIPT_DIR)
from scanner import scan_kstartup, scan_bizinfo, _make_session


def load_previous_ids():
    if not os.path.exists(PREV_FILE):
        return set()
    ids = set()
    with open(PREV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            ids.add(f"{item['source']}:{item['id']}")
    return ids


def save_current(items):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PREV_FILE, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def _load_discord_token():
    settings_path = os.path.expanduser("~/.cli-jaw/settings.json")
    with open(settings_path, "r") as f:
        return json.load(f)["discord"]["token"]


def send_discord(message, token=None):
    if token is None:
        token = _load_discord_token()

    url = f"https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages"
    payload = json.dumps({"content": message}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", f"Bot {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Content-Length", str(len(payload)))
    req.add_header("User-Agent", "GovFundingAlert/1.0")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[alert] Discord 전송 실패: {e}", file=sys.stderr)
        return False


def format_item(item):
    source = "K-Startup" if item["source"] == "kstartup" else "기업마당"
    deadline = item.get("deadline", "")
    deadline_str = f" | 마감: {deadline}" if deadline else ""
    category = item.get("category", "")
    cat_str = f"[{category}] " if category else ""
    org = item.get("org", "")
    org_str = f"\n   주관: {org}" if org else ""

    return (
        f"📢 **{cat_str}{item['title']}**\n"
        f"   출처: {source}{deadline_str}{org_str}\n"
        f"   🔗 {item['url']}"
    )


def main():
    print("[alert] 크롤링 시작...", file=sys.stderr)
    fetch, backend = _make_session()
    print(f"[alert] backend: {backend}", file=sys.stderr)

    items = []
    items.extend(scan_kstartup(fetch, max_pages=30))
    items.extend(scan_bizinfo(fetch, max_pages=15))
    print(f"[alert] 총 {len(items)}건 수집", file=sys.stderr)

    first_run = not os.path.exists(PREV_FILE)
    prev_ids = load_previous_ids()
    new_items = [
        it for it in items
        if f"{it['source']}:{it['id']}" not in prev_ids
    ]

    save_current(items)

    if first_run:
        print(f"[alert] 첫 실행 — {len(items)}건 기준 데이터 저장 (알림 생략)", file=sys.stderr)
        return

    if not new_items:
        print("[alert] 신규 공고 없음", file=sys.stderr)
        return

    print(f"[alert] 신규 {len(new_items)}건 발견!", file=sys.stderr)

    token = _load_discord_token()
    header = f"🔔 **정부 지원사업 신규 공고 {len(new_items)}건**\n{'─' * 30}"
    send_discord(header, token)

    import time as _time
    for i, item in enumerate(new_items[:20]):
        msg = format_item(item)
        send_discord(msg, token)
        _time.sleep(0.5)

    if len(new_items) > 20:
        send_discord(f"... 외 {len(new_items) - 20}건", token)

    print(f"[alert] 디스코드 전송 완료 ({min(len(new_items), 20)}건)", file=sys.stderr)


if __name__ == "__main__":
    main()
