# CRAI — Game Community Trend Detection System

> 리니지 시리즈 커뮤니티(Reddit · Bilibili · 인벤 · Bahamut)의 게시글을 자동 수집하고,  
> 멀티 에이전트 AI 파이프라인으로 분석해 **핵/봇, 업데이트, 경제, 여론** 이슈를 자동 탐지하는 트렌드 모니터링 시스템.

---

## 왜 만들었나

리니지 시리즈는 한국(인벤), 영어권(Reddit), 중국(Bilibili), 대만(Bahamut)에 걸쳐 대규모 커뮤니티가 동시에 운영된다. 각 플랫폼의 언어와 형식이 달라 사람이 직접 모니터링하기 어렵고, 핵/봇 급증이나 시세 폭락 같은 이상 신호가 발생해도 늦게 파악되는 문제가 있다.

CRAI는 이 네 플랫폼을 한 곳에서 수집·분석해 **반복적으로 등장하는 이슈 패턴을 조기에 탐지**하는 것을 목표로 한다.

---

## 핵심 특징

| | |
|---|---|
| **4개 플랫폼 동시 수집** | 한국어(인벤), 영어(Reddit), 중국어(Bilibili), 번체중국어(Bahamut) |
| **6개 게임 커버** | 리니지 클래식 · 리마스터 · 2 · M · 2M · W |
| **24시간 롤링 수집** | 6시간 간격 스케줄러, EC2에서 상시 가동, 30일 만료 자동 삭제 |
| **데이터 기반 카테고리** | 실제 수집 데이터 분석으로 귀납적 도출한 4개 분류 체계 |
| **멀티 에이전트 파이프라인** | 필터 → 번역 → 분류 → 분석 → 보고서, 각 단계 검증 포함 |
| **실시간 대시보드** | 수집 현황 차트, 게시글 테이블, AI 리포트 카드 + 근거 게시글 연결 |

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| **백엔드** | Python 3.10+, FastAPI, APScheduler |
| **프론트엔드** | Next.js 14 (App Router), TypeScript, Tailwind CSS, Recharts |
| **DB** | PostgreSQL (AWS RDS) |
| **크롤링** | Apify (Reddit, Bilibili), crawl4ai + Playwright (인벤·Bahamut 직접 크롤링) |
| **AI** | Claude API (Anthropic) — 멀티 에이전트 파이프라인 (Filter · Translate · Classify 구현 완료) |
| **인프라** | AWS EC2 t3.small (us-east-1), AWS RDS PostgreSQL |

---

## 이슈 카테고리 설계

AI 분류 에이전트가 게시글을 4개 카테고리로 분류한다. 카테고리는 임의로 정한 것이 아니라, **Reddit · Bilibili · 인벤 3개 플랫폼에서 실제 수집된 게시글을 직접 검토하여 반복적으로 등장하는 주제를 귀납적으로 도출**했다.

### 실제 데이터에서 확인한 근거

| 카테고리 | 실제 관측 예시 | 출처 |
|----------|--------------|------|
| **핵/봇** | "자동 많고 비엠 많이 나오고", "아니 자동들이 ~~~~??" | 인벤 |
| | "对峙2最好的作弊器" (최고의 치트툴), 외부 핵 사용법 영상 | Bilibili |
| **업데이트** | "성장 상한 버그 수정(BUG修正)", "Lineage-仿正服角色成长上限BUG修正" | Bilibili |
| | "2단가속상자는 지금 손해인가", "패치 이후 시세 봐요" | 인벤 |
| **경제** | "뎅값 나락간김에", "천만뎅 65만? 이거 맞는교?" | 인벤 |
| | "ㅂㄹ템 ㅂ.ㅅ같은 시세 조작" | 인벤 |
| **여론** | "사람들이 다 떠난 이유", "나도 접고 싶은데" | 인벤 |
| | "리니지는 역시 고여서 썩었구나", "이제부터 물오리 열사로 부르겠습니다" | 인벤 |

