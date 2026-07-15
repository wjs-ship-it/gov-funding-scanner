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
MSS_BASE = "https://www.mss.go.kr/site/smba/ex/bbs/List.do"
KISED_BASE = "https://www.kised.or.kr/board.es"
KOTRA_BASE = "https://www.kotra.or.kr"
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
# 중소벤처기업부 크롤러
# <tbody> 안의 <tr> 행 파싱. td 순서: 번호, 제목, 담당부서, 첨부, 등록일, 조회
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _parse_mss_list(html):
    items = []
    tbody_m = re.search(r"<tbody>(.*?)</tbody>", html, re.DOTALL)
    if not tbody_m:
        return items
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tbody_m.group(1), re.DOTALL)
    for row in rows:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(tds) < 5:
            continue
        seq = _strip(re.sub(r"<[^>]+>", "", tds[0]))
        if not seq.isdigit():
            continue
        title = _strip(re.sub(r"<[^>]+>", "", tds[1]))
        title = htmllib.unescape(title)
        dept = _strip(re.sub(r"<[^>]+>", "", tds[2]))
        date = _strip(re.sub(r"<[^>]+>", "", tds[4]))
        date = date.replace(".", "-") if date else ""

        links = re.findall(r"bcIdx=(\d+)", row)
        bc_idx = links[0] if links else seq
        url = f"https://www.mss.go.kr/site/smba/ex/bbs/View.do?cbIdx=86&bcIdx={bc_idx}"

        items.append({
            "source": "mss",
            "id": seq,
            "category": "",
            "dday": "",
            "title": title,
            "program": "",
            "org": f"중소벤처기업부 {dept}",
            "start": "",
            "deadline": "",
            "url": url,
        })
    return items


def scan_mss(fetch, max_pages=5):
    all_items = []
    seen_ids = set()
    for page in range(1, max_pages + 1):
        url = f"{MSS_BASE}?cbIdx=86&pageIndex={page}"
        status, html = fetch(url)
        if status != 200:
            print(f"  [mss] page {page}: HTTP {status} — 중단", file=sys.stderr)
            break
        items = _parse_mss_list(html)
        if not items:
            break
        new = 0
        for it in items:
            if it["id"] not in seen_ids:
                seen_ids.add(it["id"])
                all_items.append(it)
                new += 1
        print(f"  [mss] page {page}: {new}건 수집 (누적 {len(all_items)})", file=sys.stderr)
        if new == 0:
            break
        time.sleep(DELAY)
    return all_items


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 창업진흥원 크롤러
# div.tstyle_list 안의 ul/li 파싱. 보도자료 게시판 (사업공고는 K-Startup에 게재)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _parse_kised_list(html):
    items = []
    list_m = re.search(r'id="listView"', html)
    if not list_m:
        return items
    section = html[list_m.start():list_m.start() + 50000]
    paging_m = re.search(r'class="[^"]*paging', section)
    if paging_m:
        section = section[:paging_m.start()]

    for ul_m in re.finditer(r"<ul>(.*?)</ul>", section, re.DOTALL):
        ul = ul_m.group(1)
        lis = re.findall(r"<li[^>]*>(.*?)</li>", ul, re.DOTALL)
        if len(lis) < 4:
            continue

        seq = _strip(re.sub(r"<[^>]+>", "", lis[0]))
        if not seq.isdigit():
            continue

        link_m = re.search(r'href="([^"]+)"', lis[1])
        href = htmllib.unescape(link_m.group(1)) if link_m else ""
        title_m = re.search(r'title="([^"]+)"', lis[1])
        title = htmllib.unescape(title_m.group(1)) if title_m else ""
        if not title:
            title = _strip(re.sub(r"<[^>]+>", "", lis[1]))
            title = htmllib.unescape(title)

        author = _strip(re.sub(r"<[^>]+>", "", lis[2]))
        date = _strip(re.sub(r"<[^>]+>", "", lis[3]))

        url = f"https://www.kised.or.kr{href}" if href and not href.startswith("http") else href

        items.append({
            "source": "kised",
            "id": seq,
            "category": "",
            "dday": "",
            "title": title,
            "program": "",
            "org": f"창업진흥원 {author}",
            "start": "",
            "deadline": "",
            "url": url,
        })
    return items


