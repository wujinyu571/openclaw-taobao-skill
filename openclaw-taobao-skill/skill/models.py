from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class TaskPayload:
    task_id: str = "local-debug-task"
    keyword: str = "索尼耳机"
    min_positive_rate: float = 99.0
    headful: bool = False
    max_items: int = 3


@dataclass
class ItemResult:
    title: str
    price: str
    positive_rate: float


@dataclass
class RunResult:
    run_id: str
    task_id: str
    success: bool
    message: str
    matched_items: list[ItemResult] = field(default_factory=list)
    added_to_cart_count: int = 0
    artifacts: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z"))
