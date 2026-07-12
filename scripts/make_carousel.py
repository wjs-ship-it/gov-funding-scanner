#!/usr/bin/env python3
"""정부 지원사업 스캐너 — 인스타 캐러셀 10장 생성기."""
import os
import textwrap
from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = os.path.expanduser("~/Projects/gov-funding-scanner/output/carousel")
W, H = 1080, 1350

# 색상
BG_DARK = "#0F1419"
BG_CARD = "#1A2332"
ACCENT = "#4ECDC4"
ACCENT2 = "#FF6B6B"
ACCENT3 = "#FFE66D"
WHITE = "#FFFFFF"
GRAY = "#8899AA"
LIGHT = "#E8F4F8"

# 폰트
FONT_BOLD = "/usr/share/fonts/truetype/nanum/NanumSquareB.ttf"
FONT_REG = "/usr/share/fonts/truetype/nanum/NanumSquareR.ttf"


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def new_card():
    return Image.new("RGB", (W, H), BG_DARK)


def draw_page_num(draw, page, total=10):
    draw.text((W - 80, 60), f"{page}/{total}", fill=GRAY, font=font(28))


def draw_header(draw, text, y=120):
    draw.text((80, y), text, fill=ACCENT, font=font(32, bold=True))


def draw_title(draw, text, y=180, color=WHITE, size=52):
    lines = textwrap.wrap(text, width=16)
    for i, line in enumerate(lines):
        draw.text((80, y + i * (size + 16)), line, fill=color, font=font(size, bold=True))
    return y + len(lines) * (size + 16)


def draw_body(draw, lines, y=400, size=36, color=LIGHT, spacing=20):
    for line in lines:
        wrapped = textwrap.wrap(line, width=22)
        for wl in wrapped:
            draw.text((80, y), wl, fill=color, font=font(size))
            y += size + spacing
        y += 10
    return y


def draw_box(draw, x, y, w, h, color=BG_CARD, radius=20):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=color)


def draw_stat(draw, number, label, x, y):
    draw.text((x, y), number, fill=ACCENT, font=font(72, bold=True))
    draw.text((x, y + 85), label, fill=GRAY, font=font(28))


# ─── 각 장 생성 ──────────────────────────────────────────────────────────────

def card_01():
    """훅 — 큰 숫자로 임팩트"""
    img = new_card()
    draw = ImageDraw.Draw(img)
    draw_page_num(draw, 1)
    draw.text((80, 200), "정부 지원사업", fill=GRAY, font=font(36))
    draw.text((80, 280), "271건", fill=ACCENT, font=font(120, bold=True))
    draw.text((80, 430), "2분 만에", fill=WHITE, font=font(64, bold=True))
    draw.text((80, 520), "전수조사 했다", fill=WHITE, font=font(64, bold=True))
    draw.rounded_rectangle([60, 700, W - 60, 860], radius=16, fill=BG_CARD)
    draw.text((100, 730), "검색으로는 절대 못 찾는 것들이", fill=LIGHT, font=font(32))
    draw.text((100, 790), "수두룩하다. AI로 자동화한 방법 공유.", fill=LIGHT, font=font(32))
    draw.text((80, H - 120), "→ 넘겨서 확인", fill=ACCENT, font=font(30, bold=True))
    return img


def card_02():
    """문제 제기 — 검색의 한계"""
    img = new_card()
    draw = ImageDraw.Draw(img)
    draw_page_num(draw, 2)
    draw_header(draw, "# 문제")
    y = draw_title(draw, '"AI"로 검색하면?')
    draw.rounded_rectangle([60, y + 30, W - 60, y + 180], radius=16, fill=BG_CARD)
    draw.text((100, y + 60), "K-Startup 검색 결과:  15건", fill=ACCENT2, font=font(36, bold=True))
    draw.text((100, y + 120), "실제 지원 가능한 사업:  41건", fill=ACCENT, font=font(36, bold=True))
    y2 = y + 250
    draw_body(draw, [
        "X  콘텐츠 제작지원 - 안 잡힘",
        "X  예술x기술 입주 - 안 잡힘",
        "X  사회서비스 창업 - 안 잡힘",
        "",
        '→ "AI"라는 단어가 제목에 없으니까',
    ], y=y2, size=34)
    return img


