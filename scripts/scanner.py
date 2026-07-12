#!/usr/bin/env python3
"""정부 지원사업 스캐너.

K-Startup과 기업마당에서 모집중인 공고를 자동으로 긁어옵니다.
결과는 JSONL(한 줄에 공고 하나)로 저장됩니다.

사용법:
  python3 scanner.py kstartup -o results/kstartup.jsonl
  python3 scanner.py bizinfo -o results/bizinfo.jsonl
  python3 scanner.py all -o results/all.jsonl
  python3 scanner.py detail 178499 -o details/
"""
import argparse
import html as htmllib
import json
import os
import re
import sys
import time

KSTARTUP_BASE = "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do"
BIZINFO_BASE = "https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/list.do"
DELAY = 0.4  # 서버 부담 줄이려고 요청 사이에 쉬는 시간(초)


def _make_session():
    """HTTP 요청 도구를 만든다. curl_cffi가 있으면 그걸 쓰고, 없으면 기본 urllib로."""
    try:
        from curl_cffi import requests as cr
        # Safari인 척 해야 K-Startup이 안 막음
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
    """공백/줄바꿈을 하나로 합쳐서 깔끔한 한 줄 텍스트로."""
    return re.sub(r"\s+", " ", text).strip() if text else ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# K-Startup 크롤러
# 페이지당 15건, ?page=N으로 넘김, HTML 안의 리스트를 직접 파싱
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _parse_kstartup_list(html):
    """K-Startup 목록 페이지 HTML에서 공고 정보를 뽑아낸다."""
    items = []

    # 페이지 상단 캐러셀(추천 공고)은 건너뛰고, 진짜 목록만 가져옴
    parts = html.split('id="bizPbancList"', 1)
    if len(parts) < 2:
        return items
    body = parts[1].split("</ul>", 1)[0] if "</ul>" in parts[1] else parts[1][:50000]

    # 각 <li>가 공고 하나
    for blk in re.split(r"<li\b[^>]*>", body)[1:]:
        # go_view(공고번호)로 상세페이지 이동하는 JS가 있음
        m = re.search(r"go_view\((\d+)\)", blk)
        if not m:
            continue
        sn = m.group(1)

        # 블록 안에서 특정 패턴 찾는 헬퍼
        def g(pat):
            mm = re.search(pat, blk)
            return _strip(htmllib.unescape(mm.group(1))) if mm else ""

        # "시작일자 2026-07-01" 같은 span 태그들
        spans = [
            _strip(htmllib.unescape(x))
            for x in re.findall(r'<span class="list"><i[^>]*></i>([^<]+)</span>', blk)
        ]

        # spans에서 "시작일자", "마감일자" 같은 접두어로 값 꺼내기
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
    """K-Startup 모집중 공고를 페이지 넘기면서 전부 수집한다."""
    all_items = []
    seen_ids = set()  # 같은 공고 중복 방지용
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
        # 새로운 게 0이면 마지막 페이지를 넘은 것
        if new == 0:
            break
        time.sleep(DELAY)
    return all_items


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 기업마당 크롤러
# <tbody> 안의 <tr> 행을 파싱. td 순서: 번호, 분야, 제목, 기간, 주관부처, 수행기관...
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _parse_bizinfo_list(html):
    """기업마당 목록 페이지 HTML에서 공고 정보를 뽑아낸다."""
    items = []
    tbody = html.split("<tbody")[1] if "<tbody" in html else ""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tbody, re.DOTALL)
    for row in rows:
        # 각 칸의 HTML 태그 벗기고 텍스트만
        tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        cleaned = [_strip(re.sub(r"<[^>]+>", "", td)) for td in tds]
        if len(cleaned) < 6:
            continue

        seq = cleaned[0]       # 공고 번호
        category = cleaned[1]  # 분야 (수출, 기술, 경영 등)
        title = cleaned[2]     # 공고 제목
        date_range = cleaned[3]  # "2026-07-07 ~ 2026-07-17" 형태
        org_main = cleaned[4]  # 주관부처
        org_sub = cleaned[5] if len(cleaned) > 5 else ""  # 수행기관

        # 날짜 범위에서 시작일/마감일 분리
        m_date = re.search(r"(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})", date_range)
        start = m_date.group(1) if m_date else ""
        deadline = m_date.group(2) if m_date else ""

        # 상세페이지 링크 추출
        m_link = re.search(r'<a[^>]*href=["\s]*([^">\s]+)', row)
        href = m_link.group(1).strip() if m_link else ""
        if href and not href.startswith("http"):
            href = "https://www.bizinfo.go.kr" + href
        if not href:
            # 링크가 없으면 번호로 URL 직접 조립
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
    """기업마당 공고를 페이지 넘기면서 전부 수집한다."""
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 상세 페이지 — 자격요건 확인할 때 쓰는 기능
# HTML에서 태그 다 벗기고 순수 텍스트만 저장
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def fetch_detail(fetch, url_or_id, output_dir):
    """공고 상세페이지를 텍스트로 변환해서 파일로 저장한다."""
    # 숫자만 들어오면 K-Startup 공고번호로 간주
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

    # HTML → 순수 텍스트: 스크립트/스타일 제거 → 태그를 줄바꿈으로 → 빈줄 정리
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CLI — 터미널에서 바로 실행하는 진입점
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
