from typing import TypedDict, Optional
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class CRAIState(TypedDict):
    # Scout
    data_count: int
    retry_count: int
    posts: list[dict]

    # Vision
    captioning_done: bool

    # Report
    trend_titles: list[str]
    summary: str
    top_keywords: list[str]
    style_trends: list[dict]

    # Critic
    validation_passed: bool
    report_id: Optional[int]
    error_messages: list[str]
