"""
偏好管理 + 对话记忆模块

功能：
1. 加载用户偏好配置（profiles/*.json）
2. 记录对话历史到 SQLite
3. 分析对话模式，自动更新偏好
4. 生成个性化 prompt 注入文本
"""
import json
import logging
import sqlite3
import threading
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent
PROFILES_DIR = BASE_DIR / "profiles"
DB_PATH = BASE_DIR / "data" / "conversations.db"

# 确保数据目录存在
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class ProfileManager:
    """用户偏好管理器"""

    def __init__(self):
        self._init_db()

    # ========== 数据库初始化 ==========

    def _init_db(self):
        """初始化 SQLite 数据库"""
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                open_id TEXT NOT NULL,
                user_message TEXT NOT NULL,
                bot_reply TEXT,
                chat_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                open_id TEXT NOT NULL,
                conversation_id INTEGER,
                rating TEXT,  -- 'like' or 'dislike'
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 创建索引加速查询
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conv_open_id 
            ON conversations(open_id, created_at)
        """)
        conn.commit()
        conn.close()
        logger.info("对话数据库初始化完成")

    # ========== 偏好加载 ==========

    def load_profile(self, open_id: Optional[str] = None) -> dict:
        """
        加载用户偏好配置

        Args:
            open_id: 用户的飞书 open_id，为空则加载默认配置

        Returns:
            偏好配置字典
        """
        if open_id:
            profile_path = PROFILES_DIR / f"{open_id}.json"
            if profile_path.exists():
                try:
                    with open(profile_path, "r", encoding="utf-8") as f:
                        profile = json.load(f)
                    logger.info(f"加载用户偏好: {profile.get('name', open_id)}")
                    return profile
                except Exception as e:
                    logger.error(f"加载偏好失败: {e}")

        # 加载默认配置
        default_path = PROFILES_DIR / "default.json"
        if default_path.exists():
            with open(default_path, "r", encoding="utf-8") as f:
                return json.load(f)

        return {"name": "默认用户", "style": "均衡型投资者"}

    def save_profile(self, open_id: str, profile: dict):
        """保存用户偏好配置"""
        profile["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        profile_path = PROFILES_DIR / f"{open_id}.json"
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        logger.info(f"已保存用户偏好: {profile.get('name', open_id)}")

    # ========== 对话记录 ==========

    def log_conversation(self, open_id: str, user_message: str, bot_reply: str = None, chat_id: str = None):
        """记录一次对话"""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO conversations (open_id, user_message, bot_reply, chat_id) VALUES (?, ?, ?, ?)",
                (open_id, user_message[:500], bot_reply[:500] if bot_reply else None, chat_id),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"记录对话失败: {e}")

    def get_recent_conversations(self, open_id: str, days: int = 7, limit: int = 50) -> list:
        """获取用户最近的对话记录"""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            since = (datetime.now() - timedelta(days=days)).isoformat()
            cursor.execute(
                "SELECT user_message, bot_reply, created_at FROM conversations "
                "WHERE open_id = ? AND created_at >= ? ORDER BY created_at DESC LIMIT ?",
                (open_id, since, limit),
            )
            rows = cursor.fetchall()
            conn.close()
            return [
                {"user_message": r[0], "bot_reply": r[1], "created_at": r[2]}
                for r in rows
            ]
        except Exception as e:
            logger.error(f"获取对话历史失败: {e}")
            return []

    # ========== 智能分析 ==========

    def analyze_interests(self, open_id: str) -> dict:
        """
        分析用户的关注点（基于对话历史）

        通过关键词匹配，自动识别用户最常问的板块和话题
        """
        conversations = self.get_recent_conversations(open_id, days=30, limit=100)
        if not conversations:
            return {}

        # 板块关键词映射
        sector_keywords = {
            "半导体": ["半导体", "芯片", "算力", "GPU", "光刻", "封装", "HBM", "存储"],
            "AI": ["AI", "人工智能", "大模型", "GPT", "Claude", "DeepSeek", "智能"],
            "新能源": ["新能源", "光伏", "锂电", "储能", "风电", "宁德", "比亚迪"],
            "消费电子": ["消费电子", "手机", "苹果", "华为", "小米", "OPPO"],
            "互联网": ["互联网", "腾讯", "阿里", "字节", "美团", "拼多多", "电商"],
            "金融": ["银行", "保险", "券商", "利率", "美联储", "降息", "加息"],
            "医药": ["医药", "药", "医疗", "CXO", "创新药", "疫苗"],
            "黄金": ["黄金", "贵金属", "避险", "金价"],
            "房地产": ["房地产", "地产", "房价", "楼市"],
            "消费": ["消费", "白酒", "食品", "饮料", "零售"],
            "汽车": ["汽车", "新能源车", "电动车", "自动驾驶"],
        }

        # 统计每个板块被提到的次数
        all_text = " ".join([c["user_message"] for c in conversations])
        sector_hits = {}
        for sector, keywords in sector_keywords.items():
            count = sum(all_text.count(kw) for kw in keywords)
            if count > 0:
                sector_hits[sector] = count

        # 按次数排序
        sorted_sectors = sorted(sector_hits.items(), key=lambda x: x[1], reverse=True)

        result = {
            "top_sectors": [s[0] for s in sorted_sectors[:5]],
            "total_conversations": len(conversations),
            "analyzed_at": datetime.now().isoformat(),
        }

        logger.info(f"用户兴趣分析: {result['top_sectors']}")
        return result

    def auto_update_profile(self, open_id: str) -> bool:
        """
        自动更新用户偏好（基于对话分析）

        如果用户经常问某个板块的问题，自动加入 focus_sectors
        """
        profile = self.load_profile(open_id)
        interests = self.analyze_interests(open_id)

        if not interests.get("top_sectors"):
            return False

        updated = False
        current_focus = set(profile.get("focus_sectors", []))

        for sector in interests["top_sectors"]:
            if sector not in current_focus:
                current_focus.add(sector)
                updated = True
                logger.info(f"自动添加关注板块: {sector}")

        if updated:
            profile["focus_sectors"] = list(current_focus)
            profile["auto_updated"] = True
            self.save_profile(open_id, profile)
            return True

        return False

    # ========== Prompt 生成 ==========

    def build_personalized_context(self, open_id: Optional[str] = None) -> str:
        """
        生成个性化的 prompt 注入文本

        把用户的偏好转换成 AI 能理解的指令，注入到早报生成和对话的 prompt 中
        """
        profile = self.load_profile(open_id)

        if not profile or profile.get("name") == "默认用户":
            return ""

        parts = []

        # 投资风格
        style = profile.get("style", "")
        if style:
            parts.append(f"用户是{style}，请在分析时匹配这种风格。")

        # 关注板块
        focus = profile.get("focus_sectors", [])
        if focus:
            parts.append(f"用户重点关注板块：{'、'.join(focus)}。请优先分析这些板块相关的新闻和影响。")

        # 回避板块
        avoid = profile.get("avoid_sectors", [])
        if avoid:
            parts.append(f"用户不关注板块：{'、'.join(avoid)}。这些板块的新闻可以简略带过。")

        # 风险偏好
        risk = profile.get("risk_tolerance", "")
        risk_map = {
            "低": "用户风险偏好保守，分析时侧重风险提示和防御策略",
            "中等": "用户风险偏好适中，分析时兼顾机会和风险",
            "中等偏高": "用户风险偏好较高，分析时可以多关注成长机会和进攻策略",
            "高": "用户风险偏好激进，分析时侧重高弹性机会",
        }
        if risk in risk_map:
            parts.append(risk_map[risk])

        # 分析偏好
        analysis = profile.get("analysis_preference", "")
        if analysis:
            parts.append(f"分析风格要求：{analysis}")

        # 市场倾向
        bias = profile.get("market_bias", "")
        bias_map = {
            "偏多": "用户倾向看多，但请保持客观分析，不要刻意迎合",
            "偏空": "用户倾向看空，但请保持客观分析，不要刻意迎合",
        }
        if bias in bias_map:
            parts.append(bias_map[bias])

        # 自定义备注
        notes = profile.get("custom_notes", "")
        if notes:
            parts.append(f"额外说明：{notes}")

        context = "\n\n【用户偏好】（请在回答时参考以下偏好，但保持客观专业）\n" + "\n".join(f"- {p}" for p in parts)

        return context


# 全局单例
_profile_manager: Optional[ProfileManager] = None
_lock = threading.Lock()


def get_profile_manager() -> ProfileManager:
    """获取 ProfileManager 单例"""
    global _profile_manager
    with _lock:
        if _profile_manager is None:
            _profile_manager = ProfileManager()
        return _profile_manager


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    pm = ProfileManager()

    # 测试：加载你的偏好
    print("=" * 60)
    print("测试1：加载用户偏好")
    print("=" * 60)
    profile = pm.load_profile("ou_772dc199c86c75abeff86b40fc38fef4")
    print(json.dumps(profile, ensure_ascii=False, indent=2))

    # 测试：生成个性化 prompt
    print("\n" + "=" * 60)
    print("测试2：生成个性化 prompt 注入文本")
    print("=" * 60)
    context = pm.build_personalized_context("ou_772dc199c86c75abeff86b40fc38fef4")
    print(context)

    # 测试：模拟对话记录
    print("\n" + "=" * 60)
    print("测试3：记录对话")
    print("=" * 60)
    pm.log_conversation("ou_772dc199c86c75abeff86b40fc38fef4", "半导体板块今天怎么看？", "半导体板块今天...", "oc_test")
    pm.log_conversation("ou_772dc199c86c75abeff86b40fc38fef4", "AI算力需求会不会继续增长？", "AI算力需求...", "oc_test")
    pm.log_conversation("ou_772dc199c86c75abeff86b40fc38fef4", "黄金现在还能买吗？", "黄金...", "oc_test")
    print("已记录3条对话")

    # 测试：兴趣分析
    print("\n" + "=" * 60)
    print("测试4：分析用户兴趣")
    print("=" * 60)
    interests = pm.analyze_interests("ou_772dc199c86c75abeff86b40fc38fef4")
    print(json.dumps(interests, ensure_ascii=False, indent=2))
