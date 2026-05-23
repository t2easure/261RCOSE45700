# CRAI — Curated Reference AI

> **20대 여성**을 핵심 타겟으로, SPA 브랜드와 인플루언서 데이터를 자율 수집·분석하여  
> 패션 트렌드 리포트를 자동 생성하는 **Agentic AI 시스템**

---

## 프로젝트 개요

기존 패션 실무자들이 겪는 수동적 리서치와 주관적 판단의 한계를 극복하고자 기획한 시스템이다.  
H&M·유니클로 등 SPA 브랜드 공식 사이트와 한국 인플루언서 Instagram 계정에서 패션 이미지를 자동 수집하고, Claude Vision API로 1차 캡셔닝 → 일반화 메타 키워드 2차 캡셔닝 → 벡터 임베딩 기반 시맨틱 검색과 LangGraph 멀티 에이전트 트렌드 리포트 생성을 제공한다.

### 분석 대상이 SPA + 20대 여성 인플루언서인 이유

- **SPA/패스트패션**: 디자인 교체 주기가 빠르고 구매 빈도가 높아 트렌드 신호가 가장 빠르게 나타나는 카테고리
- **20대 여성**: 패션 온라인 구매율 72.4% (오픈서베이), 패션 브랜드 구매자 중 44.7% (토스애즈) — 단순 화제성이 아니라 실제 커머스 전환과 직결되는 세그먼트
- **Instagram**: 20대 이용률 80.9% (한국언론진흥재단), 패션 구매 시 SNS 콘텐츠 영향 75% (패션비즈 2025) — 핵심 채널

---

## 핵심 기능

| | |
|---|---|
| **멀티소스 수집** | Instagram 한국 인플루언서 (Instaloader) + H&M·유니클로·ZARA·탑텐·스파오 브랜드 룩북 (Playwright) |
| **Claude Vision 캡셔닝** | 실루엣·소재·컬러·스타일 속성을 한국어 전문 용어로 캡셔닝 (`caption_ai`), 패션 아닌 이미지 자동 삭제 |
| **2차 메타 캡셔닝** | 전문용어 캡션을 일반화 키워드 5~8개로 압축 (`caption_meta`) |
| **하이브리드 검색** | 벡터 유사도(70%) + 키워드 매칭(30%) 결합, Claude 쿼리 확장으로 검색 품질 향상 |
| **LangGraph 에이전트** | Scout → Couture MD (Planner+Writer) → Critic 자동화 파이프라인, DB 저장 |
| **Self-Correction** | Critic 노드: 데이터 부족·JSON 파싱 실패 시 Couture MD로 자동 재시도 (최대 3회) |
| **Next.js 대시보드** | 시맨틱 검색, 트렌드 리포트 조회, 전체 이미지 브라우징 UI |
| **크롤링 원클릭 파이프라인** | 크롤 버튼 클릭 → 수집 → 1차 캡셔닝 → 2차 캡셔닝 → 임베딩 자동 순차 실행, 새로 수집한 데이터만 처리 |
| **중복 수집 방지** | 브랜드 스크래퍼: DB에 이미 있는 URL 발견 시 즉시 조기 종료, Instagram: 마지막 크롤 시각 기준으로 이후 포스트만 수집 |
| **동적 키워드 태그** | 검색창 하단 키워드 칩을 caption_meta 빈도 기반으로 DB에서 실시간 추출 |
| **벡터 기반 대표 이미지** | 트렌드 리포트 대표 이미지를 Claude 선택이 아닌 트렌드 제목 pgvector 유사도 검색으로 자동 매칭 |
| **자연어 검색** | 키워드뿐 아니라 자연어 쿼리 입력 가능, Claude Haiku가 패션 키워드로 자동 확장 |
| **멀티 키워드 검색** | 검색창 하단 키워드 태그 복수 선택 시 조합 검색 (예: 미니멀 + 캐주얼 + 화이트) |
| **멀티 필터링** | 소스(Instagram/Lookbook), 기간, 계정을 복수 조건으로 검색 결과 필터링 |
| **리포트 기간 필터** | 리포트 생성 시 분석 기간 선택 (1일~전체), 해당 기간 포스트 수 실시간 확인 및 데이터 부족 경고 |
| **여성 패션 자동 필터링** | 캡셔닝 시 Claude가 남성복·아동복·패션 무관 이미지 판별 후 자동 삭제 |

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| **백엔드** | Python 3.10+, FastAPI |
| **프론트엔드** | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| **DB** | PostgreSQL + pgvector |
| **크롤링** | Instaloader (Instagram), Playwright + playwright-stealth (브랜드 웹) |
| **AI — 이미지** | Claude Vision API (1차 전문용어 캡셔닝) |
| **AI — 메타** | Claude Haiku API (2차 일반화 키워드 추출) |
| **AI — 리포트** | Claude Haiku API + LangGraph (Scout·Couture MD 에이전트) |
| **임베딩** | SentenceTransformers `paraphrase-multilingual-MiniLM-L12-v2` (384차원) |

