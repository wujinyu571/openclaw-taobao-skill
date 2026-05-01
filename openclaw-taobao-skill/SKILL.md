# Taobao UI Automation Skill (OpenClaw)

## 1. Skill Metadata
- **name**: `taobao_ui_automation_skill`
- **version**: `0.1.0`
- **description**: Receive test tasks from Feishu, run Taobao UI automation, and send execution results back to Feishu.
- **runtime**: Python 3.10+

## 2. Input Schema
```json
{
  "task_id": "string",
  "keyword": "string, default=索尼耳机",
  "min_positive_rate": "number, default=99",
  "headful": "boolean, default=false",
  "max_items": "integer, default=3"
}
```

## 3. Output Schema
```json
{
  "run_id": "string",
  "task_id": "string",
  "success": "boolean",
  "message": "string",
  "matched_items": [
    {
      "title": "string",
      "price": "string",
      "positive_rate": "number"
    }
  ],
  "added_to_cart_count": "integer",
  "artifacts": {
    "screenshot": "string",
    "log_file": "string"
  }
}
```

## 4. Execution Flow
1. Pull task from Feishu (or local payload when debugging).
2. Open Taobao homepage and try account-password login.
3. Search the configured keyword.
4. Parse item cards and filter by positive rate threshold.
5. Add qualified items to cart.
6. Send final result to Feishu webhook.

## 5. Retry & Failure Policy
- Network calls use retry with exponential backoff.
- Browser actions use explicit timeout and fallback selectors.
- Failure categories:
  - `LOGIN_FAILED`
  - `SEARCH_FAILED`
  - `NO_MATCHED_ITEMS`
  - `ADD_TO_CART_FAILED`
  - `REPORT_FAILED`

## 6. Security Notes
- Do not hardcode account/password/webhook in source code.
- Use environment variables from `.env`.
- Keep logs and screenshots in local `logs/` directory for troubleshooting.

## 7. Run Commands
- Debug run:
  - `python -m skill.main --task "search=索尼耳机;rating=99" --headful`
- Pull task from Feishu queue simulation:
  - `python -m skill.main`
