# AI로 정부 지원사업 자동 전수조사 시스템 만들기

> 내 프로젝트 정보만 입력하면 지원 가능한 정부사업을 자동으로 찾아주는 시스템

---

## 한 줄 요약

Python 크롤러로 K-Startup·기업마당의 **모집중 공고를 전수 수집**하고, AI가 내 프로필에 맞는 사업을 골라서 **"즉시 지원 / 로드맵 / 변형 가능"** 3단계로 분류한 보고서를 만들어줍니다.

---

## 왜 이게 필요한가

### 기존 방식의 3가지 실패

| 실패 원인 | 실제 상황 | 결과 |
|-----------|----------|------|
| **키워드 사각지대** | "AI"로 검색 → 콘텐츠 제작지원, 예술x기술 입주 등 못 찾음 | 지원 가능한 사업 70% 놓침 |
| **자격요건 오판** | 제목만 보고 2주 준비 → "예비창업자 불가" 발견 | 시간 낭비 |
| **추정 보고** | "아마 될 것 같아요" → 실제론 지역 제한 | 방향 틀림 |

### 이 시스템의 해결법

- 키워드 검색 X → **전수 수집 후 AI가 전체 제목을 직접 읽음**
- 제목만 판단 X → **상세공고 원문에서 자격요건 자동 검증**
- 추정 보고 X → **공고에 없으면 '불명' + 문의처 표기**

---

## 전체 흐름

```
프로필 입력 → 크롤러가 전수 수집 (300~1000건)
→ AI가 전체 제목 직접 읽고 후보 선별 (25~40건)
→ 상세공고 원문에서 자격요건 검증
→ 3분류 보고서 생성 (A: 즉시 / B: 로드맵 / C: 변형)
```

---

## 1. 환경 세팅

### 필요한 것
- Python 3.10+
- curl_cffi (TLS 지문 차단 우회용)

```bash
pip install 'curl_cffi>=0.15'
```

> curl_cffi가 없어도 urllib로 동작하지만, K-Startup이 TLS 지문으로 차단할 수 있어서 권장합니다.

---

## 2. 크롤러 코드

아래 코드를 `scanner.py`로 저장하세요.

### 핵심 구조

```python
def _make_session():
    """curl_cffi로 Safari 지문 세션 생성. 없으면 urllib 폴백."""
    from curl_cffi import requests as cr
    sess = cr.Session(impersonate="safari")
    # Safari인 척 해야 K-Startup이 안 막음

def scan_kstartup(fetch, max_pages=30):
    """K-Startup 모집중 공고 전수 수집"""
    for page in range(1, max_pages + 1):
        url = f"{BASE}?page={page}&pbancEndYn=N"
        status, html = fetch(url)
        items = _parse_kstartup_list(html)
        # 페이지별 15건씩, 더 이상 없으면 중단

def scan_bizinfo(fetch, max_pages=15):
    """기업마당 전 부처 공고 수집"""
    for page in range(1, max_pages + 1):
        url = f"{BASE}?rows=20&cPage={page}"
        # ...
```

### 파싱 핵심

K-Startup은 HTML에 `id="bizPbancList"` 영역 안에 공고가 `<li>` 태그로 나열됩니다:

```python
def _parse_kstartup_list(html):
    body = html.split('id="bizPbancList"', 1)[1]
    for blk in re.split(r"<li\b[^>]*>", body)[1:]:
        sn = re.search(r"go_view\((\d+)\)", blk).group(1)  # 공고번호
        title = re.search(r'<p class="tit">\s*([^<]+)', blk)  # 제목
        deadline = pick("마감일자")  # 마감일
        # → JSONL로 저장
```

기업마당은 `<tbody>` 안에 `<tr>` 행으로 정리:

```python
def _parse_bizinfo_list(html):
    tbody = html.split("<tbody")[1]
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tbody, re.DOTALL)
    # 각 행의 td: [번호, 카테고리, 제목, 기간, 주관부처, 수행기관, ...]
```

> 전체 소스코드는 아래 첨부 파일에 있습니다. 복사해서 그대로 사용하세요.

---

## 3. 실행

