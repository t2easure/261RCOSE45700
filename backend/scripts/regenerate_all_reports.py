"""
기존 fashion_reports의 기간(period_start~period_end)을 그대로 유지한 채
전체 리포트를 삭제 후 오래된 기간부터 순서대로 재생성한다.
트렌드명 연속성 매칭(_trend_agent의 직전 리포트 비교)이 시간 순서에 의존하므로
반드시 오래된 기간부터 생성해야 한다.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import _get_connection
from pipeline.multi_agent_pipeline import run_multi_agent_pipeline


def get_existing_periods() -> list[tuple[str, str]]:
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT period_start, period_end FROM fashion_reports "
                "WHERE period_start IS NOT NULL AND period_end IS NOT NULL "
                "ORDER BY period_start ASC"
            )
            rows = cur.fetchall()
    return [(str(r[0]), str(r[1])) for r in rows]


def delete_all_reports():
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM fashion_reports")
        conn.commit()


def main():
    periods = get_existing_periods()
    print(f"[재생성] 대상 기간 {len(periods)}개")
    for s, e in periods:
        print(f"  - {s} ~ {e}")

    if not periods:
        print("재생성할 리포트가 없습니다.")
        return

    delete_all_reports()
    print("[재생성] 기존 리포트 전체 삭제 완료")

    for i, (start_date, end_date) in enumerate(periods, 1):
        print(f"\n[{i}/{len(periods)}] {start_date} ~ {end_date} 생성 중...")
        try:
            report_id = run_multi_agent_pipeline(start_date=start_date, end_date=end_date)
            print(f"  -> 완료 (id={report_id})")
        except Exception as e:
            print(f"  -> 실패: {e}")

    print("\n[재생성] 전체 완료")


if __name__ == "__main__":
    main()