---

## 시스템 아키텍처

```
[Instagram 인플루언서]     [H&M / 유니클로 브랜드 사이트]
         │                              │
         │  Instaloader                 │  Playwright + Stealth
         ▼                              ▼
[instagram_collector.py]      [brand_scraper.py]
  - 인플루언서: 60일 룩백         - H&M, 유니클로, ZARA
  - 팔로워/댓글 수 수집           - 이미지 로컬 저장 / 중복 skip
         │                              │
         └──────────────┬───────────────┘
                        ▼
            [fashion_posts 테이블 (PostgreSQL)]
                        │
           ┌────────────┼────────────┐
           ▼            ▼            ▼
[fashion_captioner]  [meta_captioner]  [embedder.py]
 Claude Vision API   Claude Haiku      SentenceTransformers
 caption_ai 생성     caption_meta 생성  embedding(384) 생성
 계정당 50개 제한    (일반화 키워드)
           │
           ▼
[langgraph_pipeline.py] ← LangGraph Agentic 파이프라인
  Scout → Couture MD (Planner+Writer) → DB 저장
           │
           ▼
       [FastAPI]
  ├── GET  /stats                          → 수집 통계
  ├── GET  /posts?source=&limit=&offset=   → 전체 이미지 목록
  ├── GET  /search?q=&days=&limit=         → pgvector 유사도 검색
  ├── GET  /fashion-reports                → 리포트 목록
  ├── GET  /fashion-reports/{id}           → 리포트 상세
  ├── GET  /fashion-reports/generate/status → 리포트 생성 진행 상태
  ├── POST /fashion-reports/generate       → LangGraph 리포트 생성 (백그라운드)
  ├── GET  /pipeline/status                → 파이프라인 실행 상태
  ├── POST /pipeline/caption               → 1차 캡셔닝 실행 (since 필터 지원)
  ├── POST /pipeline/meta                  → 2차 메타 캡셔닝 실행 (since 필터 지원)
  ├── POST /pipeline/embed                 → 임베딩 실행 (since 필터 지원)
  ├── POST /crawl                          → 브랜드+Instagram 크롤링 실행 (백그라운드)
  └── GET  /logs                           → 크롤링 로그 조회
           │
           ▼
     [Next.js 대시보드]
  ├── 대시보드: 최근 수집 이미지 + 통계
  ├── 검색: 키워드 → 이미지 그리드 (유사도 점수)
  ├── 리포트: AI 트렌드 리포트 목록 + 상세
  └── 전체 이미지: All / Instagram / Lookbook 필터
```

### AI 캡셔닝 파이프라인

```
이미지
  │
  ▼
[fashion_captioner.py]  Claude Vision API
  caption_ai 저장 — "오버사이즈 실루엣의 베이지 린넨 셔츠. 루즈한 핏과..."
  │
  ▼
[embedder.py]  SentenceTransformers
  embedding(384) 저장 — 시맨틱 검색용 벡터
  │
  ▼
[meta_captioner.py]  Claude Haiku API
  caption_meta 저장 — "오버사이즈, 린넨, 베이지, 캐주얼, 셔츠, 와이드팬츠"
```

### LangGraph Agentic 파이프라인

```
[시작]
   │
   ▼
[Scout 노드]  caption_ai 완료 포스트 수 확인
   ├── 50개 미만 → 재시도 (최대 3회)
   └── 충분 →
         ▼
   [Couture MD 노드]  Planner → 트렌드 5개 선정
                      Writer  → 키워드별 분석문 + 대표 이미지 매칭
         ▼
   [DB 저장]  fashion_reports 테이블 저장
```

---

## 프로젝트 구조