### 카테고리 정의

| 카테고리 | 설명 |
|----------|------|
| **핵/봇** | 불법 프로그램(자동사냥봇, 매크로, 치트툴) 사용·유포·제보 관련 이슈 |
| **업데이트** | 패치 내용, 밸런스 변경, 버그 수정, 신규 콘텐츠에 대한 반응 |
| **시세/거래** | 게임 내 재화(뎅, 아덴 등) 시세·시세 조작·작업장·거래소 이슈 |
| **여론** | 유저 이탈, 게임 평가, 운영사 비판, 커뮤니티 감정 흐름 |

> 4개 분류는 리니지 시리즈에서 구조적으로 반복되는 이슈 유형에 대응하며, 플랫폼이 추가되거나 신규 게임이 편입되어도 동일하게 적용 가능하다.

---

## 시스템 파이프라인

```
[Reddit / Bilibili / 인벤]
        │
        │  6시간 주기 자동 수집 (EC2 스케줄러)
        ▼
[AWS RDS PostgreSQL]  ←── 30일 만료 데이터 자동 삭제
        │
        ▼
   [Analyzer]  ──── 검증 실패 시 재시도 ────┐
        │                                   │
   [Validator] ◄──────────────────────────┘
        │
        │  최종 승인 → trend_reports 저장
        ▼
[Next.js Dashboard]  ←── 사용자 요청 시 조회
```

### AI 분석 파이프라인 (6~9주차)

```
원시 데이터 (Reddit + Bilibili + 인벤, 한국어·영어·중국어)
  │
  ▼  1. 필터 에이전트   ✅ 구현 완료   리니지 무관·질문/공략·잡담 제거
  ▼  2. 번역 에이전트   ✅ 구현 완료   중국어 / 영어 → 한국어 (뎅·아덴 등 고유명사 보존)
  ▼  3. 분류 에이전트   ✅ 구현 완료   핵/봇 · 업데이트 · 시세/거래 · 여론 분류
  ▼  4. 분석 에이전트   ⏳ 구현 예정   트렌드 감지, 이상 징후 탐지, 위험도 평가
  ▼  5. 보고서 에이전트 ⏳ 구현 예정   최종 리포트 생성 및 DB 저장
```

각 에이전트는 독립적으로 실행 가능하며, `run_pipeline.py`로 전체 파이프라인을 순차 실행한다.
결과는 `backend/data/results/pipeline_YYYYMMDD_HHMMSS.json`에 로컬 저장된다.

#### 필터 에이전트 상세 (`filter_agent.py`)

Claude Haiku API를 호출해 게시글의 트렌드 분석 유의미성을 판단한다.

filter → translate → classify 순서의 핵심 근거: **번역 전에 걸러서 번역 API 비용 절감**. 따라서 filter는 원문(한국어·중국어·영어) 그대로 판단한다.

**포함 기준:** 리니지 게임(클래식·리마스터·2·M·2M·W)과 관련된 모든 내용. 질문·잡담·여론·시세·핵봇 등 주제 무관하게 리니지 게임 관련이면 통과.

**제외 기준:**
- 리니지OS(안드로이드 운영체제), 혈통(일반적 의미) 등 리니지 게임과 무관한 내용
- 리니지 게임과 전혀 관계없는 일상 게시글
- 제목 없거나 본문 10자 미만 → API 호출 없이 즉시 제거

#### 번역 에이전트 상세 (`translate_agent.py`)

- `inven` → 한국어이므로 번역 스킵, 원본 그대로 `translated_title` / `translated_content`에 복사
- `reddit` / `bilibili` / `bahamut` → Claude Haiku로 한국어 번역, JSON 형식 응답 파싱
- 뎅·아덴 등 게임 고유 명칭은 번역하지 않고 그대로 유지
- 본문 500자 제한 (비용 절감), API 오류 시 원본 반환

