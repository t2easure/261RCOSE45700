# CRAI — Curated Reference AI

> **패션 MD의 수동 트렌드 모니터링을 AI로 자동화**  
> 인플루언서·브랜드 이미지 자동 수집 → AI 캡셔닝 → 트렌드 클러스터링 → 주간·월간 리포트 자동 생성

서비스: http://107.22.8.250/

---

## 문제 정의

| 현재 MD 업무 | 문제점 |
|---|---|
| 인플루언서 SNS 수십 개 계정 수동 모니터링 | 시간 소모 과다 |
| 트렌드 파악 후 리포트 작성 | 주관적 판단, 비정형 데이터 |
| 소싱 타이밍 포착 | 경쟁 브랜드 선점 여부 파악 어려움 |

패션 트렌드 정보가 분산되어 있고, 구조화된 인사이트로 전환하는 과정이 전부 수동이다.

---

## 최종 목표

```
인플루언서·브랜드 이미지 자동 수집
         ↓
AI 이미지 캡셔닝 (카테고리별 구조화)
         ↓
트렌드 클러스터링
         ↓
MD 소싱 결정에 활용 가능한 주간·월간 트렌드 리포트 자동 생성
```

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| AI / LLM | Claude (Vision, Haiku) |
| 에이전트 오케스트레이션 | LangGraph |
| 벡터 DB | PostgreSQL + pgvector |
| 백엔드 | FastAPI |
| 프론트엔드 | Next.js 14 |
| 배포 | AWS EC2, PM2 |
| 크롤링 | Playwright |
| 임베딩 | SentenceTransformers (`paraphrase-multilingual-MiniLM-L12-v2`, 384차원) |

---

## 전체 파이프라인

```
[Instagram 인플루언서]        [H&M / ZARA / UNIQLO / TOPTEN / SPAO]
         │                                  │
         │  Playwright                      │  Playwright
         ▼                                  ▼
[instagram_playwright.py]         [brand_scraper.py]
  - 세션 인증 기반 수집              - 이미지 URL 수집
  - 마지막 크롤 이후 포스트만 수집    - 중복 URL 조기 종료
         │                                  │
         └─────────────────┬────────────────┘
                           ▼
               [fashion_posts (PostgreSQL)]
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
  [fashion_captioner]  [meta_captioner]  [embedder]
  Claude Vision        Claude Haiku      SentenceTransformers
  카테고리별 구조화      유사 키워드 포함    embedding(384) 저장
  캡션 + few-shot      키워드 추출
                           │
                           ▼
              [multi_agent_pipeline.py]
              LangGraph 멀티에이전트 파이프라인
              → 트렌드 리포트 자동 생성
                           │
                           ▼
                       [FastAPI]
                           │
                           ▼
                   [Next.js 대시보드]
```

### 자동 실행 스케줄

| 시간 | 작업 |
|------|------|
| 매일 02:00 | 크롤링 → 캡셔닝 → 메타태깅 → 임베딩 |
| 매주 월요일 03:00 | 주간 트렌드 리포트 자동 생성 |
| 매월 말일 04:00 | 월간 트렌드 리포트 자동 생성 |

---

## 핵심 기능

### 시맨틱 이미지 검색

사용자가 자연어 또는 이미지로 원하는 스타일을 검색한다.

**RRF 기반 하이브리드 검색**
```
RRF_score(d) = Σ 1 / (k + rank_i(d))   (k=60)

벡터 검색 순위 + 키워드 검색 순위를 RRF로 합산
```

- **벡터 검색**: 사용자 검색어를 sentence-transformer로 변환 후 cosine similarity
- **키워드 검색**: Claude가 검색어를 관련 키워드로 확장 후 caption_ai 매칭
- 두 검색 결과의 순위를 RRF로 결합 → 단위 차이 없이 공정한 합산

> 기존 단순 가중합(벡터 0.7 + 키워드 0.3) 방식의 단위 불일치 문제를 RRF로 해결

**검색 방식**
- 자연어 쿼리 검색 ("와이드 데님 캐주얼")
- 이미지 업로드 → Claude Vision 분석 → 유사 스타일 검색
- 브랜드 / 인플루언서 계정별 필터
- 멀티 키워드 조합 검색

---

### AI 캡셔닝

#### 1차 캡셔닝 (fashion_captioner.py)
Claude Vision으로 이미지를 카테고리별로 구조화 분석:

```
[스타일] 미니멀 캐주얼
[실루엣] 오버사이즈
[컬러] 아이보리, 베이지
[소재] 코튼, 린넨
[아이템] 와이드 슬랙스, 크롭 반팔티, 크로스백
[디테일] 톤온톤 배색, 루즈핏
[설명] 기본 아이템들의 톤온톤 조합으로 완성한 미니멀 캐주얼 스타일입니다.
```

- 여성 패션 외 이미지 자동 SKIP (브랜드 로고, 남성복, 음식 등)
- few-shot 예제 포함으로 일관된 출력 형식 유지

#### 2차 메타 캡셔닝 (meta_captioner.py)
1차 캡션에서 검색용 키워드 추출 + 유사어 확장:

