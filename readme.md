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
| **멀티소스 수집** | Instagram 한국 인플루언서 (Instaloader) + H&M·유니클로 브랜드 룩북 (Playwright) |
| **Claude Vision 캡셔닝** | 실루엣·소재·컬러·스타일 속성을 한국어 전문 용어로 캡셔닝 (`caption_ai`) |
| **2차 메타 캡셔닝** | 전문용어 캡션을 일반화 키워드 5~8개로 압축 (`caption_meta`) |
| **시맨틱 검색** | `paraphrase-multilingual-MiniLM-L12-v2` 384차원 벡터 + pgvector 유사도 검색 |
| **LangGraph 에이전트** | Scout → Vision → Couture MD (Planner+Writer) → Critic → Save 자동화 파이프라인 |
| **Self-Correction** | JSON 파싱 실패 및 데이터 부족 시 자동 재시도 (최대 3회) |
| **Next.js 대시보드** | 시맨틱 검색, 트렌드 리포트 조회, 전체 이미지 브라우징 UI |

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| **백엔드** | Python 3.10+, FastAPI |
| **프론트엔드** | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| **DB** | PostgreSQL + pgvector |
| **크롤링** | Instaloader (Instagram), Playwright + playwright-stealth (브랜드 웹) |
| **AI — 이미지** | Claude Vision API (1차 전문용어 캡셔닝) |
| **AI — 메타** | Claude API (2차 일반화 키워드 추출) |
| **AI — 리포트** | Claude API + LangGraph (Scout·Vision·Couture MD·Critic 에이전트) |
| **임베딩** | SentenceTransformers `paraphrase-multilingual-MiniLM-L12-v2` (384차원) |

---

## 시스템 아키텍처

```
[Instagram 인플루언서]     [H&M / 유니클로 브랜드 사이트]
         │                              │
         │  Instaloader                 │  Playwright + Stealth
         ▼                              ▼
[instagram_collector.py]      [brand_scraper.py]
  - 브랜드: 30일 룩백            - H&M, 유니클로, ZARA
  - 인플루언서: 60일 룩백         - 이미지 로컬 저장
  - 팔로워/댓글 수 수집           - 중복 skip
         │                              │
         └──────────────┬───────────────┘
                        ▼
            [fashion_posts 테이블 (PostgreSQL)]
                        │
           ┌────────────┼────────────┐
           ▼            ▼            ▼
[fashion_captioner]  [meta_captioner]  [embedder.py]
 Claude Vision API   Claude API        SentenceTransformers
 caption_ai 생성     caption_meta 생성  embedding(384) 생성
 (전문용어 캡션)      (일반화 키워드)
           │
           ▼
[langgraph_pipeline.py] ← LangGraph Agentic 파이프라인
  Scout → Vision → Couture MD → Critic → Save
           │
           ▼
       [FastAPI]
  ├── GET  /search              → pgvector 유사도 검색
  ├── GET  /posts               → 전체 이미지 목록 (소스 필터, 페이지네이션)
  ├── GET  /stats               → 수집 통계
  ├── POST /fashion-reports/generate → 리포트 생성 (백그라운드)
  └── GET  /fashion-reports          → 리포트 목록
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
[meta_captioner.py]  Claude API
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
   [Vision 노드]  caption_ai NULL 이미지 캡셔닝
         ▼
   [Couture MD 노드]  Planner → 트렌드 5개 선정
                      Writer  → 키워드별 분석문 + 대표 이미지 매칭
         ▼
   [Critic 노드]  summary / 트렌드 5개 완비 검증
         ├── 실패 → Couture MD 재시도 (최대 3회)
         └── 통과 →
               ▼
         [Save 노드]  fashion_reports 테이블 저장
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
│   │       └── fashion_reports.py # GET/POST /fashion-reports
│   ├── crawlers/
│   │   ├── instagram_collector.py # Instaloader, 세션 인증, 브랜드 30일/인플루언서 60일
│   │   └── brand_scraper.py       # Playwright + Stealth, H&M·유니클로·ZARA 스크래핑
│   ├── pipeline/
│   │   ├── run_fashion_pipeline.py # 파이프라인 실행 진입점
│   │   ├── fashion_captioner.py    # Claude Vision 1차 캡셔닝 (비동기, 동시 5개)
│   │   ├── meta_captioner.py       # Claude 2차 캡셔닝 — 일반화 키워드 추출
│   │   ├── embedder.py             # SentenceTransformers 배치 임베딩
│   │   ├── langgraph_pipeline.py   # LangGraph Scout/Vision/Couture MD/Critic/Save
│   │   └── report_generator.py     # 기존 Planner→Writer 멀티 에이전트 리포트
│   ├── utils/
│   │   └── image_downloader.py     # 이미지 로컬 저장 (MD5 해시 중복 방지)
│   └── db/
│       └── database.py             # PostgreSQL + pgvector CRUD
│
└── frontend/
    ├── app/
    │   ├── page.tsx              # 메인 (대시보드·검색·리포트·전체이미지 탭)
    │   └── api/                  # Next.js → FastAPI 프록시
    │       ├── posts/route.ts
    │       ├── stats/route.ts
    │       ├── search/route.ts
    │       ├── crawl/route.ts
    │       └── fashion-reports/route.ts
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
| full_report | TEXT | 전체 리포트 |
| post_count | INTEGER | 분석에 사용된 이미지 수 |
| source_accounts | TEXT | 출처 계정 목록 (JSON) |

---

## API

백엔드: `http://localhost:8001` | Swagger: `http://localhost:8001/docs`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/stats` | 수집 통계 (전체·소스별) |
| GET | `/posts?source=&limit=&offset=` | 전체 이미지 목록 |
| GET | `/search?q=키워드&days=60` | 벡터 유사도 검색 |
| GET | `/fashion-reports` | 트렌드 리포트 목록 |
| POST | `/fashion-reports/generate` | 리포트 생성 (백그라운드) |