def card_03():
    """3대 실패"""
    img = new_card()
    draw = ImageDraw.Draw(img)
    draw_page_num(draw, 3)
    draw_header(draw, "지원사업 찾기의 3대 실패")
    boxes = [
        ("① 키워드 사각지대", "내가 지원 가능한데\n제목에 내 키워드가 없음", ACCENT2),
        ("② 자격요건 오판", "제목만 보고 2주 준비\n→ '예비창업자 불가'", ACCENT3),
        ("③ 정보 과부하", "271건을 사람이\n일일이 읽을 수 없음", ACCENT),
    ]
    y = 260
    for title, desc, color in boxes:
        draw.rounded_rectangle([60, y, W - 60, y + 260], radius=16, fill=BG_CARD, outline=color, width=2)
        draw.text((100, y + 30), title, fill=color, font=font(36, bold=True))
        for i, line in enumerate(desc.split("\n")):
            draw.text((100, y + 90 + i * 50), line, fill=LIGHT, font=font(32))
        y += 300
    return img


def card_04():
    """해결: 시스템 흐름"""
    img = new_card()
    draw = ImageDraw.Draw(img)
    draw_page_num(draw, 4)
    draw_header(draw, "내가 만든 시스템")
    steps = [
        ("1", "크롤러가 전수 수집", "271건, 2분"),
        ("2", "AI가 전체 제목 직접 읽음", "키워드 검색 아님"),
        ("3", "상세공고에서 자격 검증", "예비창업자 가능?"),
        ("4", "3분류 보고서 생성", "A/B/C 등급"),
    ]
    y = 280
    for num, title, sub in steps:
        draw.ellipse([80, y + 5, 130, y + 55], fill=ACCENT)
        draw.text((93, y + 8), num, fill=BG_DARK, font=font(32, bold=True))
        draw.text((160, y + 10), title, fill=WHITE, font=font(38, bold=True))
        draw.text((160, y + 65), sub, fill=GRAY, font=font(28))
        if num != "4":
            draw.line([105, y + 60, 105, y + 140], fill=ACCENT, width=2)
        y += 220
    return img


def card_05():
    """실제 결과 — 통계"""
    img = new_card()
    draw = ImageDraw.Draw(img)
    draw_page_num(draw, 5)
    draw_header(draw, "오늘 실행 결과")
    draw_stat(draw, "271", "건 수집", 100, 220)
    draw_stat(draw, "2", "분 소요", 550, 220)
    y = 450
    cats = [
        ("멘토링/교육", "64건", 0.24),
        ("시설/공간", "58건", 0.21),
        ("사업화 자금", "52건", 0.19),
        ("행사/네트워크", "33건", 0.12),
        ("기타", "64건", 0.24),
    ]
    for label, count, ratio in cats:
        draw.rounded_rectangle([80, y, 80 + int(700 * ratio), y + 50], radius=8, fill=ACCENT)
        draw.text((80 + int(700 * ratio) + 20, y + 8), f"{label} {count}", fill=LIGHT, font=font(28))
        y += 80
    draw.text((80, y + 40), "[!] 마감 D-1: 5건 발견", fill=ACCENT2, font=font(34, bold=True))
    return img


def card_06():
    """변형 지원 — 핵심 차별점"""
    img = new_card()
    draw = ImageDraw.Draw(img)
    draw_page_num(draw, 6)
    draw_header(draw, "핵심: 변형 지원")
    draw.text((80, 200), "각도만 바꾸면 지원 가능한 것들", fill=WHITE, font=font(38, bold=True))
    examples = [
        ("TTS 회사", "→", "콘텐츠 제작지원", "(음성 콘텐츠)"),
        ("AI 헬스케어", "→", "사회서비스 창업", "(장애인 접근성)"),
        ("SaaS", "→", "아트코리아랩 입주", "(디자인 도구)"),
    ]
    y = 360
    for src, arrow, dst, note in examples:
        draw.rounded_rectangle([60, y, W - 60, y + 160], radius=16, fill=BG_CARD)
        draw.text((100, y + 20), src, fill=ACCENT2, font=font(34, bold=True))
        draw.text((100, y + 70), f"{arrow} {dst}", fill=ACCENT, font=font(34, bold=True))
        draw.text((100, y + 115), note, fill=GRAY, font=font(26))
        y += 200
    draw.text((80, y + 30), "이건 사람이 읽어도 못 찾는다.", fill=LIGHT, font=font(30))
    draw.text((80, y + 75), "AI가 알려줘야 보인다.", fill=LIGHT, font=font(30))
    return img


