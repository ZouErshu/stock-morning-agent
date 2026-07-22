"""
飞书机器人诊断脚本 - 逐项排查配置问题
"""
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("诊断")

print("=" * 60)
print("🔍 飞书机器人配置诊断工具")
print("=" * 60)

# ========== 第1项：检查 .env 配置 ==========
print("\n📋 [1/6] 检查 .env 配置文件...")
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

APP_ID = os.getenv("FEISHU_APP_ID", "")
APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

if APP_ID and APP_ID != "cli_xxxxxxxxxxxxxxxx":
    print(f"  ✅ FEISHU_APP_ID: {APP_ID[:10]}...")
else:
    print(f"  ❌ FEISHU_APP_ID 未填写或仍是模板值")
    
if APP_SECRET and APP_SECRET != "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx":
    print(f"  ✅ FEISHU_APP_SECRET: {APP_SECRET[:10]}...")
else:
    print(f"  ❌ FEISHU_APP_SECRET 未填写或仍是模板值")

if API_KEY and API_KEY != "sk-xxxxxxxxxxxxxxxxxxxxxxxx":
    print(f"  ✅ DEEPSEEK_API_KEY: {API_KEY[:10]}...")
else:
    print(f"  ⚠️  DEEPSEEK_API_KEY 未填写（不影响飞书测试）")

# ========== 第2项：获取 tenant_access_token ==========
print("\n🔑 [2/6] 测试飞书凭证（获取 tenant_access_token）...")
import requests

try:
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") == 0:
        token = data["tenant_access_token"]
        print(f"  ✅ 凭证验证成功！已获取 tenant_access_token")
        print(f"     Token: {token[:20]}...")
    else:
        print(f"  ❌ 凭证验证失败: code={data.get('code')}, msg={data.get('msg')}")
        print(f"     请检查 FEISHU_APP_ID 和 FEISHU_APP_SECRET 是否正确")
        exit(1)
except Exception as e:
    print(f"  ❌ 网络请求失败: {e}")
    exit(1)

# ========== 第3项：获取机器人信息 ==========
print("\n🤖 [3/6] 检查机器人能力是否已启用...")
try:
    resp = requests.get(
        "https://open.feishu.cn/open-apis/bot/v3/info",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") == 0:
        bot_info = data.get("data", {}).get("bot", {})
        bot_name = bot_info.get("app_name", "未知")
        print(f"  ✅ 机器人已启用！")
        print(f"     名称: {bot_name}")
    else:
        print(f"  ❌ 获取机器人信息失败: code={data.get('code')}, msg={data.get('msg')}")
        print(f"     这说明「机器人」能力可能未正确配置")
        print(f"     请去飞书开放平台 → 添加应用能力 → 确认「机器人」已添加")
except Exception as e:
    print(f"  ❌ 请求失败: {e}")

# ========== 第4项：列出最近会话 ==========
print("\n💬 [4/6] 获取机器人最近的会话列表（需要先有人@过机器人）...")
try:
    resp = requests.get(
        "https://open.feishu.cn/open-apis/im/v1/chats",
        headers={"Authorization": f"Bearer {token}"},
        params={"page_size": 10},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") == 0:
        items = data.get("data", {}).get("items", [])
        if items:
            print(f"  ✅ 找到 {len(items)} 个会话：")
            for item in items:
                chat_id = item.get("chat_id", "")
                chat_name = item.get("name", "未命名")
                print(f"     - {chat_name}")
                print(f"       chat_id: {chat_id}")
                print(f"       ← 把这个 chat_id 填到 .env 的 FEISHU_RECEIVE_ID")
        else:
            print(f"  ⚠️  没有找到任何会话")
            print(f"     这说明机器人还没有被添加到任何群聊或单聊")
            print(f"     请去飞书客户端：")
            print(f"     1. 创建一个群（或打开已有群）")
            print(f"     2. 群设置 → 群机器人 → 添加「市场早报助手」")
            print(f"     3. 在群里 @机器人 发一条消息")
    else:
        print(f"  ❌ 获取会话列表失败: code={data.get('code')}, msg={data.get('msg')}")
        print(f"     可能原因：未开通 im:chat 权限")
except Exception as e:
    print(f"  ❌ 请求失败: {e}")

# ========== 第5项：检查事件订阅状态 ==========
print("\n📡 [5/6] 检查事件订阅配置状态...")
try:
    resp = requests.get(
        "https://open.feishu.cn/open-apis/event/v1/app_event_config",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") == 0:
        config = data.get("data", {})
        events = config.get("events", [])
        if events:
            print(f"  ✅ 已订阅 {len(events)} 个事件：")
            for evt in events:
                print(f"     - {evt}")
        else:
            print(f"  ⚠️  未订阅任何事件！")
            print(f"     请去飞书开放平台 → 事件与回调 → 事件配置 → 添加事件")
    else:
        print(f"  ⚠️  无法获取事件配置（可能应用未发布）: code={data.get('code')}")
except Exception as e:
    print(f"  ⚠️  请求失败: {e}（可能应用未发布）")

# ========== 第6项：尝试发送测试消息 ==========
print("\n📨 [6/6] 尝试发送测试消息...")
print("   请输入你想发送到的 chat_id（从上一步复制）：")
print("   （如果上一步没有找到会话，先跳过这一步）")
print("   （直接回车跳过）")

chat_id = input("   chat_id: ").strip()
if chat_id:
    try:
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "🤖 诊断测试"},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "✅ 诊断脚本发送成功！\n\n如果你看到这条消息，说明：\n- App ID / Secret 正确\n- 发送消息权限正常\n- chat_id 正确\n\n接下来可以继续配置事件接收。"
                    }
                }
            ],
        }
        resp = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            params={"receive_id_type": "chat_id"},
            json={
                "receive_id": chat_id,
                "msg_type": "interactive",
                "content": json.dumps(card),
            },
            timeout=10,
        )
        data = resp.json()
        if data.get("code") == 0:
            print(f"  ✅ 消息发送成功！请去飞书群查看")
        else:
            print(f"  ❌ 发送失败: code={data.get('code')}, msg={data.get('msg')}")
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
else:
    print("  ⏭️  已跳过")

print("\n" + "=" * 60)
print("🏁 诊断完成！")
print("=" * 60)
print("\n📌 下一步：")
print("1. 如果第4项找到了 chat_id → 把它填到 .env 的 FEISHU_RECEIVE_ID")
print("2. 如果第4项没找到会话 → 去飞书群添加机器人后重新运行本脚本")
print("3. 如果第5项显示未订阅事件 → 去飞书开放平台添加事件")
print("4. 如果都OK → 运行 python main.py serve 启动服务")