#### 분류 에이전트 상세 (`classify_agent.py`)

`translated_title` / `translated_content` 기준으로 분류 (없으면 원본 사용).

| 카테고리 | 분류 기준 |
|----------|-----------|
| **핵/봇** | 불법 프로그램·자동사냥봇·매크로·치트툴 사용·유포·제보 |
| **업데이트** | 운영사 배포 패치·밸런스 변경·신규 콘텐츠에 대한 반응. "이번 패치", "업데이트 이후" 등 운영사 행동 언급 필수 |
| **시세/거래** | 게임 내 재화(뎅·아덴) 시세 변동·거래소·작업장·아이템 거래 이슈. 단순 아이템 질문 제외 |
| **운영 비판** | NC 정책·행태·서비스 비판, 유저 이탈·게임 존폐 우려, 고객지원 불만, 과금 정책 비판 |
| **커뮤니티** | 위 4개 외 모든 것. 게임플레이 질문·공략·잡담·자랑·일반 감상 |

판단 순서: 핵/봇 → 업데이트 → 시세/거래 → 운영 비판 → 커뮤니티.
유효하지 않은 분류 반환 시 기본값 `"커뮤니티"` 처리. API 오류 시도 `"커뮤니티"` 반환.

**분류 체계 설계 근거:**
기존 `여론` 카테고리가 전체의 70%를 차지하며 운영사 비판(트렌드 분석 핵심)과 단순 잡담이 혼재함.
`운영 비판`을 별도로 분리해 운영팀이 즉시 참고할 수 있는 신호와 일반 커뮤니티 노이즈를 구분.

**`커뮤니티` 카테고리 포함 내용:**
트렌드 분석에 직접 쓰이진 않지만 커뮤니티 활성도 지표로 활용 가능.

| 유형 | 예시 |
|------|------|
| 게임플레이 질문 | `[질문]기사단 망토 인챈트 질문`, `【문제】힘 성검` |
| 공략/정보 공유 | `[잡담]91 마검사 사냥시 룬 셋팅`, `【팁】인형·성물 증명서 출처` |
| 자랑/성과 | `[잡담]드디어 8층 가나`, `[잡담]짭사이드 처음 성공했다` |
| 클래스 토론 | `[잡담]투사 징징거리지 마라`, `[잡담]너무 쎄다 광전사` |
| 일상 잡담 | `[잡담]오랜만이다`, `[잡담]현생복귀` |
| 팁/노하우 | `【노하우】성검사~황 연속 실측`, `【수다】요정이 칼 들고 새로운 세계 발견` |
| 일러스트/창작 | `【그림】여 법사`, `【일러스트】검은 요정 선화 공유` |

리포트에서 "이번 주 커뮤니티 활동량" 지표로만 집계하고 상세 분석 대상에서는 제외.

#### 파이프라인 실행

```bash
cd backend
python -m pipeline.run_pipeline
```

결과 로그 예시:
```
[Pipeline] 시작 - game=None
[Pipeline] DB에서 20개 게시글 로드
[Filter] 제거: [잡담]5월 5일까지 노는 애들 부럽다
[Filter] 총 20개 중 14개 통과
[Translate] 14개 게시글 처리 완료
[Classify] 14개 게시글 분류 완료
[Pipeline] 결과 저장: backend/data/results/pipeline_20260512_162118.json
[Pipeline] 완료: 14개 처리 | 소요시간: 36.9초
```

---

## 크롤링 타겟

