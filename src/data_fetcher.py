"""
数据采集模块 - 抓取隔夜全球市场行情 + 财经新闻

数据源：
1. yfinance - 美股指数、外汇、大宗商品、加密货币、中概ETF
2. akshare  - 国内财经新闻、A股相关数据
3. 新浪财经 - 全球7x24小时快讯（备选）
"""
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

import akshare as ak
import pandas as pd
import yfinance as yf

from config import Config, WATCH_SYMBOLS

logger = logging.getLogger(__name__)


class MarketDataFetcher:
    """行情数据采集器"""

    def __init__(self):
        self.symbols = WATCH_SYMBOLS

    def fetch_all_quotes(self) -> dict:
        """抓取所有监控标的的行情"""
        logger.info("开始抓取全球市场行情...")
        all_quotes = {}

        for category, symbols in self.symbols.items():
            logger.info(f"  抓取 {category}...")
            for symbol, name in symbols.items():
                quote = self._fetch_single(symbol, name, category)
                if quote:
                    all_quotes[symbol] = quote
                time.sleep(0.2)  # 礼貌延迟，避免被限流

        logger.info(f"行情抓取完成，共获取 {len(all_quotes)} 个标的")
        return all_quotes

    def _fetch_single(self, symbol: str, name: str, category: str) -> Optional[dict]:
        """抓取单个标的的行情数据"""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d")

            if hist.empty:
                logger.warning(f"  {name}({symbol}) 无数据")
                return None

            latest = hist.iloc[-1]
            # 取最近一个交易日和前一交易日的收盘价
            if len(hist) >= 2:
                prev_close = hist.iloc[-2]["Close"]
            else:
                prev_close = latest["Close"]

            current = latest["Close"]
            change = current - prev_close
            change_pct = (change / prev_close * 100) if prev_close else 0

            quote = {
                "symbol": symbol,
                "name": name,
                "category": category,
                "price": round(float(current), 4),
                "change": round(float(change), 4),
                "change_pct": round(float(change_pct), 2),
                "direction": "↑" if change > 0 else ("↓" if change < 0 else "→"),
                "trade_date": hist.index[-1].strftime("%Y-%m-%d"),
            }
            logger.info(
                f"  ✅ {name}: {quote['price']} ({quote['direction']}{quote['change_pct']}%)"
            )
            return quote

        except Exception as e:
            logger.error(f"  ❌ {name}({symbol}) 抓取失败: {e}")
            return None


class NewsFetcher:
    """财经新闻采集器"""

    def fetch_global_news(self, limit: int = 20) -> list:
        """抓取全球财经快讯（使用 akshare 的全球财经直播）"""
        logger.info("开始抓取财经新闻...")

        news_list = []

        # 数据源1：akshare 全球财经直播
        try:
            news_list.extend(self._fetch_from_akshare(limit))
        except Exception as e:
            logger.error(f"akshare 新闻抓取失败: {e}")

        # 数据源2：东方财富快讯（备选）
        if len(news_list) < limit:
            try:
                news_list.extend(self._fetch_from_eastmoney(limit - len(news_list)))
            except Exception as e:
                logger.error(f"东方财富新闻抓取失败: {e}")

        # 去重 + 截断
        seen = set()
        unique_news = []
        for n in news_list:
            key = n.get("title", "")[:30]
            if key and key not in seen:
                seen.add(key)
                unique_news.append(n)

        logger.info(f"新闻抓取完成，共获取 {len(unique_news)} 条")
        return unique_news[:limit]

    def _fetch_from_akshare(self, limit: int) -> list:
        """从 akshare 抓取财经新闻"""
        news = []

        try:
            df = ak.stock_info_global_em()
            if df is not None and not df.empty:
                for _, row in df.head(limit).iterrows():
                    news.append(
                        {
                            "title": str(row.get("标题", "")).strip(),
                            "content": str(row.get("内容", "")).strip(),
                            "time": str(row.get("发布时间", "")).strip(),
                            "source": "东方财富-全球",
                        }
                    )
        except Exception as e:
            logger.warning(f"akshare 全球财经接口异常: {e}")

        return news

    def _fetch_from_eastmoney(self, limit: int) -> list:
        """从东方财富抓取快讯（直接请求接口）"""
        import requests

        news = []
        url = "https://np-cnbond.eastmoney.com/api/QuickNews/GetFastNewsList"
        params = {
            "client": "web",
            "biz": "web_724",
            "fastColumn": "102",
            "sortEnd": "",
            "pageSize": str(limit),
            "req_trace": str(int(time.time() * 1000)),
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://kuaixun.eastmoney.com/",
        }

        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            data = resp.json()
            items = data.get("data", {}).get("list", [])
            for item in items:
                news.append(
                    {
                        "title": item.get("title", "").strip(),
                        "content": item.get("digest", "").strip(),
                        "time": datetime.fromtimestamp(
                            int(item.get("showTime", 0))
                        ).strftime("%Y-%m-%d %H:%M")
                        if item.get("showTime")
                        else "",
                        "source": "东方财富-快讯",
                    }
                )
        except Exception as e:
            logger.warning(f"东方财富快讯接口异常: {e}")

        return news


def fetch_today_events() -> list:
    """抓取今日财经事件（经济数据发布、重要会议等）"""
    logger.info("抓取今日财经事件...")
    events = []

    try:
        # 使用 akshare 的百度股市通经济日历
        today_str = datetime.now().strftime("%Y%m%d")
        df = ak.news_economic_baidu(date=today_str)
        if df is not None and not df.empty:
            for _, row in df.head(15).iterrows():
                events.append(
                    {
                        "time": str(row.get("时间", "")),
                        "country": str(row.get("国家", "")),
                        "event": str(row.get("事件", "")),
                        "importance": str(row.get("重要性", "")),
                        "actual": str(row.get("今值", "")),
                        "forecast": str(row.get("预期", "")),
                        "previous": str(row.get("前值", "")),
                    }
                )
    except Exception as e:
        logger.warning(f"经济日历抓取失败: {e}")

    logger.info(f"今日事件抓取完成，共 {len(events)} 条")
    return events


def collect_all_data() -> dict:
    """一键采集所有数据"""
    fetcher = MarketDataFetcher()
    news_fetcher = NewsFetcher()

    quotes = fetcher.fetch_all_quotes()
    news = news_fetcher.fetch_global_news(limit=20)
    events = fetch_today_events()

    return {
        "quotes": quotes,
        "news": news,
        "events": events,
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
