# CRAI — Couture Retrieval AI

> 패션 인플루언서·브랜드 데이터를 자율적으로 수집·분석하여  
> **전문가 수준의 트렌드 리포트를 생성하는 Agentic AI 시스템**

---

## 프로젝트 개요

CRAI(Couture Retrieval AI)는 Instagram 인플루언서와 H&M 등 브랜드의 패션 이미지를 수집하고, Claude Vision API로 캡셔닝 후 벡터 임베딩 기반 시맨틱 검색과 멀티 에이전트 트렌드 리포트 생성을 제공하는 패션 인텔리전스 플랫폼이다.

단순한 데이터 수집을 넘어, 데이터 부족 감지 → 자율 보충 → 편향 검수 → 분석 → 리포트 생성을 하나의 **자율 루프**로 연결하는 Agentic 워크플로우를 목표로 한다.

---

## 핵심 특징

| | |
|---|---|
| **멀티소스 수집** | Instagram 인플루언서 + 브랜드 계정 (Instaloader), H&M 웹 스크래핑 |
| **Claude Vision 캡셔닝** | 실루엣·소재·컬러·스타일 속성을 한국어 전문 용어로 3~4문장 기술 |
| **시맨틱 검색** | `paraphrase-multilingual-MiniLM-L12-v2` 384차원 벡터 + pgvector 유사도 검색 |
| **멀티 에이전트 리포트** | Planner → Writer 2단계 에이전트가 트렌드 제목 선정 후 분석문 작성 |
| **Self-Correction** | JSON 파싱 실패 시 재시도 로직 내장 |
| **Next.js 대시보드** | 검색, 리포트 조회, 수집 현황 통계 UI |

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| **백엔드** | Python 3.10+, FastAPI, APScheduler |
| **프론트엔드** | Next.js 14 (App Router), TypeScript, Tailwind CSS, Recharts |
| **DB** | PostgreSQL + pgvector (AWS RDS) |
| **크롤링** | Instaloader (Instagram), crawl4ai (H&M 등 브랜드 웹) |
| **AI — 텍스트** | Claude Haiku 4.5 (필터·번역·분류·리포트 생성) |
| **AI — 이미지** | Claude Vision Haiku 4.5 (패션 이미지 캡셔닝) |
| **임베딩** | SentenceTransformers `paraphrase-multilingual-MiniLM-L12-v2` (384차원) |
| **인프라** | AWS EC2 t3.small (us-east-1), AWS RDS PostgreSQL |

---

## 시스템 아키텍처

### 현재 구현된 파이프라인

```
[Instagram / H&M 브랜드]
        │
        │  수동 실행 / API 트리거
        ▼
[instagram_collector.py / brand_scraper.py]
        │  이미지 URL, 캡션, 메타데이터
        ▼
[fashion_posts 테이블 (PostgreSQL)]
        │
        ├──▶ [fashion_captioner.py]   ← Claude Vision API
        │         caption_ai 필드 생성 (비동기, 동시 5개)
        │
        └──▶ [embedder.py]            ← SentenceTransformers
                  embedding 필드 생성 (배치 200개)
        │
        ▼
[FastAPI]
   ├── GET /search?q=…  → pgvector 유사도 검색 → 상위 20개 반환
   ├── POST /fashion-reports/generate → 리포트 생성 (백그라운드 태스크)
   └── GET /fashion-reports → 생성된 리포트 목록
        │
        ▼
[Next.js 대시보드]
   ├── 검색 탭: 키워드 검색 → 이미지 카드 그리드
   ├── 리포트 탭: 트렌드 리포트 목록 + 상세 보기
   └── 대시보드 탭: 수집 현황 통계
```

### 리포트 생성 에이전트 (현재)

```
[fashion_posts에서 캡션 62개 무작위 샘플링]
        │
        ▼
[Planner Agent] — Claude Haiku
   입력: 캡션 목록
   출력: 트렌드 제목 5개 + 선정 근거
        │
        ▼
[Writer Agent] — Claude Haiku (트렌드별 반복)
   입력: 트렌드 제목 + 관련 캡션
   출력: 분석문 2~3문장 + 대표 이미지 ID 2개
        │
   JSON 파싱 실패 시 → 자동 재시도 (최대 3회)
        │
        ▼
[fashion_reports 테이블 저장]
```