def card_07():
    """3분류 설명"""
    img = new_card()
    draw = ImageDraw.Draw(img)
    draw_page_num(draw, 7)
    draw_header(draw, "보고서: 3분류 시스템")
    groups = [
        ("A", "즉시 지원 가능", "지금 바로 서류 넣으면 됨\n마감순 정렬, 임박건 강조", ACCENT),
        ("B", "로드맵", "법인 설립/투자유치 하면 열림\n연쇄 경로 표시", ACCENT3),
        ("C", "변형 가능", "아이템을 다른 분야 언어로\n재서술하는 각도 제안", ACCENT2),
    ]
    y = 260
    for emoji, title, desc, color in groups:
        draw.rounded_rectangle([60, y, W - 60, y + 240], radius=16, fill=BG_CARD, outline=color, width=3)
        draw.text((100, y + 30), f"{emoji} {title}", fill=color, font=font(40, bold=True))
        for i, line in enumerate(desc.split("\n")):
            draw.text((100, y + 100 + i * 48), line, fill=LIGHT, font=font(30))
        y += 290
    return img


def card_08():
    """자동 알림"""
    img = new_card()
    draw = ImageDraw.Draw(img)
    draw_page_num(draw, 8)
    draw_header(draw, "자동화")
    draw.text((80, 200), "한 번 세팅하면", fill=WHITE, font=font(44, bold=True))
    draw.text((80, 270), "매달 자동 실행", fill=WHITE, font=font(44, bold=True))
    features = [
        ">  매월 1일, 15일 자동 크롤링",
        ">  새로 열린 공고 감지",
        ">  텔레그램 알림 전송",
        ">  이전 대비 변동사항 표시",
    ]
    y = 450
    for feat in features:
        draw.rounded_rectangle([60, y, W - 60, y + 80], radius=12, fill=BG_CARD)
        draw.text((100, y + 20), feat, fill=LIGHT, font=font(32))
        y += 120
    draw.text((80, y + 60), '"모집 시작하자마자 알림 왔다"', fill=ACCENT, font=font(34, bold=True))
    return img


def card_09():
    """준비물"""
    img = new_card()
    draw = ImageDraw.Draw(img)
    draw_page_num(draw, 9)
    draw_header(draw, "준비물")
    draw.text((80, 200), "코드 50줄 + 프롬프트 1개", fill=WHITE, font=font(44, bold=True))
    items = [
        ("Python", "크롤러 실행", "v"),
        ("Claude", "공고 분류 AI", "v"),
        ("10분", "세팅 시간", "v"),
    ]
    y = 380
    for name, desc, check in items:
        draw.rounded_rectangle([60, y, W - 60, y + 140], radius=16, fill=BG_CARD)
        draw.text((100, y + 25), name, fill=ACCENT, font=font(42, bold=True))
        draw.text((100, y + 80), desc, fill=GRAY, font=font(28))
        draw.text((W - 150, y + 40), check, fill=ACCENT, font=font(50))
        y += 180
    draw.text((80, y + 40), "프로그래밍 못 해도 복붙이면 끝", fill=LIGHT, font=font(32))
    return img


def card_10():
    """CTA"""
    img = new_card()
    draw = ImageDraw.Draw(img)
    draw_page_num(draw, 10)
    draw.text((80, 200), "소스코드 +", fill=WHITE, font=font(52, bold=True))
    draw.text((80, 280), "프롬프트 전문", fill=WHITE, font=font(52, bold=True))
    draw.text((80, 370), "공유합니다", fill=ACCENT, font=font(52, bold=True))
    draw.rounded_rectangle([60, 520, W - 60, 900], radius=20, fill=BG_CARD, outline=ACCENT, width=3)
    draw.text((100, 570), "받는 법:", fill=ACCENT, font=font(36, bold=True))
    draw.text((100, 650), "1. 이 계정 팔로우", fill=LIGHT, font=font(40))
    draw.text((100, 730), '2. DM으로 "지원사업" 전송', fill=LIGHT, font=font(40))
    draw.text((100, 830), "→ 바로 보내드립니다", fill=ACCENT, font=font(32, bold=True))
    draw.text((80, H - 150), "저장해두고 나중에 보내셔도 돼요", fill=GRAY, font=font(28))
    return img


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    cards = [card_01, card_02, card_03, card_04, card_05,
             card_06, card_07, card_08, card_09, card_10]
    for i, func in enumerate(cards, 1):
        img = func()
        path = os.path.join(OUTPUT_DIR, f"{i:02d}.png")
        img.save(path, "PNG", quality=95)
        print(f"  [{i}/10] {path}")
    print(f"\n완료: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
