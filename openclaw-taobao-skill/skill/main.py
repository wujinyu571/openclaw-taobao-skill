from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from skill.config import get_settings
from skill.core.orchestrator import SkillOrchestrator
from skill.models import TaskPayload


def setup_logger() -> logging.Logger:
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("taobao_skill")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        file_handler = logging.FileHandler(logs_dir / "run.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
    return logger


def parse_task_text(text: str, default_keyword: str, default_rating: float, default_max_items: int) -> TaskPayload:
    payload = TaskPayload(
        keyword=default_keyword,
        min_positive_rate=default_rating,
        max_items=default_max_items,
    )
    if not text:
        return payload
    parts = [part for part in text.split(";") if "=" in part]
    data = dict(part.split("=", 1) for part in parts)
    if "search" in data:
        payload.keyword = data["search"]
    if "rating" in data:
        payload.min_positive_rate = float(data["rating"])
    if "max_items" in data:
        payload.max_items = int(data["max_items"])
    if "task_id" in data:
        payload.task_id = data["task_id"]
    return payload


async def run(task_text: str | None = None, headful: bool = False) -> dict:
    settings = get_settings()
    logger = setup_logger()
    orchestrator = SkillOrchestrator(settings=settings, logger=logger.info)
    payload = parse_task_text(
        task_text or "",
        default_keyword=settings.default_keyword,
        default_rating=settings.default_min_positive_rate,
        default_max_items=settings.default_max_items,
    )
    if headful:
        payload.headful = True
    result = await orchestrator.run(payload if task_text else None)
    result_dict = orchestrator.result_to_dict(result)
    logger.info("Run result: %s", json.dumps(result_dict, ensure_ascii=False))
    return result_dict


def main() -> None:
    parser = argparse.ArgumentParser(description="Taobao UI automation skill runner")
    parser.add_argument("--task", type=str, default="", help='Format: "search=索尼耳机;rating=99;max_items=3"')
    parser.add_argument("--headful", action="store_true", help="Run browser in headful mode")
    args = parser.parse_args()

    result = asyncio.run(run(task_text=args.task, headful=args.headful))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
