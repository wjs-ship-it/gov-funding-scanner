#!/usr/bin/env python3
"""카카오톡 지원사업 알리미 봇.

카카오 i 오픈빌더 스킬 서버. 사용자가 카톡으로 키워드를 보내면
크롤링 데이터에서 맞춤 공고를 골라 응답한다.

키워드 예시:
  "새 공고" → 전체 최신 공고
  "르브아제" → 화장품 판매/마케팅/수출 관련
  "복센트" → 화장품 제조/소공인/기술 관련
  "서울" / "경기" → 지역 필터
"""
import json
import os
import re
import sys
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_FILE = os.path.join(PROJECT_DIR, "data", "previous.jsonl")


def load_items():
    if not os.path.exists(DATA_FILE):
        return []
    items = []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


REVOIRZE_KEYWORDS = [
    "화장품", "뷰티", "beauty", "cosmetic", "k-beauty",
    "판로", "판매", "유통", "이커머스", "입점",
    "해외진출", "수출", "글로벌", "해외판로",
    "마케팅", "브랜드", "홍보", "sns",
]

BOKSENT_KEYWORDS = [
    "화장품", "뷰티", "beauty", "cosmetic",
    "제조", "제조업", "생산", "공장", "gmp",
    "소공인", "스마트공방", "스마트제조", "클린제조",
    "기술개발", "r&d", "연구개발", "특허", "지식재산",
    "시설", "설비", "인증", "품질",
]

REGION_SEOUL = ["서울", "서초", "강남", "종로", "마포", "영등포", "성동", "송파", "강서", "동대문", "광진", "용산"]
REGION_GYEONGGI = ["경기", "수원", "성남", "고양", "용인", "안양", "안산", "부천", "화성", "평택", "시흥", "파주", "김포", "광명", "하남", "구리", "남양주", "의정부", "양주", "포천", "동두천", "과천", "오산", "군포", "의왕", "이천", "여주", "양평", "가평", "연천"]
OTHER_REGIONS = ["부산", "대구", "광주", "대전", "울산", "세종", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주", "인천"]

SOURCE_NAMES = {
    "kstartup": "K-Startup",
    "bizinfo": "기업마당",
    "kised": "창업진흥원",
    "kotra": "KOTRA",
    "sbiz24": "판판대로",
}


def is_expired(item):
    dl = item.get("deadline", "")
    if not dl:
        return False
    try:
        return datetime.strptime(dl, "%Y-%m-%d") < datetime.now()
    except ValueError:
        return False


def match_keywords(item, keywords):
    blob = json.dumps(item, ensure_ascii=False).lower()
    return sum(1 for k in keywords if k in blob)


def filter_region(items, region_keywords):
    results = []
    for it in items:
        blob = json.dumps(it, ensure_ascii=False)
        if any(k in blob for k in region_keywords):
            results.append(it)
        elif not any(k in blob for k in OTHER_REGIONS):
            results.append(it)
    return results


def format_item_kakao(item):
    src = SOURCE_NAMES.get(item["source"], item["source"])
    dl = item.get("deadline", "")
    dl_str = f" | 마감:{dl}" if dl else ""
    cat = item.get("category", "")
    cat_str = f"[{cat}] " if cat else ""
    org = item.get("org", "")
    org_str = f"\n주관: {org}" if org else ""
    return f"📢 {cat_str}{item['title']}\n출처: {src}{dl_str}{org_str}\n🔗 {item['url']}"


def search_items(query):
    items = load_items()
    items = [it for it in items if not is_expired(it)]
    query_lower = query.lower().strip()

    if "르브아제" in query_lower:
        scored = [(match_keywords(it, REVOIRZE_KEYWORDS), it) for it in items]
        scored = [(s, it) for s, it in scored if s >= 2]
        region_kw = REGION_SEOUL + REGION_GYEONGGI + ["전국", "온라인"]
        scored = [(s, it) for s, it in scored if any(k in json.dumps(it, ensure_ascii=False) for k in region_kw) or not any(k in json.dumps(it, ensure_ascii=False) for k in OTHER_REGIONS)]
        scored.sort(key=lambda x: -x[0])
        return [it for _, it in scored[:10]], "르브아제 맞춤"

    if "복센트" in query_lower:
        scored = [(match_keywords(it, BOKSENT_KEYWORDS), it) for it in items]
        scored = [(s, it) for s, it in scored if s >= 2]
        region_kw = REGION_GYEONGGI + ["전국", "온라인", "경기", "평택"]
        scored = [(s, it) for s, it in scored if any(k in json.dumps(it, ensure_ascii=False) for k in region_kw) or not any(k in json.dumps(it, ensure_ascii=False) for k in OTHER_REGIONS)]
        scored.sort(key=lambda x: -x[0])
        return [it for _, it in scored[:10]], "복센트 맞춤"

    if "서울" in query_lower:
        filtered = filter_region(items, REGION_SEOUL)
        filtered.sort(key=lambda it: it.get("deadline", "9999"))
        return filtered[:10], "서울 지역"

    if "경기" in query_lower:
        filtered = filter_region(items, REGION_GYEONGGI)
        filtered.sort(key=lambda it: it.get("deadline", "9999"))
        return filtered[:10], "경기 지역"

    # 기본: 마감 임박순 최신 공고
    items.sort(key=lambda it: it.get("deadline", "9999"))
    return items[:10], "최신"


@app.get("/")
async def home():
    return {"status": "ok", "message": "지원사업 알리미 봇 작동 중 🚀"}


@app.post("/api/funding")
async def funding_skill(request: Request):
    try:
        kakao_data = await request.json()
        utterance = kakao_data.get("userRequest", {}).get("utterance", "")

        if not utterance:
            utterance = "새 공고"

        results, label = search_items(utterance)

        if not results:
            text = "현재 조건에 맞는 공고가 없습니다. 다른 키워드로 검색해보세요.\n\n사용법:\n• 르브아제 — 화장품 판매 관련\n• 복센트 — 화장품 제조 관련\n• 서울 / 경기 — 지역별\n• 새 공고 — 전체 최신"
        else:
            header = f"🔔 {label} 공고 {len(results)}건\n{'─' * 20}\n\n"
            body = "\n\n".join(format_item_kakao(it) for it in results)
            footer = f"\n\n💡 키워드: 르브아제, 복센트, 서울, 경기"
            text = header + body + footer

        # 카카오톡 5000자 제한
        if len(text) > 4500:
            text = text[:4500] + "\n\n... (더 많은 공고는 웹에서 확인)"

        return {
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": text}}]
            }
        }
    except Exception as e:
        return {
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": f"오류가 발생했습니다: {str(e)}"}}]
            }
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