```
입력: [컬러] 베이지
출력: 베이지, 아이보리, 크림, 뉴트럴
```

색상·소재의 유사어까지 포함해 검색 커버리지 확대.

---

### 트렌드 리포트

#### K-means 기반 스타일 클러스터링
- 해당 기간 전체 포스트 임베딩 벡터를 K-means로 클러스터링
- 클러스터별 대표 이미지 3장 (중심점 최근접 순)
- 비슷한 스타일을 그룹 단위로 파악 → 소싱 방향 설정에 실용적

#### 브랜드 포화도
```
브랜드 포화도 = 브랜드 포스트 수 / 클러스터 전체 포스트 수

> 0.4 : 이미 선점됨 (브랜드 포화)
< 0.2 : 소싱 기회 (브랜드 미진입)
```
※ Instagram 브랜드 계정 + Lookbook 소스 포스트를 브랜드로 분류

경쟁 브랜드가 선점한 트렌드를 파악하고, 지금 소싱 가능한지 빠르게 판단.

#### 인플루언서 선행 지수
```
선행 지수 = 브랜드 첫 게시일 - 인플루언서 첫 게시일

> 0      : 인플루언서가 브랜드보다 먼저 올린 트렌드
브랜드 미출현 : 선행 트렌드 (소싱 선점 기회)
```
인플루언서가 먼저 입고 있다는 것 = 수요 신호 → 브랜드 진입 전에 소싱하면 선점 가능.

#### 트렌드 신호 강도
```
signal = volume_score   (포스트 수 / 50 × 3,              max 3)
       + eng_score      (avg_engagement_rate / 0.02 × 3,  max 3)
       + brand_score    ((1 - brand_ratio) × 2,           max 2)
       + lead_score     (days_ahead / 30 × 2,             max 2)

급상승 : signal >= 8
성장중 : signal >= 5
주목   : signal >= 3
약세   : signal < 3

engagement_rate = (likes + comments) / followers
```

- `volume_score`: 인플루언서 15명 × 월평균 3~4회 포스팅 기준 분모 50 설정
- `eng_score`: RivalIQ 기준 인스타그램 상위권 engagement rate 2% 기준 (평균 1.59%)
- `brand_score`: 브랜드 미진입일수록 초기 트렌드 → 높은 점수
- `lead_score`: 30일을 한 달 리포트 주기 기준으로 설정

여러 트렌드 중 MD가 어디에 먼저 집중해야 할지 우선순위를 단일 점수로 제공.

#### 리포트 탭 메인
- 캡션 기반 트렌드 키워드 워드클라우드
- 주간 급상승 트렌드 / 월별 TOP 트렌드 요약

---

### 관리 메뉴 (Manage 탭)

MD가 수집 대상을 직접 관리:
- Instagram 인플루언서 / 브랜드 계정 추가·삭제
- 브랜드 룩북 URL 추가·삭제

---

## 핵심 이슈 및 해결

| 이슈 | 해결 |
|------|------|
| EC2에서 Instaloader IP 차단 | Playwright 세션 기반 크롤러로 교체 |
| 벡터/키워드 점수 단위 불일치 | RRF(Reciprocal Rank Fusion)로 순위 기반 합산 |
| 캡션 키워드 매칭 부정확 | 카테고리별 구조화 + 유사어 확장으로 개선 |
| 시계열 트렌드 히스토리 | 3월부터 데이터 축적 중, 충분해지면 구현 예정 |

---

## 구현 현황

### 완료

- 브랜드 스크래퍼 — Playwright, H&M·ZARA·UNIQLO·탑텐·스파오, 중복 URL 조기 종료
- Instagram 크롤러 — Playwright 세션 인증, 마지막 크롤 이후 포스트만 수집
- Claude Vision 1차 캡셔닝 — 카테고리별 구조화 출력, few-shot 예제, 여성 패션 외 자동 삭제
- Claude Haiku 2차 메타 캡셔닝 — 유사어 포함 검색 키워드 추출
- SentenceTransformers 임베딩 — 384차원, pgvector 저장
- RRF 기반 하이브리드 검색 — 벡터 + 키워드 순위 융합
- 이미지 업로드 검색 — Claude Vision 분석 후 유사 스타일 검색
- 멀티 키워드·필터 검색 — 소스·기간·계정 복수 조건
- LangGraph 멀티에이전트 파이프라인 — Scout → TrendAgent → EngagementAgent → LeadIndexAgent → Critic
- 트렌드 신호 강도 / 브랜드 포화도 / 인플루언서 선행 지수 산출
- 워드클라우드 시각화
- 수집 대상 관리 메뉴 (Manage 탭)
- 크롤링 원클릭 파이프라인 (새 데이터만 처리)
- 자동 스케줄러 — 매일 02:00 크롤링, 월요일 03:00 주간 리포트, 말일 04:00 월간 리포트
- AWS EC2 배포, PM2
- **브랜드 상세 상품 링크 크롤링** — 리스팅 페이지에서 실제 상품 상세 URL 수집
- **가격 크롤링** — 상세 페이지 방문 또는 리스팅 파싱으로 가격 자동 수집 (전 브랜드)
- **이미지 로컬 저장** — 만료 방지를 위한 EC2 로컬 다운로드 및 경로 저장
- **HEADLESS 환경변수** — 로컬(false)/EC2(true) 분리 운영
- **카드 상세 페이지 링크** — Data/Trends 탭 카드 클릭 시 브랜드 상품 페이지 또는 인스타 포스트로 이동
- **카드 메타데이터 표시** — 가격·소재·좋아요·참여율 카드에 직접 노출
- **CLIP 멀티모달 임베딩** — SentenceTransformer → CLIP(openai/clip-vit-base-patch32) 교체, 이미지 직접 임베딩
- **한국어 쿼리 번역** — Claude Haiku로 검색어 영어 변환 후 CLIP 인코딩 (색상·스타일 시각 매칭 개선)
- **BM25 키워드 검색** — LIKE → PostgreSQL ts_rank 교체, RRF로 벡터+키워드 융합
- **레이더 차트 가격 매력도** — 클러스터별 브랜드 평균가격 기반 (데이터 없으면 브랜드 미진입률로 추정)
- **인스타 캐러셀 전체 수집** — 다중 이미지 포스트 슬라이드별 개별 저장
- **Manage 탭 파이프라인 제어** — 캡셔닝/임베딩/크롤링 개별 실행, 배치사이즈 조절
- **인스타 수집 기준일 설정** — Manage 탭에서 날짜 직접 지정
- **Topten 리스팅 직접 수집** — 상세 페이지 방문 없이 리스팅 이미지+가격 수집 (EC2 IP 차단 우회)

