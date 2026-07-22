# 📊 股票国际市场早报 Agent

> 每天早上自动生成「隔夜全球市场行情 + AI 影响研判 + 今日A股策略」早报，推送到飞书；同时在飞书 @机器人 可随时对话提问。

## ✨ 核心能力

| 能力 | 说明 |
|------|------|
| 🌍 全球行情 | 美股指数、外汇、大宗商品、加密货币、中概ETF |
| 📰 财经新闻 | 自动抓取全球财经快讯，AI 筛选重要新闻 |
| 🧠 AI 研判 | DeepSeek 分析每条新闻对A股的影响链路 |
| 📅 定时推送 | 每天定时推送到飞书群/单聊 |
| 💬 对话交互 | 飞书 @机器人 随时提问市场相关问题 |
| 📦 多格式输出 | 飞书卡片 / Markdown / HTML 归档 |

## 🏗️ 架构

```
数据采集层                AI 分析层              输出层
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ yfinance     │      │              │      │ 飞书卡片推送 │
│  - 美股指数   │─────▶│  DeepSeek    │─────▶│ Markdown     │
│  - 外汇商品   │      │  - 行情综述   │      │ HTML 归档    │
│  - 中概ETF   │      │  - 新闻影响   │      └──────────────┘
├──────────────┤      │  - 情绪判断   │
│ akshare      │      │  - A股研判    │
│  - 全球新闻   │─────▶│  - 事件解读   │
│  - 经济日历   │      │              │
└──────────────┘      └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │ 飞书长连接    │
                     │ - 定时推送    │
                     │ - @对话问答   │
                     └──────────────┘
```

## 🚀 快速开始

### 1. 环境准备

- Python 3.10+
- Windows / macOS / Linux 均可

### 2. 安装依赖

```bash
cd stock-morning-agent
pip install -r requirements.txt
```

### 3. 申请 API 密钥

#### DeepSeek API（LLM）
1. 访问 https://platform.deepseek.com/
2. 注册并创建 API Key
3. 充值（10元可用很久）

#### 飞书机器人
1. 访问 https://open.feishu.cn/app 创建企业自建应用
2. 添加「机器人」能力
3. **事件订阅** → 选择「长连接模式」（无需公网IP）
4. 订阅事件：`im.message.receive_v1`
5. **权限管理** → 开启：
   - `im:message`（获取与发送单聊、群组消息）
   - `im:message:send_as_bot`（以应用身份发消息）
6. 发布版本 → 等待管理员审批（个人测试空间可秒批）
7. 把机器人添加到你的测试群或单聊

### 4. 配置

```bash
cp .env.example .env
```

编辑 `.env` 填入：
- `DEEPSEEK_API_KEY` - DeepSeek API 密钥
- `FEISHU_APP_ID` / `FEISHU_APP_SECRET` - 飞书应用凭证
- `FEISHU_RECEIVE_ID` - 推送目标（先随便填，运行 `test` 命令后看日志获取真实 ID）

### 5. 运行

```bash
cd src

# 测试飞书连接
python main.py test

# 立即生成一次早报（推送到飞书）
python main.py report

# 仅采集数据（调试用，不需要 LLM/飞书配置）
python main.py fetch

# 仅生成分析（保存为本地 HTML，不推送飞书）
python main.py analyze

# 启动完整服务（飞书长连接 + 定时推送）
python main.py serve
```

### 6. 获取飞书 chat_id

第一次运行时，`FEISHU_RECEIVE_ID` 可能不知道填什么。两种方式获取：

**方式A（推荐）**：先在飞书群里 @机器人 发一条消息，日志会打印出 `chat_id`，把它填到 `.env` 即可。

**方式B**：先用 `python main.py test` 测试，如果 `FEISHU_RECEIVE_ID` 为空会失败，但日志里也会给出提示。

## 💬 使用方式

启动 `python main.py serve` 后，在飞书中：

1. **被动接收**：每天到点自动推送早报到群/单聊
2. **主动对话**：@机器人 + 问题，例如：
   - `@机器人 早报` → 推送今日早报
   - `@机器人 今天美股为什么大跌？` → AI 解答
   - `@机器人 半导体板块怎么看？` → 板块分析
   - `@机器人 帮助` → 查看功能列表

## 📁 项目结构

```
stock-morning-agent/
├── src/
│   ├── main.py            # 主入口（命令分发）
│   ├── config.py          # 配置管理
│   ├── data_fetcher.py    # 数据采集（行情+新闻）
│   ├── analyzer.py        # AI 分析（DeepSeek）
│   ├── formatter.py       # 报告格式化（飞书卡片/MD/HTML）
│   ├── feishu_bot.py      # 飞书机器人（推送+对话）
│   └── scheduler.py       # 定时任务
├── output/                # 生成的 HTML/Markdown 早报归档
├── logs/                  # 运行日志
├── .env.example           # 配置模板
├── requirements.txt       # Python 依赖
└── README.md
```

## 🔧 自定义配置

### 修改监控标的

编辑 `src/config.py` 中的 `WATCH_SYMBOLS`：

```python
WATCH_SYMBOLS = {
    "美股指数": {
        "^GSPC": "标普500",
        # 添加更多...
    },
    # 添加新分类...
}
```

标的代码查询：https://finance.yahoo.com/

### 修改推送时间

编辑 `.env`：
```
PUSH_HOUR=7
PUSH_MINUTE=30
```

### 切换 LLM

`.env` 中修改（兼容 OpenAI 格式的 API 都可用）：

```
# 智谱 GLM-4
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
LLM_MODEL=glm-4

# 通义千问
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus

# Moonshot Kimi
LLM_BASE_URL=https://api.moonshot.cn/v1
LLM_MODEL=moonshot-v1-8k
```

## 💰 成本估算

| 项目 | 频次 | 单次成本 | 月成本 |
|------|------|----------|--------|
| 早报生成 | 1次/天 | ~0.03元 | ~1元 |
| 对话问答 | 10次/天 | ~0.05元 | ~15元 |
| **合计** | | | **~16元/月** |

（基于 DeepSeek 定价：输入1元/百万token，输出2元/百万token）

## ⚠️ 免责声明

本项目生成的所有内容均由 AI 分析产生，**仅供学习参考，不构成任何投资建议**。投资有风险，决策需谨慎。

## 📝 License

MIT