| 플랫폼 | 방식 | 수집 대상 | 수집 기간 |
|--------|------|-----------|-----------|
| **Reddit** | Apify `trudax/reddit-scraper-lite` | r/Lineage, r/lineage2, r/LineageM, r/LineageW | 최근 24시간 |
| **Bilibili** | Apify `zhorex/bilibili-scraper` | 게임별 중국어 키워드 (外挂/hack/bot/更新 등) | 최근 24시간 |
| **인벤** | crawl4ai + Playwright (직접 크롤링) | 6개 게임 자유게시판 각 2페이지 | 최근 24시간 |
| **Bahamut** | crawl4ai + Playwright (직접 크롤링) | 6개 게임 관련 게시판 | 최근 24시간 |

**Reddit 노이즈 제거:** `lineageos`, `android`, `rom`, `aosp` 포함 게시글 자동 제외 — LineageOS(안드로이드 OS 배포판)와 혼재 방지

**인벤 날짜 처리:** 목록의 `HH:MM` / `MM-DD` 형식을 KST 기준으로 파싱 후, 상세 페이지에서 정확한 날짜와 본문 재수집. 봇 차단 방지를 위해 요청 사이 1초 대기.

### Bilibili 게임별 검색 키워드

| 게임 | 키워드 |
|------|--------|
| lineage_m | 天堂M 外挂, 天堂M hack, 天堂M cheat, 天堂M bot, 天堂M 脚本, 天堂M 辅助, 天堂M 更新, 天堂M 私服, lineage m hack, lineage m bot, lineage m update |
| lineage2 | 天堂2 外挂, 天堂2 hack, 天堂2 bot, 天堂2 更新, lineage2 hack |
| lineage_classic | 天堂经典 外挂, 天堂经典 脚本, 天堂经典 更新, lineage classic hack |
| lineage_remaster | 天堂重制版 外挂, 天堂重制版 更新, 天堂重制版 游戏 |
| lineage2m | 天堂2M 外挂, 天堂2M 更新, 天堂2M 游戏, lineage 2m hack |
| lineage_w | 天堂W 外挂, 天堂W 更新, lineage w hack |

---

## 프로젝트 구조

```
CRAI/
├── .env                        # API 키 및 DB 연결 정보 (git 제외)
├── .env.example                # 환경변수 템플릿
├── ec2.md                      # EC2 서버 세팅 및 운영 가이드
├── ssh.bat                     # EC2 SSH 접속 스크립트 (Windows)
│
├── backend/
│   ├── requirements.txt
│   ├── api/
│   │   ├── main.py             # FastAPI 앱 진입점 (CORS 설정, 라우터 등록, DB 초기화)
│   │   └── routers/
│   │       ├── posts.py        # GET /posts — 게시글 목록 (DB 레벨 페이지네이션)
│   │       ├── stats.py        # GET /stats — 수집 통계 / GET /logs — 크롤링 로그
│   │       ├── crawl.py        # POST /crawl — 크롤러 즉시 실행 트리거
│   │       └── reports.py      # GET·POST·DELETE /reports — 트렌드 리포트 CRUD
│   ├── crawlers/
│   │   ├── reddit_crawler.py   # Apify 연동, r/Lineage 계열 4개 서브레딧
│   │   ├── bilibili_crawler.py # Apify 연동, 게임별 중국어 키워드 검색
│   │   ├── inven_crawler.py    # crawl4ai + Playwright, 6개 게임 자유게시판
│   │   └── bahamut_crawler.py  # crawl4ai + Playwright, 대만 Bahamut 게시판
│   ├── pipeline/
│   │   ├── crawler_runner.py   # Reddit/Bilibili 병렬 실행 + 인벤/Bahamut 순차 실행 → DB 저장
│   │   ├── filter_agent.py     # 리니지 무관·질문/공략·잡담 제거 (Claude Haiku)
│   │   ├── translate_agent.py  # 영어·중국어 → 한국어 번역, inven 스킵 (Claude Haiku)
│   │   ├── classify_agent.py   # 핵/봇·업데이트·시세/거래·여론 분류 (Claude Haiku)
│   │   └── run_pipeline.py     # 전체 파이프라인 실행 진입점, 결과 로컬 JSON 저장
│   ├── scheduler/
│   │   └── scheduler.py        # 시작 즉시 1회 + 6시간 간격 반복, 30일 만료 처리
│   ├── db/
│   │   ├── database.py         # RDS 연결, 테이블 초기화, CRUD, DB 레벨 페이지네이션
│   │   ├── preprocess.py       # HTML 태그 제거, 날짜 정규화, 빈 항목 필터
│   │   └── cli.py              # 터미널 DB 조회 도구 (stats / posts / logs)
│   └── utils/
│       └── config.py           # 환경변수 로드 (APIFY_API_TOKEN, DATABASE_URL, DATA_DIR)
│
├── frontend/
│   ├── lib/
│   │   └── gameLabels.ts       # GAME_LABELS 상수 (전체 컴포넌트 공통 사용)
│   ├── app/
│   │   ├── page.tsx            # 메인 대시보드 페이지
│   │   ├── layout.tsx
│   │   └── api/                # Next.js → FastAPI 프록시 라우트
│   │       ├── posts/route.ts  # → GET /posts
│   │       ├── stats/route.ts  # → GET /stats
│   │       └── crawl/route.ts  # → POST /crawl
│   └── components/
│       ├── Sidebar.tsx         # 게임 / 소스 / 카테고리 / 기간 필터 사이드바
│       ├── StatsChart.tsx      # 게임별·소스별 수집 현황 막대 차트 (Recharts)
│       ├── PostsTable.tsx      # 게시글 목록 테이블 (서버사이드 페이지네이션)
│       ├── CrawlButton.tsx     # 수동 크롤링 버튼 (실행 중 상태 표시)
│       └── TrendReport.tsx     # AI 트렌드 리포트 카드 컴포넌트
│
└── backend/data/               # 원시 데이터 로컬 JSON 백업 (30일 후 자동 삭제)
    ├── reddit/{game}/YYYY-MM-DD_HH-MM.json
    ├── bilibili/{game}/YYYY-MM-DD_HH-MM.json
    └── inven/{game}/YYYY-MM-DD_HH-MM.json
```

