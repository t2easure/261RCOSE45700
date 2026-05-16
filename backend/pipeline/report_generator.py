import sys
from pathlib import Path
import os
import json
import random
import re
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone, timedelta
import anthropic

# 경로 설정
sys.path.insert(0, str(Path(__file__).parent.parent))
from db.database import _get_connection

# [Step 1: 플래너 에이전트] 5개 트렌드 목차 선정
PLANNER_PROMPT = """당신은 수석 패션 MD 에이전트입니다. 
지금은 {year}년이며, 당신이 분석하는 데이터는 모두 {year}년의 최신 데이터입니다.
{count}개의 데이터를 분석하여 이번 시즌 가장 중요한 핵심 트렌드 제목 5개를 선정해 JSON으로 응답하세요.

[데이터]
{captions}

[JSON 양식]
{{
  "summary": "{year}년 시즌 전체 요약 (3줄)",
  "top_keywords": ["키워드1", "키워드2"],
  "trend_titles": ["트렌드1 제목", "트렌드2 제목", "트렌드3 제목", "트렌드4 제목", "트렌드5 제목"]
}}"""

# [Step 2: 라이터 에이전트] 각 트렌드 상세 분석 및 이미지 매칭
WRITER_PROMPT = """당신은 패션 리포트 작가 에이전트입니다. 
제시된 트렌드 제목에 대해 2~3문장의 상세 분석을 작성하고, 가장 잘 어울리는 이미지 ID 2개를 매칭하세요.
지금은 {year}년 시즌임을 명시하세요.

[트렌드 제목]: {title}
[참고 데이터]: {captions}

[JSON 양식]
{{
  "title": "{title}",
  "content": "트렌드 상세 설명 (전문 용어 사용)",
  "representative_ids": [ID1, ID2]
}}"""

def get_recent_captions(days: int = 14, sample: int = 200):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days))
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, caption_ai, account_name FROM fashion_posts WHERE caption_ai IS NOT NULL AND collected_at >= %s", (cutoff,))
            rows = cur.fetchall()
    if len(rows) > sample: rows = random.sample(rows, sample)
    return rows, cutoff.strftime("%Y-%m-%d"), datetime.now(timezone.utc).strftime("%Y-%m-%d")

def save_fashion_report(report_data: dict) -> int:
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO fashion_reports (period_start, period_end, summary, top_keywords, style_trends, brand_comparison, full_report, post_count, source_accounts)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (report_data["period_start"], report_data["period_end"], report_data["summary"], 
                 json.dumps(report_data["top_keywords"], ensure_ascii=False),
                 report_data["style_trends"], report_data["brand_comparison"], 
                 report_data["summary"], report_data["post_count"], json.dumps(report_data["source_accounts"], ensure_ascii=False))
            )
            report_id = cur.fetchone()[0]
        conn.commit()
    return report_id

def extract_text(response):
    """응답 객체에서 텍스트만 안전하게 추출 (리스트 에러 방지)"""
    full_text = ""
    for block in response.content:
        if hasattr(block, 'text'):
            full_text += block.text
        elif isinstance(block, dict) and 'text' in block:
            full_text += block['text']
    return full_text

def safe_json_parse(text):
    """JSON 블록만 찾아내어 파싱"""
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match: raise ValueError("JSON 형식을 찾을 수 없습니다.")
    return json.loads(re.sub(r'[\x00-\x1F\x7F]', '', match.group(0)))

def run_report_generator(days: int = 14):
    posts, p_start, p_end = get_recent_captions(days=days)
    if len(posts) < 5: return print(f"❌ 데이터 부족 ({len(posts)}개)")

    current_year = 2026
    captions_text = "\n".join([f"ID:{p['id']}|{p['caption_ai']}" for p in posts])
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    try:
        # 1단계: 플래너가 목차 구성
        print(f"🤖 [Step 1] 플래너 에이전트가 {current_year}년 트렌드를 기획 중...")
        plan_res = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            messages=[{"role": "user", "content": PLANNER_PROMPT.format(year=current_year, count=len(posts), captions=captions_text)}]
        )
        plan_data = safe_json_parse(extract_text(plan_res))
        
        # 2단계: 라이터가 각 트렌드별 상세 분석 (Agentic Loop)
        print(f"✅ 기획 완료! {len(plan_data['trend_titles'])}개의 트렌드를 상세 분석합니다.")
        final_trends = []
        for title in plan_data['trend_titles']:
            print(f"🤖 [Step 2] 라이터 에이전트가 '{title}' 분석 중...")
            writer_res = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1000,
                messages=[{"role": "user", "content": WRITER_PROMPT.format(year=current_year, title=title, captions=captions_text)}]
            )
            final_trends.append(safe_json_parse(extract_text(writer_res)))

        # 저장
        report_id = save_fashion_report({
            "period_start": p_start, "period_end": p_end,
            "summary": plan_data['summary'],
            "top_keywords": plan_data['top_keywords'],
            "style_trends": json.dumps(final_trends, ensure_ascii=False),
            "brand_comparison": "종합 분석 완료",
            "post_count": len(posts),
            "source_accounts": list({p["account_name"] for p in posts}),
        })

        print(f"✨ [Success] 에이전트 리포트 완성! (ID: {report_id})")
        return report_id

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return 0

if __name__ == "__main__":
    run_report_generator()