```
CRAI/
├── .env                          # API 키 및 DB 연결 정보 (git 제외)
├── config/
│   ├── instagram_accounts.json   # 수집 대상 인플루언서/브랜드 계정 목록
│   └── brand_urls.json           # 브랜드 웹사이트 URL (H&M, 유니클로 등)
│
├── backend/
│   ├── requirements.txt
│   ├── api/
│   │   ├── main.py               # FastAPI 앱 (CORS, 라우터, /stats, /posts)
│   │   └── routers/
│   │       ├── search.py         # GET /search — 벡터 유사도 검색
│   │       ├── fashion_reports.py # GET/POST /fashion-reports
│   │       └── pipeline.py       # GET|POST /pipeline/* — 파이프라인 트리거·상태
│   ├── crawlers/
│   │   ├── instagram_collector.py # Instaloader, 세션 인증, 인플루언서 60일 룩백
│   │   └── brand_scraper.py       # Playwright + Stealth, H&M·유니클로·ZARA 스크래핑
│   ├── pipeline/
│   │   ├── fashion_captioner.py   # Claude Vision 1차 캡셔닝 (비동기, 동시 5개)
│   │   ├── meta_captioner.py      # Claude Haiku 2차 캡셔닝 — 일반화 키워드 추출
│   │   ├── embedder.py            # SentenceTransformers 배치 임베딩
│   │   └── langgraph_pipeline.py  # LangGraph Scout / Couture MD 노드
│   ├── utils/
│   │   └── image_downloader.py    # 이미지 로컬 저장 (MD5 해시 중복 방지)
│   └── db/
│       └── database.py            # PostgreSQL + pgvector CRUD
│
└── frontend/
    ├── app/
    │   ├── page.tsx              # 메인 (대시보드·검색·리포트·전체이미지 탭)
    │   └── api/                  # Next.js → FastAPI 프록시
    │       ├── posts/route.ts
    │       ├── stats/route.ts
    │       ├── search/route.ts
    │       ├── fashion-reports/route.ts
    │       ├── fashion-reports/generate/route.ts
    │       └── pipeline/
    │           ├── status/route.ts
    │           ├── caption/route.ts
    │           ├── meta/route.ts
    │           └── embed/route.ts
    └── components/
        ├── Navbar.tsx
        ├── SearchBar.tsx
        ├── ImageCard.tsx
        └── CrawlButton.tsx
```

---

## DB 스키마

### `fashion_posts`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL PK | |
| source | VARCHAR(20) | `instagram` / `lookbook` |
| account_name | VARCHAR(100) | 인플루언서·브랜드 계정명 |
| post_url | TEXT UNIQUE | 중복 방지 키 |
| image_url | TEXT | 이미지 원본 URL |
| caption | TEXT | 원본 캡션 |
| likes | INTEGER | 좋아요 수 |
| comments | INTEGER | 댓글 수 |
| followers | INTEGER | 팔로워 수 |
| posted_at | TIMESTAMP | 게시 시각 |
| collected_at | TIMESTAMP | 수집 시각 |
| caption_ai | TEXT | Claude Vision 1차 캡션 (전문용어) |
| caption_meta | TEXT | Claude 2차 캡션 (일반화 키워드) |
| meta_at | TIMESTAMP | 2차 캡셔닝 시각 |
| captioned_at | TIMESTAMP | 1차 캡셔닝 시각 |
| embedding | vector(384) | SentenceTransformers 벡터 |

### `fashion_reports`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL PK | |
| created_at | TIMESTAMP | |
| period_start / period_end | TEXT | 분석 기간 |
| summary | TEXT | 시즌 전체 요약 |
| top_keywords | TEXT | 핵심 키워드 (JSON) |
| style_trends | TEXT | 트렌드별 분석문 + 대표 이미지 (JSON) |
| post_count | INTEGER | 분석에 사용된 이미지 수 |

---

## API