---

## DB 스키마

### `posts` — 수집된 게시글

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL PK | |
| url | TEXT UNIQUE | 중복 저장 방지 키 (`ON CONFLICT DO NOTHING`) |
| title | TEXT | HTML 태그 제거 후 저장 |
| content | TEXT | HTML 태그 제거 후 저장 |
| author | TEXT | |
| date | TEXT | `YYYY-MM-DD` 또는 `YYYY-MM-DD HH:MM` 정규화 |
| game | TEXT | `lineage_classic` / `lineage_remaster` / `lineage2` / `lineage_m` / `lineage2m` / `lineage_w` |
| source | TEXT | `reddit` / `bilibili` / `inven` / `bahamut` |
| keyword | TEXT | Bilibili 검색 키워드 (해당 시) |
| views | TEXT | |
| recommend | TEXT | |
| raw | TEXT | 원본 JSON 전체 백업 |
| created_at | TEXT | UTC ISO 문자열 — 30일 경과 시 자동 삭제 기준 |

### `crawl_logs` — 크롤링 실행 기록

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL PK | |
| run_at | TEXT | UTC ISO 문자열 |
| source | TEXT | `reddit` / `bilibili` / `inven` / `bahamut` |
| game | TEXT | |
| status | TEXT | `success` / `error` |
| count | INTEGER | 신규 저장 건수 (중복 제외) |
| error_msg | TEXT | 에러 발생 시 메시지 |

