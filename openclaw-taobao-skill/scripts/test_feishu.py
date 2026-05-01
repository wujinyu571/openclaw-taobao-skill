"""
测试飞书 Webhook 消息推送
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from skill.config import get_settings
from skill.integrations.feishu_client import FeishuClient
from skill.models import RunResult, ItemResult


async def test_feishu_webhook():
    settings = get_settings()
    client = FeishuClient(settings)

    # 创建模拟结果
    result = RunResult(
        run_id="test-run-001",
        task_id="test-task-001",
        success=True,
        message="OK",
        matched_items=[
            ItemResult(title="Sony MDR-EX15LP 耳机", price="¥69", positive_rate=97.0),
            ItemResult(title="Sony MDR-EX255AP 耳机", price="¥159", positive_rate=96.0),
        ],
        added_to_cart_count=2,
        artifacts={"screenshot": "logs/test.png"}
    )

    print("Sending test message to Feishu...")
    await client.push_result(result)
    print("✅ Message sent! Check your Feishu group.")


if __name__ == "__main__":
    asyncio.run(test_feishu_webhook())