---

## 목표 아키텍처: LangGraph 기반 Agentic 워크플로우

### 설계 동기

현재 파이프라인의 세 가지 한계를 해결하기 위해 LangGraph 기반 자율 에이전트 시스템으로 전환을 계획한다.

| 문제 | 현상 | 해결 방향 |
|------|------|-----------|
| **Autonomy 부족** | 데이터 부족 시 수동으로 크롤러를 재실행해야 함 | Scout Agent가 자율 판단 후 재수집 |
| **데이터 편향** | 수집 데이터가 특정 성별/스타일에 편중될 수 있음 | Diversity Auditor가 편향 감지 후 수집 파라미터 조정 |
| **출력 신뢰성** | JSON 깨짐, 날짜 환각(2026→2024 오인) 발생 | Critic Agent가 문법·날짜 정합성 최종 검수 |

### LangGraph State 정의

```python
from typing import TypedDict, Optional

class CRAIState(TypedDict):
    # 수집 단계
    target_days: int                    # 분석 대상 기간 (기본 14일)
    raw_data: list[dict]               # fashion_posts 쿼리 결과
    data_count: int                     # 유효 이미지 수
    bias_filter_params: dict           # Diversity Auditor가 쓰는 재수집 파라미터
    
    # 처리 단계
    analyzed_captions: list[dict]      # Vision Agent 처리 완료 캡션 목록
    trend_report: Optional[dict]       # Writer가 생성한 리포트 초안
    
    # 검수·메타
    bias_logs: list[str]               # 편향 감지 로그
    error_messages: list[str]          # 에러 메시지 누적
    retry_count: int                   # 현재 루프 재시도 횟수 (무한루프 방지)
    validation_passed: bool            # Critic Agent 검수 통과 여부
```

### 에이전트 노드 구성

```
[시작: 목표 기간 설정]
        │
        ▼
┌─────────────────────────────┐
│  Scout Agent                │  DB에서 fashion_posts 조회
│  - 캡션 있는 이미지 수 확인  │  → data_count 기록
│  - 50개 미만 시 재수집 판단  │
└─────────────────────────────┘
        │
        ├── data_count < 50 AND retry < 3  ──▶ [크롤러 재실행] ──▶ Scout 재진입
        │
        ├── data_count < 50 AND retry >= 3 ──▶ 경고 로그 후 계속 진행
        │
        ▼ (데이터 충분)
┌─────────────────────────────┐
│  Diversity Auditor          │  캡션 기반 성별/스타일 분포 분석
│  - 남성복/여성복/중성 비율   │  → 편향 시 bias_filter_params 기록
│  - 스타일 다양성 확인        │  → 경고 로그 후 계속 진행 (재수집 안 함)
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  Vision Agent               │  caption_ai NULL인 이미지만 처리
│  - Claude Vision API 캡셔닝  │  (기존 캡션 있으면 스킵)
│  - 비동기 동시 5개 처리      │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  Couture MD (Planner)       │  캡션 샘플링 → 트렌드 제목 5개 선정
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  Couture MD (Writer)        │  트렌드별 분석문 + 대표 이미지 매칭
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  Critic Agent               │  JSON 문법 검사
│  - JSON 파싱 가능 여부       │  + 날짜 2026년 정합성 확인
│  - 날짜 환각(2024년) 감지    │
└─────────────────────────────┘
        │
        ├── 검수 실패 AND retry < 3 ──▶ Writer로 복귀 (재작성)
        │
        ▼ (검수 통과)
[fashion_reports 저장 → Next.js 렌더링]
```

### 핵심 설계 원칙

- **무한루프 방지**: 모든 루프에 `retry_count` 상한(3회) 적용. 초과 시 현재 상태로 강제 진행
- **Vision Agent 중복 방지**: `caption_ai IS NOT NULL`인 이미지는 API 호출 스킵
- **Diversity Auditor 역할 제한**: 편향 감지 후 재수집 트리거가 아닌 `bias_logs` 기록만 수행. 수집 대상(계정 목록) 자체의 편향은 Scout이 해결할 수 없음
- **날짜 환각 1차 방지**: 모든 에이전트 시스템 프롬프트에 `현재 날짜: 2026년 5월` 명시. Critic은 2차 검수