### `trend_reports` — AI 분석 리포트

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL PK | |
| created_at | TEXT | UTC ISO 문자열 |
| game | TEXT | |
| period_start | TEXT | 분석 기간 시작 (`YYYY-MM-DD`) |
| period_end | TEXT | 분석 기간 종료 (`YYYY-MM-DD`) |
| summary | TEXT | 한 줄 요약 |
| category_filter | TEXT | 필터 에이전트 처리 결과 |
| category_translation | TEXT | 번역 에이전트 처리 결과 |
| category_classification | TEXT | 분류 에이전트 처리 결과 |
| category_analysis | TEXT | 분석 에이전트 처리 결과 |
| full_report | TEXT | 전체 리포트 마크다운 본문 |
| keywords | TEXT | 핵심 키워드 (콤마 구분 문자열, 조회 시 배열로 변환) |
| trend_level | TEXT | `hot` (급상승) / `rising` (상승) / `normal` (일반) |
| post_count | INTEGER | 분석에 사용된 게시글 수 |

---

## API 엔드포인트

백엔드: `http://localhost:8001` | Swagger UI: `http://localhost:8001/docs`

### 게시글

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/posts` | 게시글 목록 (DB 레벨 페이지네이션) |

쿼리 파라미터: `game`, `source`, `page` (기본 1), `limit` (기본 20, 최대 100)

```json
// 응답
{ "posts": [...], "total": 1234, "page": 1, "totalPages": 62 }
```

### 통계 & 로그

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/stats` | 전체·게임별·소스별 수집 건수, 마지막 크롤링 시각 |
| GET | `/logs` | 크롤링 실행 로그 최신순 (`?limit=50`) |

### 크롤링 & 리포트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/crawl` | 크롤러 즉시 실행 (비동기, 수 분 소요) |
| GET | `/reports` | 리포트 목록 (`?game=&limit=20`) |
| GET | `/reports/{id}` | 리포트 단건 조회 |
| POST | `/reports` | 리포트 저장 — AI 에이전트가 분석 완료 후 호출 |
| DELETE | `/reports/{id}` | 리포트 삭제 |

---

## 데이터 전처리

크롤러가 수집한 데이터는 `save_posts()` 호출 전 `preprocess.py`에서 자동으로 정제된다:

- **HTML 태그 제거** — title, content 필드
- **날짜 정규화** — ISO 8601, 슬래시 구분자, trailing Z, 타임존 오프셋 등 다양한 형식을 `YYYY-MM-DD` 또는 `YYYY-MM-DD HH:MM`으로 통일
- **빈 항목 필터링** — title 또는 url이 없는 항목 제거
- **공백 제거** — 모든 문자열 필드 strip
- **중복 방지** — url 기준 `ON CONFLICT DO NOTHING` (같은 글 재수집 시 자동 skip)

---

## 환경 설정

### 패키지 설치

```bash
cd backend && pip install -r requirements.txt && playwright install chromium
cd frontend && npm install
```

### `.env` 파일 생성 (프로젝트 루트 `CRAI/`)

```env
APIFY_API_TOKEN=apify_api_xxxxxxxxxxxxxxxx
DATABASE_URL=postgresql://user:password@your-rds-endpoint:5432/crai?sslmode=require
```

> `.env`는 `.gitignore`에 포함되어 있어 저장소에 올라가지 않는다. 직접 생성해야 함.

---

## 실행

### 백엔드

```bash
cd backend
uvicorn api.main:app --reload --port 8001
# Swagger UI → http://localhost:8001/docs
```

### 프론트엔드

```bash
cd frontend
npm run dev
# → http://localhost:3000
```

> 프론트엔드의 `/api/*` 요청은 `localhost:8001`로 프록시된다. 백엔드를 먼저 실행해야 한다.

### 스케줄러 (EC2 상시 가동)

```bash
cd backend
nohup python3 -m scheduler.scheduler > scheduler.log 2>&1 &
tail -f scheduler.log      # 로그 실시간 확인
ps aux | grep scheduler    # 실행 중인지 확인
kill <PID>                 # 중지
```

시작 즉시 1회 실행 후 6시간 간격으로 반복. 매 실행마다 30일 만료 posts와 로컬 JSON 파일 자동 삭제.

