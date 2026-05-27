import sys
from pathlib import Path
import json
import psycopg2.extras

# 경로 설정
sys.path.insert(0, str(Path(__file__).parent.parent))
from db.database import _get_connection

def generate_visual_report():
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 1. 가장 최신 리포트 가져오기
            cur.execute("SELECT * FROM fashion_reports ORDER BY created_at DESC LIMIT 1")
            report = cur.fetchone()
            
            if not report:
                print("❌ 생성된 리포트가 없습니다.")
                return

            # 2. 트렌드 JSON 파싱
            trends = json.loads(report['style_trends'])
            
            # 3. HTML 뼈대 구축
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>CRAI Trend Report</title>
                <style>
                    body {{ background: #F2E8DC; font-family: 'Pretendard', sans-serif; padding: 40px; color: #333; }}
                    .container {{ max-width: 900px; margin: 0 auto; background: white; padding: 40px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }}
                    h1 {{ color: #5A2E1E; border-bottom: 2px solid #5A2E1E; padding-bottom: 10px; }}
                    .summary {{ background: #F9F3ED; padding: 20px; border-left: 5px solid #D4A373; margin: 20px 0; line-height: 1.6; font-style: italic; }}
                    .keyword-tag {{ display: inline-block; background: #E7D8C9; padding: 5px 15px; border-radius: 20px; margin: 5px; font-size: 14px; font-weight: bold; }}
                    .trend-section {{ margin-top: 50px; border-top: 1px solid #eee; pt: 30px; }}
                    .trend-title {{ font-size: 24px; color: #8C5E45; margin-bottom: 15px; }}
                    .trend-content {{ line-height: 1.7; margin-bottom: 20px; }}
                    .image-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
                    .image-card img {{ width: 100%; border-radius: 10px; aspect-ratio: 3/4; object-fit: cover; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>CRAI AI Fashion Trend Report</h1>
                    <p><strong>분석 기간:</strong> {report['period_start']} ~ {report['period_end']} ({report['post_count']}개 데이터 기반)</p>
                    
                    <div class="summary">{report['summary']}</div>
                    
                    <div>
                        {" ".join([f'<span class="keyword-tag">#{k}</span>' for k in json.loads(report['top_keywords'])])}
                    </div>
            """

            # 4. 각 트렌드별 루프 돌며 사진 채우기
            for trend in trends:
                raw_ids = trend.get('representative_ids', [])
                
                # 💡 [핵심 수정] 'ID:264' 형태의 문자열에서 숫자만 추출하여 정수로 변환합니다.
                ids = []
                for rid in raw_ids:
                    try:
                        # 숫자가 아닌 문자(ID:)를 제거하고 정수로 변환
                        clean_id = int(str(rid).replace('ID:', '').strip())
                        ids.append(clean_id)
                    except ValueError:
                        continue

                images_html = ""
                if ids:
                    # 정제된 숫자 ID 리스트를 쿼리에 전달합니다.
                    cur.execute("SELECT image_url FROM fashion_posts WHERE id IN %s", (tuple(ids),))
                    imgs = cur.fetchall()
                    for img in imgs:
                        images_html += f'<div class="image-card"><img src="{img["image_url"]}"></div>'
                        
                html_content += f"""
                <div class="trend-section">
                    <h2 class="trend-title">✨ {trend['title']}</h2>
                    <p class="trend-content">{trend['content']}</p>
                    <div class="image-grid">{images_html}</div>
                </div>
                """

            html_content += """
                </div>
            </body>
            </html>
            """

            with open("report_preview.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            print("✅ 'report_preview.html'이 생성되었습니다. 브라우저에서 확인하세요!")

if __name__ == "__main__":
    generate_visual_report()