def scan_kised(fetch, max_pages=5):
    all_items = []
    seen_ids = set()
    for page in range(1, max_pages + 1):
        url = f"{KISED_BASE}?mid=a10305000000&bid=0006&act=list&nPage={page}"
        status, html = fetch(url)
        if status != 200:
            print(f"  [kised] page {page}: HTTP {status} — 중단", file=sys.stderr)
            break
        items = _parse_kised_list(html)
        if not items:
            break
        new = 0
        for it in items:
            if it["id"] not in seen_ids:
                seen_ids.add(it["id"])
                all_items.append(it)
                new += 1
        print(f"  [kised] page {page}: {new}건 수집 (누적 {len(all_items)})", file=sys.stderr)
        if new == 0:
            break
        time.sleep(DELAY)
    return all_items


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# KOTRA 크롤러
# 사업신청 페이지의 AJAX 응답 파싱. curl_cffi 필수 (세션 쿠키 필요).
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _parse_kotra_ajax(html):
    items = []
    for m in re.finditer(
        r'<a[^>]*class=["\']card-tit["\'][^>]*href=["\']javascript:fn_selectBizMntInfoDetailNew\(["\']([^"\']+)',
        html,
    ):
        detail_url = m.group(1)
        biz_no_m = re.search(r"dtlBizMntNo=([^&\"']+)", detail_url)
        biz_id = biz_no_m.group(1) if biz_no_m else ""

        end_idx = html.find("</a>", m.end())
        raw_title = html[m.end():end_idx] if end_idx > 0 else ""
        title = _strip(re.sub(r"<[^>]+>", "", raw_title))
        title = re.sub(r"^['\");>\\s]+", "", title)
        title = htmllib.unescape(title)

        block = html[m.end():m.end() + 2000]
        dept_m = re.search(r"주관부서\s*</dt>\s*<dd[^>]*>(.*?)</dd>", block, re.DOTALL)
        dept = _strip(re.sub(r"<[^>]+>", "", dept_m.group(1))) if dept_m else ""
        period_m = re.search(r"모집기간\s*</dt>\s*<dd[^>]*>(.*?)</dd>", block, re.DOTALL)
        period = _strip(re.sub(r"<[^>]+>", "", period_m.group(1))) if period_m else ""

        start, deadline = "", ""
        if period:
            date_m = re.search(r"(\d{4}[./]\d{2}[./]\d{2})\s*~\s*(\d{4}[./]\d{2}[./]\d{2})", period)
            if date_m:
                start = date_m.group(1).replace("/", "-").replace(".", "-")
                deadline = date_m.group(2).replace("/", "-").replace(".", "-")

        full_url = f"{KOTRA_BASE}{detail_url}" if detail_url.startswith("/") else detail_url

        items.append({
            "source": "kotra",
            "id": biz_id,
            "category": "",
            "dday": "",
            "title": title,
            "program": "",
            "org": f"KOTRA {dept}",
            "start": start,
            "deadline": deadline,
            "url": full_url,
        })
    return items


def scan_kotra(fetch, max_pages=5):
    all_items = []
    seen_ids = set()

    biz_page_url = f"{KOTRA_BASE}/subList/20000020753.do"
    status, page_html = fetch(biz_page_url)
    if status != 200:
        print(f"  [kotra] 사업신청 페이지 로드 실패: HTTP {status}", file=sys.stderr)
        return all_items

    form_m = re.search(
        r"<form[^>]*(?:id|name)=[\"']searchDtlFrm[\"'][^>]*>(.*?)</form>",
        page_html,
        re.DOTALL,
    )
    if not form_m:
        print("  [kotra] searchDtlFrm 폼을 찾을 수 없음", file=sys.stderr)
        return all_items

    inputs = re.findall(
        r"<input[^>]*name=[\"']([^\"'>]+)[\"'][^>]*value=[\"']([^\"'>]*)[\"']",
        form_m.group(1),
    )
    params = {k: v for k, v in inputs}
    params["pageSize"] = "100"
    params["listCount"] = "100"

    ajax_url = f"{KOTRA_BASE}/module/subhome/bizAply/selectBmBizAllListAjax.do"
    for page in range(1, max_pages + 1):
        params["pageNo"] = str(page)
        status, ajax_html = fetch(ajax_url, method="POST", data=params)
        if status != 200:
            print(f"  [kotra] page {page}: HTTP {status} — 중단", file=sys.stderr)
            break
        items = _parse_kotra_ajax(ajax_html)
        if not items:
            break
        new = 0
        for it in items:
            if it["id"] not in seen_ids:
                seen_ids.add(it["id"])
                all_items.append(it)
                new += 1
        print(f"  [kotra] page {page}: {new}건 수집 (누적 {len(all_items)})", file=sys.stderr)
        if new == 0:
            break
        time.sleep(DELAY)
    return all_items


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 판판대로(소상공인24) 크롤러
# SPA + NetFunnel 대기열 → Playwright 필수. 네트워크 인터셉트로 JSON 직접 수집.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SBIZ24_URL = "https://www.sbiz24.kr/#/pbanc"
SBIZ24_API = "https://www.sbiz24.kr/api/pbanc/sbiz24PbancList"

_SBIZ24_PAYLOAD = {
    "sortModel": [],
    "search": {
        "searchValue": "", "rcrtTypeCdNmList": [],
        "rcrtTypeCdNmListDisplay": "", "regionNmList": [],
        "regionNmListDisplay": "", "tpbizCdList": [],
        "tpbizCdListDisplay": "",
        "bhis": {"from": None, "to": None},
        "wrkr": {"from": None, "to": None},
        "sls": {"from": None, "to": None},
        "aplySeYn": "N", "sbrPbancYn": "N", "itrstPbancYn": "N",
        "departNmList": None, "searchBox": None,
        "departNmListDisplay": "소상공인시장진흥공단",
        "ptPbancSortBy": None, "pbancNm": "", "regionCdList": [],
    },
    "paging": True, "startRow": 0, "endRow": 50,
}


