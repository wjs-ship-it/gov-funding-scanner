#!/usr/bin/env python3
"""정부 지원사업 스캐너 — K-Startup + 기업마당 공고 수집기.

공개 페이지만 접근하며 요청 간 딜레이를 둡니다.

Usage:
  python3 scanner.py kstartup -o results/kstartup.jsonl
  python3 scanner.py bizinfo -o results/bizinfo.jsonl
  python3 scanner.py all -o results/all.jsonl
  python3 scanner.py detail <url_or_id> -o details/
"""
import argparse
import html as htmllib
import json
import os
import re
import sys
import time
from pathlib import Path

KSTARTUP_BASE = "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do"
BIZINFO_BASE = "https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/list.do"
DELAY = 0.4


def _make_session():
    try:
        from curl_cffi import requests as cr
        sess = cr.Session(impersonate="safari")

        def fetch(url, method="GET", data=None):
            if method == "POST":
                r = sess.post(url, data=data, timeout=30)
            else:
                r = sess.get(url, timeout=30)
            return r.status_code, r.text

        return fetch, "curl_cffi"
    except ImportError:
        import urllib.request
        import urllib.parse

        def fetch(url, method="GET", data=None):
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15"
                )
            }
            if method == "POST" and data:
                body = urllib.parse.urlencode(data).encode()
                req = urllib.request.Request(url, data=body, headers=headers)
            else:
                req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, resp.read().decode("utf-8", "replace")

        return fetch, "urllib"


def _strip(text):
    return re.sub(r"\s+", " ", text).strip() if text else ""


# ─── K-Startup ───────────────────────────────────────────────────────────────

def _parse_kstartup_list(html):
    items = []
    parts = html.split('id="bizPbancList"', 1)
    if len(parts) < 2:
        return items
    body = parts[1].split("</ul>", 1)[0] if "</ul>" in parts[1] else parts[1][:50000]

    for blk in re.split(r"<li\b[^>]*>", body)[1:]:
        m = re.search(r"go_view\((\d+)\)", blk)
        if not m:
            continue
        sn = m.group(1)

        def g(pat):
            mm = re.search(pat, blk)
            return _strip(htmllib.unescape(mm.group(1))) if mm else ""

        spans = [
            _strip(htmllib.unescape(x))
            for x in re.findall(r'<span class="list"><i[^>]*></i>([^<]+)</span>', blk)
        ]

        def pick(prefix):
            for x in spans:
                if x.startswith(prefix):
                    return x.replace(prefix, "").strip()
            return ""

        items.append({
            "source": "kstartup",
            "id": sn,
            "category": g(r'<span class="flag type\d+">\s*([^<]+)</span>'),
            "dday": g(r'<span class="flag day">\s*([^<]+)</span>'),
            "title": g(r'<p class="tit">\s*([^<]+)'),
            "program": spans[0] if spans else "",
            "org": spans[1] if len(spans) > 1 else "",
            "start": pick("시작일자"),
            "deadline": pick("마감일자"),
            "url": f"{KSTARTUP_BASE}?schM=view&pbancSn={sn}",
        })
    return items


def scan_kstartup(fetch, max_pages=30):
    all_items = []
    seen_ids = set()
    for page in range(1, max_pages + 1):
        url = f"{KSTARTUP_BASE}?page={page}&schStr=&pbancEndYn=N"
        status, html = fetch(url)
        if status != 200:
            print(f"  [kstartup] page {page}: HTTP {status} — 중단", file=sys.stderr)
            break
        items = _parse_kstartup_list(html)
        if not items:
            break
        new = 0
        for it in items:
            if it["id"] not in seen_ids:
                seen_ids.add(it["id"])
                all_items.append(it)
                new += 1
        print(f"  [kstartup] page {page}: {new}건 수집 (누적 {len(all_items)})", file=sys.stderr)
        if new == 0:
            break
        time.sleep(DELAY)
    return all_items


# ─── 기업마당 (bizinfo) ──────────────────────────────────────────────────────