---

## 구현 현황

### ✅ 완료

- Instagram 수집기 — Instaloader 세션 인증, 브랜드 30일/인플루언서 60일 룩백, 팔로워·댓글 수 수집
- 브랜드 스크래퍼 — Playwright + Stealth, H&M·유니클로·ZARA·탑텐·스파오
- 이미지 로컬 저장 — MD5 해시 기반 중복 방지
- Claude Vision 1차 캡셔닝 — 비동기 동시 5개, 한국어 전문 용어, 계정당 50개 제한
- Claude 2차 메타 캡셔닝 — 전문용어 → 일반화 키워드 5~8개 추출
- SentenceTransformers 임베딩 — 384차원, 배치 처리, pgvector 저장
- LangGraph 파이프라인 — Scout / Vision / Couture MD 노드 구현
- 기존 멀티 에이전트 리포트 — Planner → Writer, Self-Correction
- FastAPI — `/search`, `/posts`, `/stats`, `/fashion-reports` 엔드포인트
- Next.js 대시보드 — 대시보드, 검색, 리포트, 전체 이미지 탭

### ⏳ 예정

**AI 파이프라인**
- LangGraph Critic / Save 노드 + 그래프 조립 완성

**프론트**
- 리포트 생성 진행 상태 실시간 표시

---

## 실행

```bash
# 백엔드
cd backend
uvicorn api.main:app --reload --port 8001

# 프론트엔드
cd frontend
npm run dev   # → http://localhost:3000

# 패션 파이프라인 수동 실행
cd backend
python -m crawlers.brand_scraper          # 브랜드 이미지 수집
python -m crawlers.instagram_collector    # 인플루언서 이미지 수집
python -m pipeline.fashion_captioner      # Claude Vision 1차 캡셔닝
python -m pipeline.meta_captioner         # Claude 2차 메타 키워드 추출
python -m pipeline.embedder               # 임베딩 생성
python -m pipeline.langgraph_pipeline     # LangGraph 에이전트 파이프라인 실행
```

### 환경변수 (`.env`)

```env
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql://user:password@host:5432/crai
```