---

## 프로젝트 구조

```
CRAI/
├── .env                              # API 키 및 DB 연결 정보 (git 제외)
├── .env.example                      # 환경변수 템플릿
├── config/
│   ├── instagram_accounts.json       # 수집 대상 브랜드 + 인플루언서 계정 목록
│   └── brand_urls.json               # 브랜드 웹사이트 URL 목록
│
├── backend/
│   ├── requirements.txt
│   ├── api/
│   │   ├── main.py                   # FastAPI 앱 진입점 (CORS, 라우터 등록, DB 초기화)
│   │   └── routers/
│   │       ├── posts.py              # GET /posts — 게시글 목록
│   │       ├── stats.py              # GET /stats, GET /logs
│   │       ├── crawl.py              # POST /crawl — 크롤러 즉시 실행
│   │       ├── reports.py            # GET·POST·DELETE /reports
│   │       ├── search.py             # GET /search — 벡터 유사도 검색
│   │       └── fashion_reports.py    # GET /fashion-reports, POST /fashion-reports/generate
│   ├── crawlers/
│   │   ├── instagram_collector.py    # Instaloader, 브랜드+인플루언서, 60일 룩백
│   │   ├── brand_scraper.py          # H&M 등 브랜드 웹 스크래핑
│   │   ├── reddit_crawler.py         # Apify, 리니지 서브레딧 (레거시)
│   │   ├── bilibili_crawler.py       # Apify, 중국어 키워드 (레거시)
│   │   ├── inven_crawler.py          # crawl4ai + Playwright (레거시)
│   │   └── bahamut_crawler.py        # crawl4ai + Playwright (레거시)
│   ├── pipeline/
│   │   ├── run_fashion_pipeline.py   # 패션 파이프라인 실행 진입점
│   │   ├── fashion_captioner.py      # Claude Vision 캡셔닝 (비동기, 동시 5개)
│   │   ├── embedder.py               # SentenceTransformers 배치 임베딩 (200개 단위)
│   │   ├── report_generator.py       # Planner→Writer 멀티 에이전트 리포트 생성
│   │   ├── preview_report.py         # 리포트 미리보기 (HTML 출력)
│   │   ├── crawler_runner.py         # 크롤러 병렬 실행 오케스트레이터
│   │   ├── filter_agent.py           # 리니지 무관 게시글 필터 (레거시)
│   │   ├── translate_agent.py        # 다국어 → 한국어 번역 (레거시)
│   │   ├── classify_agent.py         # 카테고리 분류 (레거시)
│   │   └── run_pipeline.py           # 레거시 파이프라인 실행 진입점
│   ├── scheduler/
│   │   └── scheduler.py              # APScheduler, 6시간 간격, 30일 만료 처리
│   ├── db/
│   │   ├── database.py               # PostgreSQL + pgvector ORM, 테이블 초기화, CRUD
│   │   ├── preprocess.py             # HTML 태그 제거, 날짜 정규화
│   │   └── cli.py                    # 터미널 DB 조회 도구
│   └── utils/
│       └── config.py                 # 환경변수 로드
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx                  # 메인 대시보드 (검색·리포트·통계 탭)
│   │   ├── layout.tsx
│   │   ├── globals.css
│   │   └── api/                      # Next.js → FastAPI 프록시 라우트
│   │       ├── posts/route.ts
│   │       ├── stats/route.ts
│   │       ├── crawl/route.ts
│   │       ├── search/route.ts
│   │       └── fashion-reports/route.ts
│   ├── components/
│   │   ├── Navbar.tsx                # 탭 내비게이션
│   │   ├── SearchBar.tsx             # 키워드 검색 + 기간 필터
│   │   ├── ImageCard.tsx             # 패션 이미지 카드 (유사도·캡션·메타)
│   │   ├── TrendReport.tsx           # 트렌드 리포트 카드
│   │   ├── Sidebar.tsx               # 필터 사이드바
│   │   ├── StatsChart.tsx            # 수집 현황 차트 (Recharts)
│   │   └── PostsTable.tsx            # 게시글 테이블
│   └── lib/
│       └── gameLabels.ts
│
└── backend/data/                     # 크롤링 원시 데이터 로컬 백업 (30일 자동 삭제)
    ├── reddit/{game}/
    ├── bilibili/{game}/
    ├── inven/{game}/
    └── results/                      # 파이프라인 출력 JSON
```

