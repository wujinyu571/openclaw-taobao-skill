from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseModel):
    taobao_username: str = Field(default=os.getenv("TAOBAO_USERNAME", ""))
    taobao_password: str = Field(default=os.getenv("TAOBAO_PASSWORD", ""))

    # 飞书 Webhook 配置（简单模式）
    feishu_webhook_url: str = Field(default=os.getenv("FEISHU_WEBHOOK_URL", ""))

    # 飞书 OAuth 配置（高级模式，支持接收任务）
    feishu_app_id: str = Field(default=os.getenv("FEISHU_APP_ID", ""))
    feishu_app_secret: str = Field(default=os.getenv("FEISHU_APP_SECRET", ""))
    feishu_chat_id: str = Field(default=os.getenv("FEISHU_CHAT_ID", ""))

    headless: bool = Field(default=_to_bool(os.getenv("HEADLESS"), True))
    browser_channel: str = Field(default=os.getenv("BROWSER_CHANNEL", ""))
    use_persistent_context: bool = Field(default=_to_bool(os.getenv("USE_PERSISTENT_CONTEXT"), True))
    browser_user_data_dir: str = Field(default=os.getenv("BROWSER_USER_DATA_DIR", "browser_profile"))
    semi_auto_mode: bool = Field(default=_to_bool(os.getenv("SEMI_AUTO_MODE"), True))
    manual_verify_gate: bool = Field(default=_to_bool(os.getenv("MANUAL_VERIFY_GATE"), True))
    auto_password_login: bool = Field(default=_to_bool(os.getenv("AUTO_PASSWORD_LOGIN"), False))
    persistent_session_enabled: bool = Field(default=_to_bool(os.getenv("PERSISTENT_SESSION_ENABLED"), True))
    session_state_path: str = Field(default=os.getenv("SESSION_STATE_PATH", "auth_state.json"))
    default_keyword: str = Field(default=os.getenv("DEFAULT_KEYWORD", "索尼耳机"))
    default_min_positive_rate: float = Field(default=float(os.getenv("DEFAULT_MIN_POSITIVE_RATE", "99")))
    default_max_items: int = Field(default=int(os.getenv("DEFAULT_MAX_ITEMS", "3")))
    max_scan_items: int = Field(default=int(os.getenv("MAX_SCAN_ITEMS", "20")))
    browser_timeout_ms: int = Field(default=int(os.getenv("BROWSER_TIMEOUT_MS", "15000")))
    manual_login_timeout_sec: int = Field(default=int(os.getenv("MANUAL_LOGIN_TIMEOUT_SEC", "180")))
    manual_verify_ready_timeout_sec: int = Field(default=int(os.getenv("MANUAL_VERIFY_READY_TIMEOUT_SEC", "240")))
    task_retry_times: int = Field(default=int(os.getenv("TASK_RETRY_TIMES", "2")))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