def _parse_bizinfo_list(html):
    items = []
    tbody = html.split("<tbody")[1] if "<tbody" in html else ""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tbody, re.DOTALL)
    for row in rows:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        cleaned = [_strip(re.sub(r"<[^>]+>", "", td)) for td in tds]
        if len(cleaned) < 6:
            continue
        seq = cleaned[0]
        category = cleaned[1]
        title = cleaned[2]
        date_range = cleaned[3]
        org_main = cleaned[4]
        org_sub = cleaned[5] if len(cleaned) > 5 else ""

        m_date = re.search(r"(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})", date_range)
        start = m_date.group(1) if m_date else ""
        deadline = m_date.group(2) if m_date else ""

        m_link = re.search(r'<a[^>]*href=["\s]*([^">\s]+)', row)
        href = m_link.group(1).strip() if m_link else ""
        if href and not href.startswith("http"):
            href = "https://www.bizinfo.go.kr" + href
        if not href:
            href = f"https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?seq={seq}"

        items.append({
            "source": "bizinfo",
            "id": seq,
            "category": category,
            "dday": "",
            "title": title,
            "program": "",
            "org": f"{org_main} / {org_sub}" if org_sub else org_main,
            "start": start,
            "deadline": deadline,
            "url": href,
        })
    return items


def scan_bizinfo(fetch, max_pages=15):
    all_items = []
    seen_ids = set()
    for page in range(1, max_pages + 1):
        url = f"{BIZINFO_BASE}?rows=20&cPage={page}"
        status, html = fetch(url)
        if status != 200:
            print(f"  [bizinfo] page {page}: HTTP {status} — 중단", file=sys.stderr)
            break
        items = _parse_bizinfo_list(html)
        if not items:
            break
        new = 0
        for it in items:
            if it["id"] not in seen_ids:
                seen_ids.add(it["id"])
                all_items.append(it)
                new += 1
        print(f"  [bizinfo] page {page}: {new}건 수집 (누적 {len(all_items)})", file=sys.stderr)
        if new == 0:
            break
        time.sleep(DELAY)
    return all_items


# ─── 상세 페이지 ─────────────────────────────────────────────────────────────

def fetch_detail(fetch, url_or_id, output_dir):
    if url_or_id.isdigit():
        url = f"{KSTARTUP_BASE}?schM=view&pbancSn={url_or_id}"
        fname = f"kstartup_{url_or_id}.txt"
    else:
        url = url_or_id
        fname = re.sub(r'[^a-zA-Z0-9가-힣_-]', '_', url.split('/')[-1])[:80] + ".txt"

    status, html = fetch(url)
    if status != 200:
        print(f"  [detail] {url}: HTTP {status}", file=sys.stderr)
        return None

    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '\n', text)
    text = htmllib.unescape(text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, fname)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text.strip())
    print(f"  [detail] 저장: {out_path}", file=sys.stderr)
    return out_path


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="정부 지원사업 스캐너")
    sub = parser.add_subparsers(dest="cmd")

    p_list = sub.add_parser("kstartup", help="K-Startup 모집중 공고 수집")
    p_list.add_argument("-o", "--output", default="kstartup.jsonl")
    p_list.add_argument("--max-pages", type=int, default=30)

    p_biz = sub.add_parser("bizinfo", help="기업마당 공고 수집")
    p_biz.add_argument("-o", "--output", default="bizinfo.jsonl")
    p_biz.add_argument("--max-pages", type=int, default=15)

    p_all = sub.add_parser("all", help="전체 소스 수집")
    p_all.add_argument("-o", "--output", default="all.jsonl")
    p_all.add_argument("--max-pages", type=int, default=30)

    p_det = sub.add_parser("detail", help="상세 페이지 텍스트 추출")
    p_det.add_argument("targets", nargs="+", help="공고번호 또는 URL")
    p_det.add_argument("-o", "--output", default="details/")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    fetch, backend = _make_session()
    print(f"[scanner] backend: {backend}", file=sys.stderr)

    if args.cmd in ("kstartup", "bizinfo", "all"):
        items = []
        if args.cmd in ("kstartup", "all"):
            items.extend(scan_kstartup(fetch, args.max_pages))
        if args.cmd in ("bizinfo", "all"):
            items.extend(scan_bizinfo(fetch, args.max_pages))

        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            for it in items:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
        print(f"\n[scanner] 완료: {len(items)}건 → {args.output}", file=sys.stderr)

    elif args.cmd == "detail":
        for target in args.targets:
            fetch_detail(fetch, target, args.output)
            time.sleep(DELAY)


if __name__ == "__main__":
    main()
