"""
飞书客户端 - 支持真实 API 集成
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import asdict
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from skill.config import Settings
from skill.models import RunResult, TaskPayload


class FeishuClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.access_token = None
        self.token_expire_time = 0

    def _get_access_token(self) -> str:
        """获取或刷新 access_token"""
        if not self.settings.feishu_app_id or not self.settings.feishu_app_secret:
            # 如果没有配置 OAuth，返回空（使用 Webhook 模式）
            return ""

        # 检查 token 是否过期
        current_time = time.time()
        if self.access_token and current_time < self.token_expire_time:
            return self.access_token

        # 请求新的 access_token
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.settings.feishu_app_id,
            "app_secret": self.settings.feishu_app_secret
        }

        try:
            response = httpx.post(url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 0:
                self.access_token = data["tenant_access_token"]
                expire = data.get("expire", 7200)
                self.token_expire_time = current_time + expire - 60  # 提前1分钟刷新
                return self.access_token
            else:
                raise Exception(f"Failed to get access token: {data}")
        except Exception as e:
            print(f"Warning: Could not get access token: {e}")
            return ""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def pull_task(self) -> TaskPayload:
        """
        从飞书拉取任务

        支持两种模式：
        1. Webhook 模式：返回默认任务（需要外部触发）
        2. OAuth 模式：从指定群聊读取最新消息作为任务
        """
        import time
        from datetime import datetime

        # 模式1：使用 OAuth 从群聊读取任务
        if self.settings.feishu_app_id and self.settings.feishu_chat_id:
            try:
                task = await self._pull_task_from_chat()
                if task:
                    return task
            except Exception as e:
                print(f"Failed to pull task from chat: {e}")

        # 模式2：返回默认任务（fallback），但生成唯一ID
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        unique_id = f"auto-{timestamp}"

        return TaskPayload(
            task_id=unique_id,
            keyword=self.settings.default_keyword,
            min_positive_rate=self.settings.default_min_positive_rate,
            max_items=self.settings.default_max_items,
            headful=not self.settings.headless,
        )

    async def _pull_task_from_chat(self) -> TaskPayload | None:
        """从群聊最新消息中解析任务"""
        access_token = self._get_access_token()
        if not access_token:
            return None

        # 获取群聊消息列表
        url = f"https://open.feishu.cn/open-apis/im/v1/messages?container_id_type=chat&container_id={self.settings.feishu_chat_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            if data.get("code") != 0 or not data.get("data", {}).get("items"):
                return None

            # 获取最新消息
            latest_msg = data["data"]["items"][0]
            msg_content = latest_msg.get("body", {}).get("content", "")

            # 解析任务参数
            # 期望格式：@机器人 搜索索尼耳机 好评率95 数量3
            return self._parse_task_from_message(msg_content, latest_msg.get("message_id"))

    def _parse_task_from_message(self, content: str, message_id: str) -> TaskPayload | None:
        """从消息内容解析任务参数"""
        try:
            # 尝试解析 JSON 格式
            if content.startswith("{"):
                data = json.loads(content)
                return TaskPayload(
                    task_id=message_id,
                    keyword=data.get("keyword", self.settings.default_keyword),
                    min_positive_rate=float(data.get("min_positive_rate", self.settings.default_min_positive_rate)),
                    max_items=int(data.get("max_items", self.settings.default_max_items)),
                )

            # 尝试解析文本格式：搜索索尼耳机 好评率95 数量3
            keyword = self.settings.default_keyword
            min_rate = self.settings.default_min_positive_rate
            max_items = self.settings.default_max_items

            if "搜索" in content:
                # 简单解析逻辑
                parts = content.split()
                for i, part in enumerate(parts):
                    if part == "搜索" and i + 1 < len(parts):
                        keyword = parts[i + 1]
                    elif "好评率" in part:
                        rate_str = part.replace("好评率", "").replace("%", "")
                        min_rate = float(rate_str)
                    elif "数量" in part:
                        num_str = part.replace("数量", "")
                        max_items = int(num_str)

            return TaskPayload(
                task_id=message_id,
                keyword=keyword,
                min_positive_rate=min_rate,
                max_items=max_items,
            )
        except Exception as e:
            print(f"Failed to parse task from message: {e}")
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def push_result(self, result: RunResult) -> None:
        """
        将结果推送到飞书

        支持两种方式：
        1. Webhook（简单，只能发送文本）
        2. OAuth API（高级，可发送富媒体卡片）
        """
        # 优先使用 OAuth API 发送富媒体消息
        if self.settings.feishu_app_id and self.settings.feishu_chat_id:
            try:
                await self._push_result_via_api(result)
                return
            except Exception as e:
                print(f"OAuth push failed, fallback to webhook: {e}")

        # Fallback：使用 Webhook
        if self.settings.feishu_webhook_url:
            await self._push_result_via_webhook(result)

    async def _push_result_via_webhook(self, result: RunResult) -> None:
        """通过 Webhook 发送结果（文本消息）"""
        success_emoji = "✅" if result.success else "❌"

        # 构建商品列表文本
        items_text = ""
        if result.matched_items:
            items_text = "\n\n📦 匹配商品：\n"
            for i, item in enumerate(result.matched_items, 1):
                items_text += f"{i}. {item.title[:30]}...\n"
                items_text += f"   好评率: {item.positive_rate}% | 价格: {item.price}\n"

        message = f"""{success_emoji} Taobao 自动化测试结果