---

## DB 스키마

### `fashion_posts` — 패션 이미지 데이터

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL PK | |
| source | TEXT | `instagram` / `hm` 등 |
| account_name | TEXT | 인플루언서·브랜드 계정명 |
| post_url | TEXT UNIQUE | 중복 방지 키 |
| image_url | TEXT | 이미지 원본 URL |
| caption | TEXT | 원본 캡션 |
| caption_ai | TEXT | Claude Vision 생성 한국어 캡션 |
| embedding | vector(384) | SentenceTransformers 벡터 |
| likes | INTEGER | |
| posted_at | TIMESTAMP | |
| created_at | TIMESTAMP | |

### `fashion_reports` — 생성된 트렌드 리포트

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL PK | |
| created_at | TIMESTAMP | |
| period_days | INTEGER | 분석 기간 (일) |
| summary | TEXT | 한 줄 요약 |
| full_report | TEXT | 전체 마크다운 리포트 |
| image_count | INTEGER | 분석에 사용된 이미지 수 |

### `posts` — 커뮤니티 게시글 (레거시, 리니지 트렌드용)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL PK | |
| url | TEXT UNIQUE | |
| title, content | TEXT | |
| game | TEXT | `lineage_classic` 등 6종 |
| source | TEXT | `reddit` / `bilibili` / `inven` / `bahamut` |
| category | TEXT | 분류 에이전트 결과 |
| translated_title, translated_content | TEXT | 번역 에이전트 결과 |
| raw | TEXT | 원본 JSON 백업 |
| created_at | TEXT | 30일 만료 기준 |

---

## API 엔드포인트

백엔드: `http://localhost:8001` | Swagger UI: `http://localhost:8001/docs`

### 패션 (주요)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/search?q=키워드&days=60` | 벡터 유사도 검색, 상위 20개 반환 |
| GET | `/fashion-reports` | 트렌드 리포트 목록 |
| POST | `/fashion-reports/generate` | 리포트 생성 (백그라운드 태스크) |

