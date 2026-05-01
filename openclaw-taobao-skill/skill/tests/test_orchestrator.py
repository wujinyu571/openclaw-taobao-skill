import pytest

from skill.config import Settings
from skill.core.orchestrator import SkillOrchestrator
from skill.models import RunResult, TaskPayload


class FakeRunner:
    async def run(self, payload: TaskPayload) -> RunResult:
        return RunResult(
            run_id="run-1",
            task_id=payload.task_id,
            success=True,
            message="OK",
            added_to_cart_count=2,
        )


class FakeFeishu:
    def __init__(self) -> None:
        self.pushed = False

    async def pull_task(self) -> TaskPayload:
        return TaskPayload(task_id="remote-1")

    async def push_result(self, result: RunResult) -> None:
        self.pushed = True


@pytest.mark.asyncio
async def test_orchestrator_run_with_payload() -> None:
    orchestrator = SkillOrchestrator(Settings(), logger=lambda _: None)
    orchestrator.runner = FakeRunner()
    fake_feishu = FakeFeishu()
    orchestrator.feishu = fake_feishu

    result = await orchestrator.run(TaskPayload(task_id="task-1"))
    assert result.success is True
    assert result.task_id == "task-1"
    assert fake_feishu.pushed is True


@pytest.mark.asyncio
async def test_orchestrator_pull_task_when_payload_missing() -> None:
    orchestrator = SkillOrchestrator(Settings(), logger=lambda _: None)
    orchestrator.runner = FakeRunner()
    fake_feishu = FakeFeishu()
    orchestrator.feishu = fake_feishu

    result = await orchestrator.run(None)
    assert result.task_id == "remote-1"
