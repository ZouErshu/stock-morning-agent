"""
配置管理模块 - 从 .env 文件加载所有配置
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 加载 .env 文件
load_dotenv(BASE_DIR / ".env")


class Config:
    """全局配置"""

    # ===== LLM 配置 =====
    LLM_API_KEY: str = os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek-chat")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))

    # ===== 飞书配置 =====
    FEISHU_APP_ID: str = os.getenv("FEISHU_APP_ID", "")
    FEISHU_APP_SECRET: str = os.getenv("FEISHU_APP_SECRET", "")
    FEISHU_RECEIVE_ID: str = os.getenv("FEISHU_RECEIVE_ID", "")
    FEISHU_RECEIVE_ID_TYPE: str = os.getenv("FEISHU_RECEIVE_ID_TYPE", "chat")

    # ===== 推送配置 =====
    PUSH_HOUR: int = int(os.getenv("PUSH_HOUR", "7"))
    PUSH_MINUTE: int = int(os.getenv("PUSH_MINUTE", "30"))

    # ===== 日志配置 =====
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ===== 路径配置 =====
    OUTPUT_DIR: Path = BASE_DIR / "output"
    LOG_DIR: Path = BASE_DIR / "logs"

    @classmethod
    def validate(cls) -> list:
        """校验必填配置，返回缺失项列表"""
        missing = []
        if not cls.LLM_API_KEY:
            missing.append("DEEPSEEK_API_KEY（DeepSeek API密钥）")
        if not cls.FEISHU_APP_ID:
            missing.append("FEISHU_APP_ID（飞书App ID）")
        if not cls.FEISHU_APP_SECRET:
            missing.append("FEISHU_APP_SECRET（飞书App Secret）")
        if not cls.FEISHU_RECEIVE_ID:
            missing.append("FEISHU_RECEIVE_ID（飞书推送目标ID）")
        return missing

    @classmethod
    def ensure_dirs(cls):
        """确保输出和日志目录存在"""
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)


# 预定义要监控的市场标的
WATCH_SYMBOLS = {
    "美股指数": {
        "^GSPC": "标普500",
        "^DJI": "道琼斯",
        "^IXIC": "纳斯达克",
        "^VIX": "恐慌指数VIX",
    },
    "外汇": {
        "USDCNY=X": "美元/人民币",
        "DX-Y.NYB": "美元指数",
        "EURUSD=X": "欧元/美元",
        "USDJPY=X": "美元/日元",
    },
    "大宗商品": {
        "GC=F": "黄金",
        "CL=F": "原油WTI",
        "HG=F": "铜",
    },
    "加密货币": {
        "BTC-USD": "比特币",
    },
    "中概股ETF": {
        "FXI": "中国大盘ETF",
        "KWEB": "中概互联网ETF",
        "ASHR": "沪深300 ETF",
    },
}


if __name__ == "__main__":
    Config.ensure_dirs()
    missing = Config.validate()
    if missing:
        print("⚠️  缺少以下配置：")
        for m in missing:
            print(f"   - {m}")
        print("\n请复制 .env.example 为 .env 并填写对应值")
    else:
        print("✅ 配置校验通过")
        print(f"   LLM: {Config.LLM_MODEL} @ {Config.LLM_BASE_URL}")
        print(f"   推送时间: {Config.PUSH_HOUR:02d}:{Config.PUSH_MINUTE:02d}")
        print(f"   飞书目标: {Config.FEISHU_RECEIVE_ID_TYPE}={Config.FEISHU_RECEIVE_ID}")
