"""
定时任务模块 - 每天定时生成并推送早报
"""
import logging
import threading
import time
from datetime import datetime

import schedule

from config import Config

logger = logging.getLogger(__name__)


class ReportScheduler:
    """早报定时推送调度器"""

    def __init__(self, bot):
        self.bot = bot
        self._running = False

    def schedule_daily(self):
        """配置每日定时任务"""
        schedule.every().day.at(f"{Config.PUSH_HOUR:02d}:{Config.PUSH_MINUTE:02d}").do(
            self._safe_push
        )
        logger.info(
            f"📅 已设定每日定时推送：{Config.PUSH_HOUR:02d}:{Config.PUSH_MINUTE:02d}"
        )

    def _safe_push(self):
        """安全推送（捕获异常避免定时任务挂掉）"""
        try:
            self.bot.generate_and_push_report()
        except Exception as e:
            logger.exception(f"定时推送异常: {e}")

    def run_pending_loop(self):
        """在子线程中运行定时检查循环"""
        self._running = True
        logger.info("🔄 定时任务调度器已启动")

        while self._running:
            schedule.run_pending()
            time.sleep(30)

    def start(self):
        """启动定时任务（在子线程中运行）"""
        self.schedule_daily()
        thread = threading.Thread(target=self.run_pending_loop, daemon=True)
        thread.start()
        logger.info(f"定时任务线程已启动，每日 {Config.PUSH_HOUR:02d}:{Config.PUSH_MINUTE:02d} 推送")
        return thread

    def stop(self):
        self._running = False
