# 🛒 Taobao UI Automation Skill

> 基于 OpenClaw 框架的淘宝自动化测试技能，实现从飞书接收任务 → 浏览器自动化操作 → 结果回传飞书的完整闭环。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-1.40+-green.svg)](https://playwright.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📋 目录

- [功能特性](#-功能特性)
- [架构设计](#-架构设计)
- [代码结构](#-代码结构)
- [快速开始](#-快速开始)
- [配置说明](#-配置说明)
- [使用方法](#-使用方法)

---

## ✨ 功能特性

### 核心功能

- ✅ **飞书任务集成**：支持 Webhook 和 OAuth 双模式，实现任务下发与结果回传
- ✅ **智能登录**：支持扫码登录和密码登录，自动检测风控验证码
- ✅ **商品搜索**：自动化搜索指定关键词，处理多标签页切换
- ✅ **智能筛选**：基于好评率阈值（默认 ≥99%）自动筛选优质商品
- ✅ **自动加购**：将符合条件的商品批量加入购物车
- ✅ **结果反馈**：生成结构化测试报告，支持富媒体卡片推送

### 技术亮点

- 🎯 **高鲁棒性**：多层降级策略，应对页面结构变化和异常场景
- 🔍 **可观测性**：每次运行生成唯一 `run_id`，绑定截图和日志
- 🛡️ **反检测能力**：隐藏自动化特征，降低被风控识别的概率
- 🔄 **会话持久化**：保存登录状态，避免重复登录触发风控
- 📊 **结构化输出**：符合 OpenClaw 规范的 Input/Output Schema

---

## 🏗️ 架构设计

### 整体架构
![Alt text](%E6%9E%B6%E6%9E%84%E5%9B%BE.png)

### 核心模块

| 模块 | 职责 | 关键文件 |
|------|------|---------|
| **编排层** | 任务调度、流程编排、异常捕获 | `skill/core/orchestrator.py` |
| **执行层** | Playwright 浏览器自动化 | `skill/core/taobao_runner.py` |
| **解析层** | 商品信息提取、好评率解析 | `skill/core/parser.py` |
| **集成层** | 飞书 API 调用、消息推送 | `skill/integrations/feishu_client.py` |
| **配置层** | 环境变量管理、类型校验 | `skill/config.py` |

---

## 🧪 代码结构
    openclaw-taobao-skill/
    ├── skill/
    │   ├── core/
    │   │   ├── orchestrator.py    负责整体流程调度，协调飞书任务拉取、淘宝自动化执行及结果回传
    │   │   ├── taobao_runner.py    基于 Playwright 实现淘宝登录、搜索、商品筛选及加购的核心自动化逻辑
    │   │   ├── parser.py    正则表达式工具，从商品详情页文本中精准提取好评率等关键信息
    │   |
    │   ├── integrations/
    │   │   ├── feishu_client.py    飞书客户端，飞书 API 调用、消息推送模块
    |   |
    │   ├── tests/
    │   │   ├── test_orchestrator.py    测试编排层，确保任务调度按预期进行
    │   │   ├── test_parser.py    测试解析层，验证商品信息提取是否准确
    │   ├── config.py    定义核心模块所需的局部配置或辅助函数
    │   ├── main.py    主程序入口，协调各模块的运行
    │   ├── models.py    定义数据模型，用于存储任务、商品信息等数据
    |
    ├── scripts/
    │   ├── feishu_mock_server.py    模拟飞书 API 服务器，用于测试飞书客户端
    |   ├── run_full_test.ps1    运行完整测试流程，包括编排层、执行层、解析层
    |   ├── run_skill.ps1    运行技能主程序，协调各模块的运行
    |   ├── send_test_task.py    发送测试任务到飞书群聊
    |   ├── test_feishu.py    测试飞书客户端，验证消息推送功能是否正常
    |
    ├── logs/    存储运行时的日志文件
    ├── .venv/    虚拟环境目录，包含项目依赖和运行时环境
    ├── browser_profile/    存储浏览器配置文件，用于登录状态持久化
    |
    ├── requirements.txt    项目依赖列表，用于安装项目依赖
    ├── .env    环境变量配置文件，包含飞书 API 密钥等敏感信息
    ├── auth_state.json    存储登录状态，避免重复登录触发风控
    ├── SKILL.md    符合 OpenClaw 规范的技能定义文档，描述技能的元数据、输入输出契约及执行流程
    ├── README.md    项目介绍、安装说明、使用方法等详细信息

    ---

## 🚀 快速开始

### 前置要求

- **Python**: 3.10 或更高版本
- **浏览器**: Microsoft Edge 或 Google Chrome
- **操作系统**: Windows / macOS / Linux

### 安装步骤

#### 1. 克隆项目
    bash
    git clone https://github.com/wujinyu571/openclaw-taobao-skill.git
    cd openclaw-taobao-skill

#### 2. 创建虚拟环境
    bash
    Windows
        python -m venv .venv 
        .venv\Scripts\activate
    macOS/Linux
        python3 -m venv .venv 
        source .venv/bin/activate

#### 3. 安装依赖
    bash
    pip install -r requirements.txt

#### 4. 安装浏览器驱动
    bash
    安装 Microsoft Edge 浏览器
        playwright install msedge
    或安装 Google Chrome
        playwright install chrome

#### 5. 配置环境变量
    bash
    复制配置模板
        cp .env.example .env
    编辑配置文件
        vim .env

#### 6. 运行
    cd openclaw-taobao-skill
    创建虚拟环境
    .\.venv\Scripts\Activate.ps1
    配置 .env 中的环境变量
    配置飞书机器人，获取 Webhook URL
    在飞书群聊中发送消息：`@机器人 搜索索尼耳机 好评率99 数量3`
    python -m skill.main
    搜索到的结果被自动加入购物车
    机器人在飞书群内发送回传的结果

---

## ⚙️ 飞书配置详解

#### 方式1：Webhook

1. 在飞书群聊中添加「自定义机器人」
2. 获取 Webhook URL
3. 填入 `.env` 文件的 `FEISHU_WEBHOOK_URL`

**优点：** 配置简单，无需申请权限  
**缺点：** 只能发送消息，无法接收任务

#### 方式2：OAuth API

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 获取 `App ID` 和 `App Secret`
4. 开通「获取与发送单聊/群组消息」权限
5. 将应用添加到目标群聊，获取 `Chat ID`
6. 填入 `.env` 文件对应字段

**优点：** 支持双向通信，可发送富媒体卡片  
**缺点：** 配置复杂，需要管理员审批

---