### 진행 예정

- 소재 데이터 크롤링 (브랜드별 HTML 구조 파악 필요)
- 시계열 트렌드 히스토리 (데이터 축적 후)
- 경쟁사 브랜드 확대
- H&M·Zara EC2 크롤링 (headless 차단 이슈)

---

## 프로젝트 구조

```
CRAI/
├── .env
├── config/
│   ├── instagram_accounts.json
│   └── brand_urls.json
├── backend/
│   ├── api/
│   │   ├── main.py                   # FastAPI 앱, APScheduler 스케줄러
│   │   └── routers/
│   │       ├── search.py             # RRF 하이브리드 검색, 이미지 검색
│   │       ├── fashion_reports.py    # 트렌드 리포트 CRUD
│   │       ├── pipeline.py           # 캡셔닝·임베딩 트리거
│   │       ├── crawl.py              # 크롤링 트리거
│   │       └── config_manager.py    # 수집 대상 관리
│   ├── crawlers/
│   │   ├── brand_scraper.py          # Playwright 브랜드 크롤러
│   │   └── instagram_playwright.py   # Playwright 인스타그램 크롤러
│   ├── pipeline/
│   │   ├── fashion_captioner.py      # Claude Vision 1차 캡셔닝 (구조화)
│   │   ├── meta_captioner.py         # Claude Haiku 2차 메타태깅 (유사어 확장)
│   │   ├── embedder.py               # SentenceTransformers 임베딩
│   │   └── multi_agent_pipeline.py   # LangGraph 트렌드 리포트
│   └── db/
│       └── database.py               # PostgreSQL + pgvector, RRF 검색
└── frontend/
    ├── app/page.tsx                   # 메인 대시보드 (Trends·Search·Reports·Data·Manage)
    └── components/
        └── TrendWordCloud.tsx
```

---

## DB 스키마

### `fashion_posts`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL PK | |
| source | VARCHAR(20) | `instagram` / `lookbook` |
| account_name | VARCHAR(100) | 계정명 |
| post_url | TEXT UNIQUE | 중복 방지 키 |
| image_url | TEXT | 이미지 URL |
| caption | TEXT | 원본 캡션 |
| likes / comments / followers | INTEGER | 인게이지먼트 지표 |
| posted_at | TIMESTAMP | 게시 시각 |
| collected_at | TIMESTAMP | 수집 시각 |
| caption_ai | TEXT | Claude Vision 1차 캡션 (카테고리 구조화) |
| caption_meta | TEXT | 검색용 키워드 (유사어 포함) |
| embedding | vector(384) | 시맨틱 검색용 벡터 |

### `fashion_reports`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL PK | |
| created_at | TIMESTAMP | |
| period_start / period_end | TEXT | 분석 기간 |
| summary | TEXT | 시즌 전체 요약 |
| top_keywords | TEXT | 핵심 키워드 (JSON) |
| style_trends | TEXT | 트렌드별 분석 + 대표 이미지 (JSON) |
| post_count | INTEGER | 분석 이미지 수 |

---

## 실행

```bash
# 백엔드
cd backend
uvicorn api.main:app --reload --port 8001

# 프론트엔드
cd frontend
npm run dev   # → http://localhost:3000
```

### 환경변수 (`.env`)

```env
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql://user:password@host:5432/crai
INSTAGRAM_USERNAME=...
INSTAGRAM_PASSWORD=...
```

### EC2 배포

```bash
git pull && pm2 restart crai-back
pm2 logs crai-back --lines 100
```
