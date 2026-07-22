# 🏗️ 股票国际市场早报 Agent — 技术架构文档

> 作者：邹尔舒 | 2026年7月

## 一、系统架构

```
┌─────────────────────────────────────────────────────────┐
│                     飞书客户端                           │
│  定时接收早报  |  @机器人提问  |  群聊/单聊              │
└────────────────────────┬────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
┌─────────────────────┐     ┌─────────────────────┐
│  飞书开放平台长连接   │     │  本地Python Agent    │
│  WebSocket双向通道   │◀───▶│                     │
│  无需公网IP          │     │  数据采集 → AI分析   │
└─────────────────────┘     │  → 格式化 → 推送     │
                            │  → 个性化引擎        │
                            │  → 对话记忆(SQLite)  │
                            └─────────────────────┘
```

## 二、数据流

### 早报生成流程

1. 定时触发（每日7:30）
2. 数据采集：yfinance抓15个标的行情 + akshare抓20条新闻 + 15条经济日历
3. 加载用户偏好：profiles/*.json
4. AI分析（DeepSeek）：行情综述 → 新闻影响链路 → 情绪判断 → A股研判 → 事件解读
5. 格式化输出：飞书卡片JSON + Markdown + HTML归档
6. 推送：飞书 im/v1/messages API

### 对话交互流程

1. 用户@机器人提问
2. 飞书事件推送 im.message.receive_v1
3. 解析消息：提取文本、去除@提及、识别用户ID
4. 加载用户偏好 + 获取今日市场数据（30分钟缓存）
5. AI对话引擎：system prompt注入用户偏好和今日数据
6. 发送回复（短文本text / 长文本card）
7. 记录对话到SQLite

## 三、技术选型

| 层次 | 技术 | 选型理由 |
|------|------|---------|
| 语言 | Python 3.12 | 数据科学生态完善，AI SDK支持好 |
| LLM | DeepSeek-chat | 推理能力强、中文好、价格低、国内直连 |
| 行情数据 | yfinance | 免费、覆盖全球市场、Python原生支持 |
| 新闻数据 | akshare | 免费、国内财经数据全、更新及时 |
| 即时通讯 | 飞书长连接(WebSocket) | 无需公网IP、原生IM体验、SDK完善 |
| 定时任务 | schedule | 轻量、Python原生、适合单机部署 |
| 对话记忆 | SQLite | 零配置、嵌入式、适合个人项目 |
| 配置管理 | python-dotenv | 环境变量管理、安全隔离密钥 |

## 四、模块设计

| 模块 | 文件 | 职责 |
|------|------|------|
| 主入口 | main.py | 命令分发、日志配置 |
| 配置管理 | config.py | .env加载、配置校验 |
| 数据采集 | data_fetcher.py | 行情+新闻+经济日历采集 |
| AI分析 | analyzer.py | LLM调用、早报生成、对话 |
| 格式化 | formatter.py | 飞书卡片/MD/HTML格式化 |
| 飞书机器人 | feishu_bot.py | 消息收发、长连接监听 |
| 定时调度 | scheduler.py | 每日定时推送 |
| 偏好管理 | profile_manager.py | 偏好加载、对话记忆、兴趣分析 |

### 个性化系统设计

三层架构：
1. 偏好配置层：profiles/*.json存储用户偏好（关注板块、投资风格、风险偏好）
2. Prompt注入层：ProfileManager.build_personalized_context()将偏好转为AI指令
3. 对话记忆层：SQLite记录所有对话，analyze_interests()自动分析用户兴趣

## 五、部署说明

### 环境要求
- Python 3.10+
- 网络：能访问 api.deepseek.com 和 msg-frontier.feishu.cn
- 无需公网IP、无需服务器

### 启动命令
```bash
cd src
python main.py serve    # 启动完整服务（长连接+定时推送）
python main.py test     # 测试飞书连接
python main.py report   # 立即生成并推送早报
python main.py fetch    # 仅采集数据（调试用）
python main.py analyze  # 生成分析并保存HTML（调试用）
```

### 迁移到新电脑
```bash
pip install -r requirements.txt
cd src && python main.py serve
```

## 六、安全与隐私

| 方面 | 措施 |
|------|------|
| API密钥 | 存储在.env，不提交到Git |
| 对话数据 | 本地SQLite，不上传任何服务器 |
| 用户偏好 | 本地JSON文件，每个用户独立 |
| 飞书通信 | 长连接内置加密 |
