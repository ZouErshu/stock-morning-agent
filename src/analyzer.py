"""
AI 分析模块 - 使用 DeepSeek 进行市场研判

核心能力：
1. 新闻摘要与分类（按重要度+板块归类）
2. 影响链路分析（事件 → 传导路径 → A股板块影响）
3. 市场情绪判断（偏多/偏空/中性）
4. 今日关注事件解读
5. 对话式问答（飞书@机器人时调用）
6. 个性化分析（根据用户偏好调整分析角度）
"""
import json
import logging
from datetime import datetime
from typing import Optional

from openai import OpenAI

from config import Config

logger = logging.getLogger(__name__)


class MarketAnalyzer:
    """市场分析器 - 封装所有 LLM 调用"""

    def __init__(self):
        self.client = OpenAI(
            api_key=Config.LLM_API_KEY,
            base_url=Config.LLM_BASE_URL,
        )
        self.model = Config.LLM_MODEL
        self.temperature = Config.LLM_TEMPERATURE
        self._profile_manager = None  # 延迟加载

    @property
    def profile_manager(self):
        """延迟加载 ProfileManager，避免循环导入"""
        if self._profile_manager is None:
            from profile_manager import get_profile_manager
            self._profile_manager = get_profile_manager()
        return self._profile_manager

    def _chat(self, system_prompt: str, user_prompt: str, max_tokens: int = 2000) -> str:
        """统一的 LLM 调用封装"""
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return f"[分析失败: {e}]"

    def generate_morning_report(self, data: dict, open_id: str = None) -> dict:
        """
        生成完整早报分析

        输入: collect_all_data() 的返回值 + 可选的用户 open_id
        输出: {
            "market_summary": "隔夜行情综述",
            "key_news": [{"title", "impact_chain", "affected_sectors", "sentiment"}],
            "overall_sentiment": "偏多/偏空/中性",
            "a_share_impact": "对今日A股的综合研判",
            "today_focus": "今日关注事件解读",
        }
        """
        logger.info("开始生成 AI 市场研判...")

        # 获取个性化上下文
        personal_context = ""
        if open_id:
            personal_context = self.profile_manager.build_personalized_context(open_id)
            if personal_context:
                logger.info(f"已加载个性化偏好: {open_id[:20]}...")

        # Step 1: 行情综述
        market_summary = self._analyze_market_overview(data["quotes"], personal_context)

        # Step 2: 重要新闻筛选与影响分析
        key_news = self._analyze_news_impact(data["news"], personal_context)

        # Step 3: 综合情绪判断 + A股研判
        overall = self._judge_overall_sentiment(market_summary, key_news, personal_context)

        # Step 4: 今日事件解读
        today_focus = self._analyze_events(data["events"], personal_context)

        result = {
            "date": datetime.now().strftime("%Y年%m月%d日"),
            "weekday": ["一", "二", "三", "四", "五", "六", "日"][
                datetime.now().weekday()
            ],
            "market_summary": market_summary,
            "key_news": key_news,
            "overall_sentiment": overall["sentiment"],
            "a_share_impact": overall["a_share_impact"],
            "today_focus": today_focus,
            "analyzed_at": datetime.now().strftime("%H:%M"),
        }

        logger.info("AI 研判完成")
        return result

    def _analyze_market_overview(self, quotes: dict, personal_context: str = "") -> str:
        """分析隔夜行情"""
        if not quotes:
            return "今日未能获取行情数据"

        lines = []
        for category in ["美股指数", "外汇", "大宗商品", "加密货币", "中概股ETF"]:
            cat_quotes = [q for q in quotes.values() if q["category"] == category]
            if cat_quotes:
                lines.append(f"【{category}】")
                for q in cat_quotes:
                    lines.append(
                        f"  {q['name']}: {q['price']} ({q['direction']}{q['change_pct']}%)"
                    )

        quotes_text = "\n".join(lines)

        system_prompt = """你是一位资深的全球宏观策略分析师，擅长用简洁有力的语言概括市场全貌。
请基于给定的隔夜全球市场行情数据，写一段 150-250 字的隔夜行情综述。
要求：
1. 突出最关键的趋势变化（大涨大跌、背离现象、异常波动）
2. 用专业但通俗的语言，避免堆砌数字
3. 点出市场情绪基调（风险偏好上升/下降、避险情绪等）
4. 不要分点，写成一段流畅的文字"""

        if personal_context:
            system_prompt += personal_context

        user_prompt = f"以下是隔夜全球市场行情数据：\n\n{quotes_text}\n\n请生成行情综述。"

        return self._chat(system_prompt, user_prompt, max_tokens=500)

    def _analyze_news_impact(self, news: list, personal_context: str = "") -> list:
        """分析重要新闻及其对A股的影响链路"""
        if not news:
            return []

        news_text = "\n".join(
            [f"{i+1}. [{n.get('time','')}] {n.get('title','')}" for i, n in enumerate(news)]
        )

        system_prompt = """你是一位专注于A股市场的宏观策略分析师。
请从给定的财经新闻中，筛选出 5-8 条对今日A股市场有重要影响的新闻，并对每条做影响链路分析。

输出要求：严格输出 JSON 数组，每个元素包含：
- title: 新闻标题（精简版，不超过30字）
- importance: 重要度（高/中/低）
- impact_chain: 影响链路分析（事件→传导路径→A股影响），50-100字
- affected_sectors: 受影响板块（数组，如 ["半导体","新能源"]）
- sentiment: 对A股影响（利好/利空/中性）

只输出 JSON，不要任何其他文字。"""

        if personal_context:
            system_prompt += personal_context

        user_prompt = f"以下是隔夜财经新闻列表：\n\n{news_text}\n\n请筛选并分析。"

        result = self._chat(system_prompt, user_prompt, max_tokens=1500)

        try:
            result = result.strip()
            if result.startswith("```"):
                result = result.split("\n", 1)[1] if "\n" in result else result[3:]
            if result.endswith("```"):
                result = result.rsplit("```", 1)[0]
            result = result.strip()
            if result.startswith("json"):
                result = result[4:].strip()

            news_analysis = json.loads(result)
            if isinstance(news_analysis, list):
                return news_analysis[:8]
        except json.JSONDecodeError as e:
            logger.error(f"新闻分析 JSON 解析失败: {e}\n原始输出: {result[:200]}")

        return []

    def _judge_overall_sentiment(self, market_summary: str, key_news: list, personal_context: str = "") -> dict:
        """综合判断市场情绪和对A股的影响"""
        news_summary = "\n".join(
            [
                f"- {n.get('title','')}: {n.get('impact_chain','')}"
                for n in key_news
            ]
        )

        system_prompt = """你是一位资深A股策略分析师。
请基于隔夜行情综述和重要新闻影响分析，给出今日A股市场的综合研判。

输出要求：严格输出 JSON，包含：
- sentiment: 整体情绪（偏多/偏空/中性）
- a_share_impact: 对今日A股的综合研判，150-250字，包括：
  * 大盘大概率走势预判（高开/低开/震荡）
  * 重点关注的板块方向（利好板块 + 需要回避的板块）
  * 操作建议（偏进攻/偏防守/均衡）

只输出 JSON，不要其他文字。"""

        if personal_context:
            system_prompt += personal_context

        user_prompt = f"""隔夜行情综述：
{market_summary}

重要新闻影响分析：
{news_summary}

请给出今日A股综合研判。"""

        result = self._chat(system_prompt, user_prompt, max_tokens=600)

        try:
            result = result.strip()
            if result.startswith("```"):
                result = result.split("\n", 1)[1] if "\n" in result else result[3:]
            if result.endswith("```"):
                result = result.rsplit("```", 1)[0]
            result = result.strip()
            if result.startswith("json"):
                result = result[4:].strip()

            return json.loads(result)
        except json.JSONDecodeError:
            logger.error(f"情绪判断 JSON 解析失败")
            return {
                "sentiment": "中性",
                "a_share_impact": result[:200] if result else "研判生成失败",
            }

    def _analyze_events(self, events: list, personal_context: str = "") -> str:
        """分析今日财经事件"""
        if not events:
            return "今日无重要财经事件"

        events_text = "\n".join(
            [
                f"- {e.get('time','')} {e.get('country','')} {e.get('event','')} (预期:{e.get('forecast','-')}, 前值:{e.get('previous','-')})"
                for e in events[:10]
            ]
        )

        system_prompt = """你是一位宏观经济分析师。
请简要解读今日将公布的财经事件/数据，指出哪些需要重点关注以及对市场可能的影响。
输出 100-200 字的流畅文字，不要分点罗列。"""

        if personal_context:
            system_prompt += personal_context

        user_prompt = f"今日财经事件：\n{events_text}\n\n请简要解读。"

        return self._chat(system_prompt, user_prompt, max_tokens=400)

    def chat(self, user_message: str, context_data: Optional[dict] = None, open_id: str = None) -> str:
        """
        对话模式 - 飞书@机器人时调用

        Args:
            user_message: 用户的提问
            context_data: 可选的今日市场数据上下文
            open_id: 用户 open_id（用于加载个性化偏好）
        """
        system_prompt = """你是「市场早报助手」，一位专业的全球市场分析AI助手。
你可以帮助用户：
1. 解读全球市场行情（美股、外汇、商品、加密货币等）
2. 分析财经新闻对A股的影响
3. 解答投资相关的疑问
4. 提供板块和行业的研究视角

注意事项：
- 你的回答仅供参考，不构成投资建议
- 用专业但通俗的语言
- 回答简洁有力，避免冗长
- 如果用户提供的数据中有今日行情，优先基于这些数据回答"""

        # 注入个性化偏好
        if open_id:
            personal_context = self.profile_manager.build_personalized_context(open_id)
            if personal_context:
                system_prompt += personal_context

        # 如果有今日数据上下文，附加到 prompt
        if context_data:
            context = self._build_context(context_data)
            system_prompt += f"\n\n今日市场数据参考：\n{context}"

        return self._chat(system_prompt, user_message, max_tokens=1000)

    def _build_context(self, data: dict) -> str:
        """把市场数据构建成 LLM 上下文"""
        lines = []
        if data.get("quotes"):
            lines.append("【今日行情】")
            for q in list(data["quotes"].values())[:15]:
                lines.append(
                    f"  {q['name']}: {q['price']} ({q['direction']}{q['change_pct']}%)"
                )
        if data.get("news"):
            lines.append("\n【今日要闻】")
            for n in data["news"][:10]:
                lines.append(f"  - {n.get('title','')}")
        return "\n".join(lines)