### 크롤러 수동 실행

```bash
cd backend
python -m pipeline.crawler_runner
```

---

## DB CLI

```bash
cd backend
python -m db.cli stats                                    # 전체·게임별·소스별 수집 통계
python -m db.cli posts                                    # 전체 게시글 조회
python -m db.cli posts --game lineage_m --source inven   # 필터 조회
python -m db.cli logs --limit 20                         # 크롤링 실행 로그
```

---

## EC2 서버

> 상세 설정 및 운영 가이드: **[ec2.md](./ec2.md)**

| 항목 | 값 |
|------|-----|
| OS | Ubuntu 24.04 LTS |
| 인스턴스 타입 | t3.small (us-east-1) |
| 접속 | SSH with `.pem` key / VSCode Remote SSH / AWS EC2 Instance Connect |

```powershell
# Windows PowerShell
ssh -i "C:\path\to\key.pem" ubuntu@<EC2_PUBLIC_IP>
```

> **주의:** 장기간 미사용 시 AWS 콘솔에서 **중지(Stop)** 해둘 것. 종료(Terminate)는 인스턴스와 데이터가 삭제되므로 절대 금지.

---

## 역할 분담

| 담당 | 브랜치 | 작업 내용 |
|------|--------|----------|
| 팀장 (서연지) | `main` / `crawler` | 전체 아키텍처 설계, 크롤러 파이프라인, FastAPI 백엔드, AWS 인프라 구축, AI 에이전트 (예정) |
| 팀원 A (정빈) | `scheduler-db` | AWS RDS 연동, 데이터 전처리, 30일 만료 처리, 크롤링 로그, 스케줄러, DB CLI |
| 팀원 B (은수) | `dashboard` | Next.js 대시보드, 수집 현황 차트, 게시글 테이블, AI 리포트 UI, 필터·페이지네이션 |

### 개발 일정

| 주차 | 진행 내용 |
|------|----------|
| 1~2주차 | 기획 확정, 개발 환경 셋팅, 크롤러 프로토타입, DB 설계 |
| 3~5주차 | 데이터 파이프라인 안정화, 대시보드 구축, AWS 연동 완성 **(중간발표)** |
| 6~9주차 | AI 에이전트 파이프라인 구현 (필터·번역·분류·분석·보고서) |
| 10~11주차 | 통합 테스트, 오탐률 최적화, 최종 데모 빌드 완성 **(최종발표)** |

---

## 구현 현황

### ✅ 완료 (3~5주차)

- [x] **프로젝트 아키텍처** — backend / frontend 분리, EC2 + RDS 배포 환경 구성
- [x] **Reddit 크롤러** — 리니지 시리즈 4개 서브레딧, LineageOS 키워드 자동 필터링
- [x] **Bilibili 크롤러** — 6개 게임 × 다국어 키워드, 중국어 게시글 수집
- [x] **인벤 크롤러** — 6개 게임 자유게시판, crawl4ai + Playwright, KST 날짜 파싱, 상세 페이지 본문 수집
- [x] **Bahamut 크롤러** — 대만 Bahamut 커뮤니티, crawl4ai + Playwright, 6개 게임 게시판 수집
- [x] **크롤링 파이프라인** — Reddit/Bilibili 병렬 실행 + 인벤/Bahamut 순차 실행, RDS 자동 저장, 중복 skip
- [x] **데이터 전처리** — HTML 태그 제거, 날짜 형식 통일, 빈 항목 필터
- [x] **DB 연동** — AWS RDS PostgreSQL, posts / crawl_logs / trend_reports 테이블
- [x] **스케줄러** — EC2 상시 가동, 6시간 정기 실행, 30일 만료 데이터 자동 삭제
- [x] **FastAPI 백엔드** — `/posts` (DB 레벨 페이지네이션), `/stats`, `/logs`, `/crawl`, `/reports`
- [x] **Next.js 대시보드** — 수집 현황 차트, 게임·소스·카테고리 필터, 게시글 테이블, 수동 크롤링 버튼
- [x] **AI 리포트 UI** — 리포트 카드, AI 분석 텍스트, 근거 게시글 연결, 상세 리포트 (더미 데이터로 완성)
- [x] **이슈 카테고리 설계** — 3개 플랫폼 실제 수집 데이터 분석 기반 4개 분류 체계 확정

