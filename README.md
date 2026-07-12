# 정부 지원사업 전수조사 스캐너

> AI가 정부 지원사업 공고를 **전수 검토**해서 내 프로젝트에 맞는 사업을 자동으로 찾아줍니다.

키워드 검색의 한계를 넘어, 모집중인 모든 공고의 제목을 AI가 직접 읽고 판단합니다.

## 왜 키워드 검색이 안 되는가

"AI 스타트업"으로 검색하면 놓치는 것들:
- 콘텐츠 제작지원 (AI 콘텐츠도 해당)
- 예술×기술 입주사업 (AI 아트도 해당)
- 사회서비스 창업지원 (AI 헬스케어도 해당)

→ **전수조사**가 답입니다.

## 커버 소스

| 소스 | 내용 | 규모 |
|------|------|------|
| [K-Startup](https://www.k-startup.go.kr) | 창업지원 통합 | ~300건 |
| [기업마당](https://www.bizinfo.go.kr) | 전 부처·지자체 | ~1,000건+ |

## 설치

```bash
git clone <this-repo>
pip install 'curl_cffi>=0.15'
```

## 사용법

```bash
# K-Startup 모집중 공고 전수 수집
python3 scripts/scanner.py kstartup -o results/kstartup.jsonl

# 기업마당 공고 수집
python3 scripts/scanner.py bizinfo -o results/bizinfo.jsonl

# 전체 소스 일괄
python3 scripts/scanner.py all -o results/all.jsonl

# 상세 페이지 텍스트 추출
python3 scripts/scanner.py detail 178499 -o results/details/
```

## 산출물: 3분류 보고서

| 분류 | 의미 |
|------|------|
| **A그룹** | 지금 즉시 지원 가능 — 현재 자격으로 충족 |
| **B그룹** | 요건 충족 시 열림 — 법인설립, 투자유치 등 트리거 명시 |
| **C그룹** | 변형하면 가능 — 아이템을 다른 분야 언어로 재서술하는 각도 제안 |

## 구조

```
gov-funding-scanner/
├── SKILL.md          # AI 워크플로 정의
├── README.md         # 이 파일
└── scripts/
    └── scanner.py    # K-Startup + 기업마당 크롤러
```

## 주의

- 공개 공고 페이지만 접근합니다
- 요청 간 0.4초 딜레이를 둡니다
- 공고 내용은 수시로 변경됩니다 — 신청 전 반드시 접수기관에 확인하세요

## License

MIT
