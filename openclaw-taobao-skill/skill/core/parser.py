from __future__ import annotations

import re

POSITIVE_RATE_PATTERNS = [
    # 匹配 "好评率 99%" 或 "好评率:99.5%"
    re.compile(r"好评率[:：]?\s*(\d+(?:\.\d+)?)\s*%"),
    # 匹配 "99%好评"
    re.compile(r"(\d+(?:\.\d+)?)\s*%\s*好评"),
    # 匹配单纯的百分比，如 "98.5%" (通常出现在评分栏)
    re.compile(r"(?:满意度|评分|好评)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*%"),
]

# 匹配店铺动态评分，如 "4.9分"、"4.8高"
SHOP_SCORE_PATTERN = re.compile(r"(\d\.\d)\s*(?:分|高)")


def parse_positive_rate(text: str) -> float | None:
    normalized = (text or "").strip()
    if not normalized:
        return None

    # 1. 优先尝试匹配明确的好评率百分比
    for pattern in POSITIVE_RATE_PATTERNS:
        match = pattern.search(normalized)
        if match:
            return float(match.group(1))

    # 2. 兜底：匹配店铺评分并转换为百分制 (例如 4.9分 -> 98%)
    # 淘宝店铺分通常在 4.0-5.0 之间，乘以 20 即可映射到 80-100 分
    score_match = SHOP_SCORE_PATTERN.search(normalized)
    if score_match:
        score = float(score_match.group(1))
        if 3.0 <= score <= 5.0:
            return score * 20

    return None