### ✅ 완료 (6~9주차 진행 중)

- [x] **필터 에이전트** — 리니지 무관·질문/공략·잡담 제거, Claude Haiku API 활용
- [x] **번역 에이전트** — 중국어·영어 → 한국어, 게임 고유명사 보존, inven 스킵
- [x] **분류 에이전트** — 핵/봇 · 업데이트 · 시세/거래 · 여론 자동 분류
- [x] **파이프라인 통합** — `run_pipeline.py`로 3개 에이전트 순차 실행, 결과 로컬 JSON 저장

### ⏳ 진행 예정 (6~9주차)

- [ ] **분석 에이전트** — 트렌드 감지, 이상 징후 탐지, 위험도 평가
- [ ] **보고서 에이전트** — 최종 리포트 생성 및 DB 저장
- [ ] **Validator** — 각 에이전트 출력 검증, 실패 시 재시도 로직
- [ ] **대시보드 연동** — 더미 데이터 → 실제 `/reports` API 연결
- [ ] **EC2 프록시 적용** — EC2 IP가 기업 IP로 인식되어 봇 차단 발생, 프록시 서버 연동 방안 검토 중
- [ ] **아웃링크 분석** — Reddit/Inven 등 게시글 내 외부 링크 수집 및 분류 시각화
- [ ] **이미지 크롤링** — 빌리빌리·TikTok 인플루언서 이미지 수집 (패션/뷰티 트렌드 방향 확장 검토)

---

## 이슈 로그

### Discord 크롤링 시도 (2025-05 중간발표 이후)

리니지 관련 Discord 서버(`1133423963771519176`) 메시지 수집 시도.

- **시도한 방법:** Discord Bot API (공식) — Bot 생성 완료, 토큰 발급 완료
- **문제:** 해당 서버에서 팀원이 일반 멤버 권한만 보유 → Bot 초대 불가 (서버 관리자 권한 필요)
- **결론:** 보류. 서버 관리자에게 Bot 초대 요청하거나 다른 Discord 서버로 대상 변경 필요
- **참고:** Discord Public API는 실제로 존재하나, Bot이 해당 서버에 초대되어 있어야만 메시지 읽기 가능

---

## 멘토링 피드백 (중간발표 이후)

| 항목 | 피드백 내용 |
|------|------------|
| **EC2 크롤링 차단** | EC2는 기업 IP로 인식되어 봇 차단 빈번. 프록시 사용 검토 필요 |
| **403 봇 차단** | 억지로 뚫으려 하지 말 것. 우회 방향(프록시 등)으로 전환 |
| **Discord** | Public API 존재하나 Bot 초대 필요. 퍼블릭 API 기반으로 접근 |
| **Crawl4AI 활용** | 처음 보는 도메인/아웃링크 → Crawl4AI로 1차 파싱 → CSS 셀렉터 규칙 자동 추출로 발전 |
| **프로젝트 방향** | 텍스트 외 이미지 크롤링(빌리빌리, TikTok 인플루언서) + 패션/뷰티 도메인 확장 검토 |
| **다음 멘토링 전** | UI/UX 화면 먼저 구성해서 미리 멘토에게 전달할 것 |
| **robots.txt** | 법적 강제력 없는 가이드라인. 실제 법적 문제는 과도한 요청·대용량 데이터 무단 수집에서 발생 |
| **GitHub 관리** | 프로젝트 디스크립션·README 구성 우수 — 칭찬받음 |
