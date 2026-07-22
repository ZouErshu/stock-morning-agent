"""
飞书机器人模块 - 长连接模式，支持定时推送 + 对话交互
"""
import json
import logging
import threading
import time
from datetime import datetime
from typing import Optional

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    P2ImMessageReceiveV1,
)

from analyzer import MarketAnalyzer
from config import Config
from data_fetcher import collect_all_data
from formatter import format_feishu_card
from profile_manager import get_profile_manager

logger = logging.getLogger(__name__)


class FeishuBot:
    """飞书机器人 - 长连接模式"""

    def __init__(self):
        self.client = lark.Client.builder() \
            .app_id(Config.FEISHU_APP_ID) \
            .app_secret(Config.FEISHU_APP_SECRET) \
            .build()

        self.analyzer = MarketAnalyzer()
        self._cached_data: Optional[dict] = None
        self._cache_time: Optional[datetime] = None

    def send_card(self, card: dict, receive_id: str = None, receive_id_type: str = None):
        """发送飞书卡片消息"""
        receive_id = receive_id or Config.FEISHU_RECEIVE_ID
        receive_id_type = receive_id_type or Config.FEISHU_RECEIVE_ID_TYPE

        if not receive_id:
            logger.error("未配置 FEISHU_RECEIVE_ID")
            return False

        req = CreateMessageRequest.builder() \
            .receive_id_type(receive_id_type) \
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(receive_id)
                .msg_type("interactive")
                .content(json.dumps(card))
                .build()
            ).build()

        resp = self.client.im.v1.message.create(req)

        if resp.success():
            logger.info(f"✅ 飞书卡片消息发送成功 -> {receive_id_type}={receive_id}")
            return True
        else:
            logger.error(
                f"❌ 飞书消息发送失败: code={resp.code}, msg={resp.msg}, log_id={resp.get_log_id()}"
            )
            return False

    def send_text(self, text: str, receive_id: str = None, receive_id_type: str = None):
        """发送纯文本消息"""
        receive_id = receive_id or Config.FEISHU_RECEIVE_ID
        receive_id_type = receive_id_type or Config.FEISHU_RECEIVE_ID_TYPE

        if not receive_id:
            logger.error("未配置 FEISHU_RECEIVE_ID")
            return False

        req = CreateMessageRequest.builder() \
            .receive_id_type(receive_id_type) \
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(receive_id)
                .msg_type("text")
                .content(json.dumps({"text": text}))
                .build()
            ).build()

        resp = self.client.im.v1.message.create(req)
        if resp.success():
            logger.info(f"✅ 飞书文本消息发送成功")
            return True
        else:
            logger.error(f"❌ 飞书文本消息发送失败: {resp.code} - {resp.msg}")
            return False

    def generate_and_push_report(self, open_id: str = None):
        """生成早报并推送到飞书（支持个性化）"""
        logger.info("=" * 50)
        logger.info("开始生成并推送市场早报...")
        if open_id:
            logger.info(f"  个性化模式: open_id={open_id[:20]}...")
        logger.info("=" * 50)

        try:
            logger.info("Step 1: 采集市场数据")
            data = collect_all_data()
            self._cached_data = data
            self._cache_time = datetime.now()
            logger.info(f"  采集完成: {len(data['quotes'])}个标的, {len(data['news'])}条新闻")

            logger.info("Step 2: AI 研判分析")
            report = self.analyzer.generate_morning_report(data, open_id=open_id)
            logger.info(f"  研判完成: 情绪={report['overall_sentiment']}")

            logger.info("Step 3: 格式化飞书卡片")
            card = format_feishu_card(report, data["quotes"])

            logger.info("Step 4: 推送到飞书")
            success = self.send_card(card)

            if success:
                logger.info("🎉 早报推送完成！")
            else:
                logger.error("早报推送失败，尝试发送文本通知")
                self.send_text("⚠️ 今日早报生成失败，请检查日志")

        except Exception as e:
            logger.exception(f"早报生成推送异常: {e}")
            try:
                self.send_text(f"⚠️ 早报生成异常: {str(e)[:200]}")
            except Exception:
                pass

    def _get_fresh_data(self) -> dict:
        """获取今日数据（带缓存，30分钟内复用）"""
        now = datetime.now()
        if (
            self._cached_data
            and self._cache_time
            and (now - self._cache_time).total_seconds() < 1800
        ):
            return self._cached_data

        try:
            data = collect_all_data()
            self._cached_data = data
            self._cache_time = now
            return data
        except Exception as e:
            logger.error(f"数据采集失败: {e}")
            return self._cached_data or {}

    def handle_message(self, user_text: str, chat_id: str = None, open_id: str = None):
        """处理用户@机器人的消息（支持个性化）"""
        logger.info(f"收到用户消息: {user_text[:50]}...")

        # 记录对话到数据库
        pm = get_profile_manager()
        pm.log_conversation(open_id, user_text, chat_id=chat_id)

        user_text_lower = user_text.strip().lower()

        if user_text_lower in ["早报", "今日早报", "市场早报", "report"]:
            # 个性化早报
            self.generate_and_push_report(open_id=open_id)
            return

        if user_text_lower in ["帮助", "help", "?", "？"]:
            help_text = (
                "👋 我是市场早报助手，可以帮你：\n\n"
                "📊 发送「早报」- 获取今日市场早报\n"
                "💬 直接提问 - 例如：\n"
                "   • 今天美股为什么大跌？\n"
                "   • 黄金现在什么情况？\n"
                "   • 半导体板块今天怎么看？\n"
                "   • 美联储加息对A股有什么影响？\n\n"
                "⚠️ 回答仅供参考，不构成投资建议"
            )
            self.send_text(help_text, receive_id=chat_id or open_id)
            return

        try:
            self.send_text("💭 思考中...", receive_id=chat_id or open_id)

            context_data = self._get_fresh_data()
            # 传入 open_id 以加载个性化偏好
            reply = self.analyzer.chat(user_text, context_data, open_id=open_id)

            # 记录回复
            pm.log_conversation(open_id, user_text, bot_reply=reply, chat_id=chat_id)

            if len(reply) > 2000:
                card = {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "title": {"tag": "plain_text", "content": "💬 市场早报助手"},
                        "template": "blue",
                    },
                    "elements": [
                        {"tag": "div", "text": {"tag": "lark_md", "content": reply}}
                    ],
                }
                self.send_card(card, receive_id=chat_id, receive_id_type="chat" if chat_id else "open_id")
            else:
                self.send_text(reply, receive_id=chat_id or open_id)

        except Exception as e:
            logger.exception(f"对话处理异常: {e}")
            self.send_text(
                f"⚠️ 处理失败: {str(e)[:100]}",
                receive_id=chat_id or open_id,
            )

    def start_listener(self):
        """启动长连接监听（阻塞，处理用户@消息）"""

        def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
            """处理接收到的消息事件"""
            # 强制日志：只要收到任何事件就打印（调试用）
            logger.info("=" * 40)
            logger.info("🔥 收到飞书事件推送！")
            logger.info(f"   事件类型: {data.event.message.message_type}")
            logger.info(f"   chat_id: {data.event.message.chat_id}")
            logger.info(f"   发送者: {data.event.sender.sender_id.open_id}")
            logger.info("=" * 40)

            try:
                msg = data.event.message
                msg_type = msg.message_type

                if msg_type != "text":
                    logger.info(f"   跳过非文本消息: type={msg_type}")
                    return

                content = json.loads(msg.content)
                user_text = content.get("text", "").strip()

                logger.info(f"   原始消息内容: {user_text[:100]}")

                # 去掉 @机器人 的部分
                # 飞书 @ 消息格式: @机器人名 实际内容
                # 也可能包含 @_user_xxx 的内部标识
                import re
                # 移除所有 @xxx 形式的提及
                user_text = re.sub(r'@\S+', '', user_text).strip()

                if not user_text:
                    logger.info("   去除@后内容为空，跳过")
                    return

                logger.info(f"   处理后文本: {user_text[:50]}")

                chat_id = msg.chat_id
                open_id = data.event.sender.sender_id.open_id

                logger.info(f"✅ 收到消息 from {open_id} in {chat_id}: {user_text[:50]}")

                threading.Thread(
                    target=self.handle_message,
                    args=(user_text,),
                    kwargs={"chat_id": chat_id, "open_id": open_id},
                    daemon=True,
                ).start()

            except Exception as e:
                logger.exception(f"❌ 消息处理异常: {e}")

        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1)
            .build()
        )

        cli = lark.ws.Client(
            Config.FEISHU_APP_ID,
            Config.FEISHU_APP_SECRET,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
        )

        logger.info("🚀 飞书机器人长连接已启动，等待消息...")
        logger.info("   在飞书中 @机器人 即可对话")
        cli.start()

    def test_send(self):
        """手动测试消息发送"""
        test_card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "🤖 机器人连接测试"},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "✅ 飞书机器人连接成功！\n\n如果你看到这条消息，说明配置正确。\n\n你可以：\n- 发送「早报」获取今日市场早报\n- 直接提问市场相关问题",
                    },
                }
            ],
        }
        return self.send_card(test_card)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    Config.ensure_dirs()

    missing = Config.validate()
    if missing:
        print("⚠️  配置不完整：")
        for m in missing:
            print(f"   - {m}")
        print("\n请先复制 .env.example 为 .env 并填写")
        exit(1)

    import sys

    bot = FeishuBot()

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("发送测试消息...")
        bot.test_send()
    elif len(sys.argv) > 1 and sys.argv[1] == "report":
        print("立即生成并推送早报...")
        bot.generate_and_push_report()
    else:
        print("启动飞书机器人长连接...")
        bot.start_listener()