백엔드: `http://localhost:8001` | Swagger: `http://localhost:8001/docs`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/stats` | 수집 통계 (전체·소스별) |
| GET | `/posts?source=&limit=&offset=` | 전체 이미지 목록 (caption_meta 포함) |
| GET | `/search?q=키워드&days=60&sources=instagram,lookbook&accounts=계정명` | 하이브리드 검색 (벡터 70% + 키워드 30%) + Claude 쿼리 확장 + 멀티 필터 |
| GET | `/search/accounts` | 수집된 계정 목록 조회 |
| GET | `/fashion-reports/count?days=30` | 기간별 캡셔닝 완료 포스트 수 조회 |
| GET | `/fashion-reports` | 트렌드 리포트 목록 |
| GET | `/fashion-reports/{id}` | 트렌드 리포트 상세 |
| GET | `/fashion-reports/generate/status` | 리포트 생성 진행 상태 |
| POST | `/fashion-reports/generate` | LangGraph 리포트 생성 (백그라운드) |
| GET | `/keywords?limit=10` | caption_meta 빈도 기준 상위 키워드 목록 |
| GET | `/posts/by-ids?ids=1,2,3` | ID 목록으로 이미지 일괄 조회 |
| GET | `/pipeline/status` | 파이프라인 실행 상태 |
| POST | `/pipeline/caption` | 1차 캡셔닝 실행 (since: ISO 날짜 필터) |
| POST | `/pipeline/meta` | 2차 메타 캡셔닝 실행 (since: ISO 날짜 필터) |
| POST | `/pipeline/embed` | 임베딩 실행 (since: ISO 날짜 필터) |
| POST | `/crawl` | 브랜드+Instagram 크롤링 실행 (백그라운드) |
| GET | `/logs` | 크롤링 로그 조회 |

---

## 구현 현황

### ✅ 완료

- Instagram 수집기 — Instaloader 세션 인증, 마지막 크롤 시각 기준 이후 포스트만 수집
- 브랜드 스크래퍼 — Playwright + Stealth, H&M·유니클로·ZARA·탑텐·스파오, 중복 URL 조기 종료
- 이미지 로컬 저장 — MD5 해시 기반 중복 방지
- Claude Vision 1차 캡셔닝 — 비동기 동시 5개, 한국어 전문 용어, 계정당 50개 제한, 패션 아닌 이미지 자동 삭제
- Claude Haiku 2차 메타 캡셔닝 — 전문용어 → 일반화 키워드 5~8개 추출
- SentenceTransformers 임베딩 — 384차원, 배치 처리, pgvector 저장
- LangGraph 파이프라인 — Scout → Couture MD (Planner+Writer) → Critic 노드 + DB 저장
- Critic 노드 — 트렌드 5개 완비·summary 유무 검증, 실패 시 Couture MD 재시도 (최대 3회)
- 크롤링 원클릭 파이프라인 — 버튼 클릭 → 수집 → 1차·2차 캡셔닝 → 임베딩 자동 순차 실행, since 필터로 새 데이터만 처리
- 하이브리드 검색 — 벡터 유사도(70%) + 키워드 매칭(30%) 결합, Claude 쿼리 확장 적용
- 멀티 키워드 검색 — 검색창 하단 키워드 태그 복수 선택 후 조합 검색
- 멀티 필터링 — 소스·기간·계정 복수 조건 필터 (검색 탭)
- 여성 패션 자동 필터링 — 캡셔닝 시 남성복·무관 이미지 자동 삭제
- 동적 키워드 태그 — caption_meta 빈도 기반 상위 키워드를 DB에서 실시간 추출해 검색창 하단에 표시
- 벡터 기반 대표 이미지 매칭 — 트렌드 제목을 벡터화해 pgvector로 가장 유사한 이미지 자동 선정
- FastAPI — 전체 이미지·검색·통계·리포트·파이프라인 트리거·크롤링·로그·키워드·ID조회 엔드포인트
- Next.js 대시보드 — Trends(대시보드), Search, Reports, Data 탭
- 이미지 카드 hover 시 전체 캡션 오버레이 표시

---

## 실행

```bash
# 백엔드
cd backend
uvicorn api.main:app --reload --port 8001

# 프론트엔드
cd frontend
npm run dev   # → http://localhost:3000

# 파이프라인 수동 실행
cd backend
python -m crawlers.brand_scraper          # 브랜드 이미지 수집
python -m crawlers.instagram_collector    # 인플루언서 이미지 수집
python -m pipeline.fashion_captioner      # Claude Vision 1차 캡셔닝
python -m pipeline.meta_captioner         # Claude Haiku 2차 메타 키워드 추출
python -m pipeline.embedder               # 임베딩 생성
python -m pipeline.langgraph_pipeline     # LangGraph 파이프라인 실행
```

### 환경변수 (`.env`)

```env
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql://user:password@host:5432/crai
```