def scan_sbiz24(fetch=None, max_pages=50):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [sbiz24] playwright 미설치 — pip install playwright && playwright install chromium", file=sys.stderr)
        return []

    all_items = []
    seen_ids = set()
    collected = []

    def _on_response(response):
        if SBIZ24_API in response.url and response.status == 200:
            try:
                collected.append(response.json())
            except Exception:
                pass

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.on("response", _on_response)

        page.goto(SBIZ24_URL, timeout=30000)
        page.wait_for_timeout(6000)

        if not collected:
            print("  [sbiz24] 첫 페이지 응답 없음", file=sys.stderr)
            browser.close()
            return all_items

        body = collected[-1]
        default = body.get("data", {}).get("default", {})
        total = default.get("total", 0)
        items_list = default.get("list", [])
        total_pages = default.get("page", {}).get("totalPages", 1)

        for it in items_list:
            _add_sbiz24_item(it, all_items, seen_ids)
        print(f"  [sbiz24] page 1/{total_pages}: {len(items_list)}건 (누적 {len(all_items)}, 전체 {total}건)", file=sys.stderr)

        pages_to_fetch = min(max_pages, total_pages)
        for pg_num in range(2, pages_to_fetch + 1):
            collected.clear()
            next_btns = page.query_selector_all("button.page-link")
            if len(next_btns) < 13:
                break
            next_btn = next_btns[12]
            if "disabled" in (next_btn.get_attribute("class") or ""):
                break
            next_btn.click()
            page.wait_for_timeout(3000)

            if not collected:
                print(f"  [sbiz24] page {pg_num}: 응답 없음 — 중단", file=sys.stderr)
                break

            items_list = collected[-1].get("data", {}).get("default", {}).get("list", [])
            if not items_list:
                break
            new = 0
            for it in items_list:
                if _add_sbiz24_item(it, all_items, seen_ids):
                    new += 1
            if pg_num % 10 == 0 or pg_num == pages_to_fetch:
                print(f"  [sbiz24] page {pg_num}/{total_pages}: 누적 {len(all_items)}건", file=sys.stderr)
            if new == 0:
                break

        browser.close()
    print(f"  [sbiz24] 완료: {len(all_items)}건 수집", file=sys.stderr)
    return all_items


def _add_sbiz24_item(it, all_items, seen_ids):
    pbanc_sn = str(it.get("pbancSn", ""))
    if not pbanc_sn or pbanc_sn in seen_ids:
        return False
    seen_ids.add(pbanc_sn)

    biz_pd = it.get("bizPd") or {}
    rcpt_pd = it.get("rcptPd") or {}
    start = (biz_pd.get("from") or "")[:10]
    deadline_raw = rcpt_pd.get("to") or ""
    deadline = deadline_raw[:10] if deadline_raw else ""

    all_items.append({
        "source": "sbiz24",
        "id": pbanc_sn,
        "category": "",
        "dday": "",
        "title": it.get("pbancNm", ""),
        "program": "",
        "org": "소상공인시장진흥공단",
        "start": start,
        "deadline": deadline,
        "url": f"https://www.sbiz24.kr/#/pbanc/{pbanc_sn}",
    })
    return True


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

    p_mss = sub.add_parser("mss", help="중소벤처기업부 공고 수집")
    p_mss.add_argument("-o", "--output", default="mss.jsonl")
    p_mss.add_argument("--max-pages", type=int, default=5)

    p_kised = sub.add_parser("kised", help="창업진흥원 보도자료 수집")
    p_kised.add_argument("-o", "--output", default="kised.jsonl")
    p_kised.add_argument("--max-pages", type=int, default=5)

    p_kotra = sub.add_parser("kotra", help="KOTRA 사업공고 수집")
    p_kotra.add_argument("-o", "--output", default="kotra.jsonl")
    p_kotra.add_argument("--max-pages", type=int, default=5)

    p_sbiz = sub.add_parser("sbiz24", help="판판대로(소상공인24) 공고 수집")
    p_sbiz.add_argument("-o", "--output", default="sbiz24.jsonl")
    p_sbiz.add_argument("--max-pages", type=int, default=10)

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

    if args.cmd in ("kstartup", "bizinfo", "mss", "kised", "kotra", "sbiz24", "all"):
        items = []
        if args.cmd in ("kstartup", "all"):
            items.extend(scan_kstartup(fetch, args.max_pages))
        if args.cmd in ("bizinfo", "all"):
            items.extend(scan_bizinfo(fetch, args.max_pages))
        if args.cmd in ("mss", "all"):
            items.extend(scan_mss(fetch, getattr(args, "max_pages", 5)))
        if args.cmd in ("kised", "all"):
            items.extend(scan_kised(fetch, getattr(args, "max_pages", 5)))
        if args.cmd in ("kotra", "all"):
            items.extend(scan_kotra(fetch, getattr(args, "max_pages", 5)))
        if args.cmd in ("sbiz24", "all"):
            items.extend(scan_sbiz24(max_pages=getattr(args, "max_pages", 10)))

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