### 공통

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/posts` | 게시글 목록 (페이지네이션) |
| GET | `/stats` | 수집 통계 |
| GET | `/logs` | 크롤링 실행 로그 |
| POST | `/crawl` | 크롤러 즉시 실행 |
| GET/POST/DELETE | `/reports` | 리포트 CRUD |

---

## 구현 현황

### ✅ 완료

**데이터 수집**
- [x] Instagram 수집기 — Instaloader, 브랜드+인플루언서 계정, 60일 룩백
- [x] H&M 브랜드 스크래퍼 — 상품 이미지 및 메타데이터 수집
- [x] Reddit / Bilibili / 인벤 / Bahamut 크롤러 (리니지 커뮤니티)

**AI 파이프라인**
- [x] Claude Vision 캡셔닝 — `fashion_captioner.py`, 비동기 동시 5개, 한국어 전문 용어
- [x] SentenceTransformers 임베딩 — 384차원, 배치 200개, pgvector 저장
- [x] 멀티 에이전트 리포트 생성 — Planner → Writer, Self-Correction (JSON 파싱 오류 재시도)
- [x] 필터 / 번역 / 분류 에이전트 — 리니지 커뮤니티 텍스트 처리

**백엔드·인프라**
- [x] FastAPI — 6개 라우터, pgvector 유사도 검색 엔드포인트
- [x] PostgreSQL + pgvector — fashion_posts, fashion_reports, posts, crawl_logs 테이블
- [x] APScheduler — 6시간 간격 수집, 30일 만료 자동 삭제
- [x] AWS EC2 + RDS 배포 환경

**프론트엔드**
- [x] Next.js 대시보드 — 검색 탭, 리포트 탭, 통계 탭
- [x] 시맨틱 검색 UI — ImageCard 그리드, 유사도 점수 표시
- [x] 트렌드 리포트 UI — 마크다운 렌더링, 리포트 생성 버튼

### ⏳ 진행 예정

**LangGraph Agentic 워크플로우**
- [ ] `langgraph` 패키지 도입, `CRAIState` TypedDict 정의
- [ ] Scout Agent — DB 데이터 수 확인, 부족 시 크롤러 재실행 (retry 상한 3회)
- [ ] Diversity Auditor — 성별·스타일 분포 분석, `bias_logs` 기록
- [ ] Vision Agent — 기존 `fashion_captioner.py` LangGraph 노드로 래핑
- [ ] Couture MD (Planner + Writer) — 기존 `report_generator.py` 리팩터링
- [ ] Critic Agent — JSON 문법 검사 + 2026년 날짜 정합성 검수
- [ ] Conditional Edge 설계 — Critic 실패 시 Writer 복귀, Scout 재시도 루프

**기타**
- [ ] 프록시 서버 연동 — EC2 IP 봇 차단 대응
- [ ] 대시보드 실시간 업데이트 — 리포트 생성 진행 상태 표시

---

## 환경 설정

### 패키지 설치

```bash
cd backend && pip install -r requirements.txt
cd frontend && npm install
```

### `.env` 파일 (프로젝트 루트)

```env
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql://user:password@your-rds-endpoint:5432/crai?sslmode=require
APIFY_API_TOKEN=apify_api_...
```

---

## 실행

### 백엔드

```bash
cd backend
uvicorn api.main:app --reload --port 8001
```

### 프론트엔드

```bash
cd frontend
npm run dev
# → http://localhost:3000
```

### 패션 파이프라인 수동 실행

```bash
cd backend
# 1. Instagram 수집
python -m crawlers.instagram_collector

# 2. Claude Vision 캡셔닝 (caption_ai 없는 것만 처리)
python -m pipeline.fashion_captioner

# 3. 벡터 임베딩 생성
python -m pipeline.embedder

# 4. 트렌드 리포트 생성
python -m pipeline.report_generator
```

### 스케줄러

```bash
cd backend
nohup python3 -m scheduler.scheduler > scheduler.log 2>&1 &
```

---

## 역할 분담

| 담당 | 작업 내용 |
|------|----------|
| 팀장 (서연지) | 전체 아키텍처 설계, AI 파이프라인, 크롤러, FastAPI 백엔드, AWS 인프라, LangGraph 설계 |
| 팀원 A (정빈) | AWS RDS 연동, 데이터 전처리, 스케줄러, DB CLI |
| 팀원 B (은수) | Next.js 대시보드, 검색 UI, 리포트 UI, 차트 컴포넌트 |

### 개발 일정

| 주차 | 진행 내용 |
|------|----------|
| 1~2주차 | 기획 확정, 개발 환경 구성, 크롤러 프로토타입, DB 설계 |
| 3~5주차 | 데이터 파이프라인 안정화, 대시보드 구축, AWS 연동 **(중간발표)** |
| 6~9주차 | Claude Vision 캡셔닝, 임베딩, 시맨틱 검색, 멀티 에이전트 리포트 생성 |
| 10~11주차 | LangGraph Agentic 워크플로우, 통합 테스트, 최종 데모 **(최종발표)** |

---

## 이슈 로그

### EC2 봇 차단 (2026-05)

EC2 IP가 기업 IP로 인식되어 일부 사이트에서 403 차단 발생. 프록시 서버 연동 방안 검토 중.

### 멘토링 피드백 (중간발표 이후)

| 항목 | 피드백 |
|------|--------|
| EC2 크롤링 차단 | 프록시 사용 검토. 억지로 우회 시도하지 말 것 |
| 프로젝트 방향 | 텍스트 외 이미지 크롤링 + 패션/뷰티 도메인 확장 → 현재 피벗 완료 |
| UI/UX | 화면 먼저 구성 후 멘토 공유 |
| GitHub 관리 | README 구성 우수 — 칭찬받음 |
