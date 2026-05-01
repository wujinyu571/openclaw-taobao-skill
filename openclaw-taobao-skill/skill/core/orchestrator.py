from __future__ import annotations

from dataclasses import asdict
from typing import Any

from skill.config import Settings
from skill.core.taobao_runner import TaobaoRunner
from skill.integrations.feishu_client import FeishuClient
from skill.models import RunResult, TaskPayload


class SkillOrchestrator:
    def __init__(self, settings: Settings, logger) -> None:
        self.settings = settings
        self.logger = logger
        self.feishu = FeishuClient(settings)
        self.runner = TaobaoRunner(settings, logger)

    async def run(self, payload: TaskPayload | None = None) -> RunResult:
        task = payload or await self.feishu.pull_task()
        self.logger(f"Start task: {task.task_id}")
        result = await self.runner.run(task)
        await self._try_push_result(result)
        self.logger(f"Finish task: {task.task_id}, success={result.success}, msg={result.message}")
        return result

    async def _try_push_result(self, result: RunResult) -> None:
        try:
            await self.feishu.push_result(result)
        except Exception as exc:  # noqa: BLE001
            self.logger(f"Push result failed: {exc}")

    @staticmethod
    def result_to_dict(result: RunResult) -> dict[str, Any]:
        return asdict(result)