📋 任务ID: {result.task_id}
⏱️ 执行时间: {result.timestamp}
🎯 状态: {'成功' if result.success else '失败'}
💬 消息: {result.message}

🛒 加购数量: {result.added_to_cart_count}/{len(result.matched_items)}
{items_text}
📸 截图: {result.artifacts.get('screenshot', 'N/A')}
"""

        payload = {
            "msg_type": "text",
            "content": {
                "text": message
            }
        }

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(self.settings.feishu_webhook_url, json=payload)
            response.raise_for_status()

    async def _push_result_via_api(self, result: RunResult) -> None:
        """通过 OAuth API 发送富媒体卡片消息"""
        access_token = self._get_access_token()
        if not access_token:
            raise Exception("No access token available")

        # 构建交互式卡片
        card_content = self._build_result_card(result)

        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        params = {"receive_id_type": "chat_id"}
        payload = {
            "receive_id": self.settings.feishu_chat_id,
            "msg_type": "interactive",
            "content": json.dumps(card_content, ensure_ascii=False)
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, params=params, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            if data.get("code") != 0:
                raise Exception(f"Failed to send message: {data}")

    def _build_result_card(self, result: RunResult) -> dict:
        """构建结果卡片"""
        success_color = "green" if result.success else "red"
        success_text = "✅ 成功" if result.success else "❌ 失败"

        # 构建商品元素
        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**{success_text}** | 任务: {result.task_id}"
                }
            },
            {
                "tag": "hr"
            },
            {
                "tag": "div",
                "fields": [
                    {
                        "is_short": True,
                        "text": {
                            "tag": "lark_md",
                            "content": f"**加购数量**\n{result.added_to_cart_count}"
                        }
                    },
                    {
                        "is_short": True,
                        "text": {
                            "tag": "lark_md",
                            "content": f"**匹配商品**\n{len(result.matched_items)}"
                        }
                    }
                ]
            }
        ]

        # 添加商品详情
        if result.matched_items:
            items_md = "\n".join([
                f"{i + 1}. {item.title[:25]}... ({item.positive_rate}%)"
                for i, item in enumerate(result.matched_items[:5])  # 最多显示5个
            ])
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**商品列表**\n{items_md}"
                }
            })

        return {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "🛒 Taobao 自动化测试报告"
                },
                "template": success_color
            },
            "elements": elements
        }

    @staticmethod
    def result_to_dict(result: RunResult) -> dict[str, Any]:
        return asdict(result)