```bash
# K-Startup 모집중 전수 수집 (~300건, 2분)
python3 scanner.py kstartup -o results/kstartup.jsonl

# 기업마당 수집
python3 scanner.py bizinfo -o results/bizinfo.jsonl

# 전체 소스 일괄
python3 scanner.py all -o results/all.jsonl

# 상세 페이지 텍스트 추출 (자격요건 검증용)
python3 scanner.py detail 178499 178493 -o results/details/
```

### 실제 결과 예시

```json
{
  "source": "kstartup",
  "id": "178499",
  "category": "시설·공간·보육",
  "dday": "D-18",
  "title": "2026 아트코리아랩 입주기업 모집 공모",
  "org": "예술경영지원센터",
  "start": "2026-07-13",
  "deadline": "2026-07-30",
  "url": "https://www.k-startup.go.kr/..."
}
```

---

## 4. AI에게 분류시키기 (Claude 프로젝트 지침)

수집된 JSONL을 Claude에게 넘기고 분류하게 합니다. 아래 지침을 Claude 프로젝트에 넣으세요:

```
당신은 정부 지원사업 전수조사 분석가입니다.

## 내 프로필
- 창업 단계: [예비창업자/개인/법인]
- 지역: [소재지]
- 나이/성별: [청년/중장년, 남/여]
- 필요: [자금/공간/R&D/멘토링]
- 아이템: [한 줄 설명]

## 분류 기준

A그룹 (즉시 지원 가능):
- 현재 신분 그대로 자격 충족
- 마감순으로 정렬, 3일 이내 마감은 "임박" 표기

B그룹 (로드맵):
- 법인 설립, 투자유치, 지역 이전 등 트리거가 명확
- 트리거 간 연쇄를 표시 (예: 경진대회 수상 → 투자유치 → TIPS)

C그룹 (변형 가능):
- 아이템을 다른 분야 언어로 재서술하면 대상이 됨
- 구체적 프레이밍 각도 제안 + 리스크 명시

## 규칙
- 공고 원문에 없는 정보는 '불명' 표기
- 모든 공고에 URL 필수
- 마감일·금액은 원문 확인분만 기재
- 추정 금지
```

### 첫 프롬프트

```
첨부한 JSONL 파일의 공고 목록을 전수 검토해줘.
내 프로필에 맞는 사업을 A/B/C 3그룹으로 분류하고,
A그룹은 상세공고까지 확인해서 자격요건을 검증해줘.
```

---

## 5. 자동화 (정기 실행)

월 2회 cron으로 돌려서 새 공고를 자동 감지:

```bash
# crontab 예시: 매월 1일, 15일 오전 9시
0 9 1,15 * * cd ~/gov-funding-scanner && python3 scanner.py all -o results/$(date +\%Y\%m\%d).jsonl
```

---

## 6. 확장 가능한 소스

현재 K-Startup + 기업마당 2개를 커버하지만, 같은 구조로 추가 가능:

| 소스 | 특화 영역 |
|------|----------|
| NIPA | AI/ICT 사업 |
| KOCCA | 콘텐츠 지원 |
| SMTECH | 중기부 R&D |
| 지역 창조경제혁신센터 | 지역 특화 |

---

## 핵심 인사이트

1. **전수조사 > 키워드 검색** — 키워드에 안 잡히는 "변형 지원"이 실제로 가장 가치 높음
2. **3분류가 핵심** — "즉시"와 "로드맵"을 구분해야 행동이 달라짐
3. **C그룹(변형)이 진짜 차별점** — AI가 "이 아이템을 이 분야 언어로 바꾸면 이 사업에 해당된다"를 제안
4. **자격요건 검증 필수** — 제목만 보면 70%는 오판. 상세공고 원문 확인이 필수

---

## 실전 팁

- **마감 임박 체크**: D-3 이내면 무조건 보고서 상단에 올리기
- **변형 프레이밍 예시**: TTS 기업 → "콘텐츠 제작지원" (음성 콘텐츠), "사회서비스" (시각장애인 접근성)
- **부재 확인**: 유명 사업(예비창업패키지, TIPS 등)이 현재 모집 아니면 명시적으로 알림
- **연쇄 경로**: 경진대회 수상 → 투자유치 실적 → 프리팁스 → TIPS 본선
