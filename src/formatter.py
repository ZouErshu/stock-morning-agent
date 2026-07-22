"""
报告格式化模块 - 把 AI 研判结果格式化为飞书卡片 / Markdown / HTML
"""
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

SENTIMENT_STYLE = {
    "偏多": {"emoji": "🔴", "color": "red", "tag": "利好"},
    "偏空": {"emoji": "🟢", "color": "green", "tag": "利空"},
    "中性": {"emoji": "⚪", "color": "grey", "tag": "中性"},
    "利好": {"emoji": "🔴", "color": "red", "tag": "利好"},
    "利空": {"emoji": "🟢", "color": "green", "tag": "利空"},
}

QUOTE_COLOR = {"↑": "red", "↓": "green", "→": "grey"}


def format_feishu_card(report: dict, quotes: dict = None) -> dict:
    """格式化为飞书交互式卡片消息 JSON"""
    date_str = f"{report['date']} 星期{report['weekday']}"
    sentiment = report.get("overall_sentiment", "中性")
    s_style = SENTIMENT_STYLE.get(sentiment, SENTIMENT_STYLE["中性"])

    elements = []

    elements.append(
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"📊 **全球市场早报**\n{s_style['emoji']} 今日A股情绪：**{sentiment}**",
            },
        }
    )

    elements.append({"tag": "hr"})

    if quotes:
        quote_lines = []
        for category in ["美股指数", "外汇", "大宗商品", "加密货币", "中概股ETF"]:
            cat_quotes = [q for q in quotes.values() if q["category"] == category]
            if cat_quotes:
                quote_lines.append(f"**{category}**")
                for q in cat_quotes:
                    color_emoji = (
                        "🔴" if q["direction"] == "↑" else ("🟢" if q["direction"] == "↓" else "⚪")
                    )
                    quote_lines.append(
                        f"  {color_emoji} {q['name']}：{q['price']} ({q['direction']}{q['change_pct']}%)"
                    )
                quote_lines.append("")

        elements.append(
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": "\n".join(quote_lines)},
            }
        )
        elements.append({"tag": "hr"})

    elements.append(
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"📝 **隔夜行情综述**\n\n{report.get('market_summary', '')}",
            },
        }
    )
    elements.append({"tag": "hr"})

    key_news = report.get("key_news", [])
    if key_news:
        news_lines = ["📰 **重要新闻影响分析**\n"]
        for i, n in enumerate(key_news, 1):
            title = n.get("title", "")
            sentiment_n = n.get("sentiment", "中性")
            n_style = SENTIMENT_STYLE.get(sentiment_n, SENTIMENT_STYLE["中性"])
            chain = n.get("impact_chain", "")
            sectors = n.get("affected_sectors", [])
            sectors_str = "、".join(sectors) if sectors else "—"

            news_lines.append(
                f"{i}. {n_style['emoji']} **{title}** [{sentiment_n}]"
            )
            news_lines.append(f"   → {chain}")
            news_lines.append(f"   📌 受影响板块：{sectors_str}\n")

        elements.append(
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": "\n".join(news_lines)},
            }
        )
        elements.append({"tag": "hr"})

    elements.append(
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"🎯 **今日A股综合研判**\n\n{s_style['emoji']} 情绪：**{sentiment}**\n\n{report.get('a_share_impact', '')}",
            },
        }
    )
    elements.append({"tag": "hr"})

    if report.get("today_focus"):
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"⏰ **今日关注**\n\n{report.get('today_focus', '')}",
                },
            }
        )

    elements.append({"tag": "hr"})
    elements.append(
        {
            "tag": "note",
            "elements": [
                {
                    "tag": "plain_text",
                    "content": f"⏱ 生成于 {report.get('analyzed_at','')} | 以上内容由AI分析，仅供参考，不构成投资建议",
                }
            ],
        }
    )

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"📊 {date_str} 市场早报",
            },
            "template": s_style["color"],
        },
        "elements": elements,
    }

    return card


def format_markdown(report: dict, quotes: dict = None) -> str:
    """格式化为 Markdown 纯文本"""
    date_str = f"{report['date']} 星期{report['weekday']}"
    sentiment = report.get("overall_sentiment", "中性")

    lines = [f"# 📊 {date_str} 市场早报", ""]

    if quotes:
        lines.append("## 📈 隔夜行情速览")
        lines.append("")
        for category in ["美股指数", "外汇", "大宗商品", "加密货币", "中概股ETF"]:
            cat_quotes = [q for q in quotes.values() if q["category"] == category]
            if cat_quotes:
                lines.append(f"### {category}")
                lines.append("| 标的 | 价格 | 涨跌幅 |")
                lines.append("|------|------|--------|")
                for q in cat_quotes:
                    lines.append(
                        f"| {q['name']} | {q['price']} | {q['direction']}{q['change_pct']}% |"
                    )
                lines.append("")

    lines.append("## 📝 隔夜行情综述")
    lines.append("")
    lines.append(report.get("market_summary", ""))
    lines.append("")

    key_news = report.get("key_news", [])
    if key_news:
        lines.append("## 📰 重要新闻影响分析")
        lines.append("")
        for i, n in enumerate(key_news, 1):
            lines.append(
                f"### {i}. {n.get('title','')} [{n.get('sentiment','')}]"
            )
            lines.append("")
            lines.append(f"**影响链路**：{n.get('impact_chain','')}")
            lines.append("")
            sectors = n.get("affected_sectors", [])
            if sectors:
                lines.append(f"**受影响板块**：{', '.join(sectors)}")
                lines.append("")

    lines.append("## 🎯 今日A股综合研判")
    lines.append("")
    lines.append(f"**整体情绪**：{sentiment}")
    lines.append("")
    lines.append(report.get("a_share_impact", ""))
    lines.append("")

    if report.get("today_focus"):
        lines.append("## ⏰ 今日关注")
        lines.append("")
        lines.append(report.get("today_focus", ""))
        lines.append("")

    lines.append("---")
    lines.append(
        f"*⏱ 生成于 {report.get('analyzed_at','')} | 以上内容由AI分析，仅供参考，不构成投资建议*"
    )

    return "\n".join(lines)


def format_html(report: dict, quotes: dict = None) -> str:
    """格式化为 HTML 页面（归档用）"""
    date_str = f"{report['date']} 星期{report['weekday']}"
    sentiment = report.get("overall_sentiment", "中性")
    s_color = SENTIMENT_STYLE.get(sentiment, {}).get("color", "grey")

    quotes_html = ""
    if quotes:
        for category in ["美股指数", "外汇", "大宗商品", "加密货币", "中概股ETF"]:
            cat_quotes = [q for q in quotes.values() if q["category"] == category]
            if cat_quotes:
                quotes_html += f'<h3>{category}</h3><table class="quote-table"><tr><th>标的</th><th>价格</th><th>涨跌幅</th></tr>'
                for q in cat_quotes:
                    color = "#e74c3c" if q["direction"] == "↑" else ("#27ae60" if q["direction"] == "↓" else "#7f8c8d")
                    quotes_html += f'<tr><td>{q["name"]}</td><td>{q["price"]}</td><td style="color:{color}">{q["direction"]}{q["change_pct"]}%</td></tr>'
                quotes_html += "</table>"

    news_html = ""
    for i, n in enumerate(report.get("key_news", []), 1):
        s = n.get("sentiment", "")
        s_color_n = SENTIMENT_STYLE.get(s, {}).get("color", "grey")
        news_html += f'<div class="news-item"><h4>{i}. {n.get("title","")} <span class="tag tag-{s_color_n}">{s}</span></h4>'
        news_html += f'<p class="chain">→ {n.get("impact_chain","")}</p>'
        sectors = n.get("affected_sectors", [])
        if sectors:
            news_html += '<p class="sectors">📌 受影响板块：' + "、".join(sectors) + "</p>"
        news_html += "</div>"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{date_str} 市场早报</title>
<style>
  body {{ font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; color: #333; line-height: 1.6; }}
  .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; }}
  .header h1 {{ margin: 0 0 10px 0; font-size: 24px; }}
  .sentiment {{ display: inline-block; padding: 4px 12px; border-radius: 16px; font-size: 14px; font-weight: bold; }}
  .sentiment-red {{ background: #fee; color: #e74c3c; }}
  .sentiment-green {{ background: #e8f8e8; color: #27ae60; }}
  .sentiment-grey {{ background: #f0f0f0; color: #7f8c8d; }}
  section {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  section h2 {{ margin-top: 0; color: #2c3e50; border-bottom: 2px solid #ecf0f1; padding-bottom: 8px; }}
  .quote-table {{ width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 14px; }}
  .quote-table th, .quote-table td {{ padding: 6px 10px; text-align: left; border-bottom: 1px solid #ecf0f1; }}
  .quote-table th {{ background: #f8f9fa; font-weight: 600; }}
  .news-item {{ padding: 12px 0; border-bottom: 1px solid #ecf0f1; }}
  .news-item:last-child {{ border-bottom: none; }}
  .news-item h4 {{ margin: 0 0 6px 0; font-size: 15px; }}
  .chain {{ color: #555; font-size: 14px; margin: 4px 0; }}
  .sectors {{ font-size: 13px; color: #7f8c8d; margin: 4px 0; }}
  .tag {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: bold; }}
  .tag-red {{ background: #fee; color: #e74c3c; }}
  .tag-green {{ background: #e8f8e8; color: #27ae60; }}
  .tag-grey {{ background: #f0f0f0; color: #7f8c8d; }}
  .footer {{ text-align: center; color: #95a5a6; font-size: 12px; padding: 20px; }}
</style>
</head>
<body>
  <div class="header">
    <h1>📊 {date_str} 市场早报</h1>
    <span class="sentiment sentiment-{s_color}">今日A股情绪：{sentiment}</span>
  </div>

  <section>
    <h2>📈 隔夜行情速览</h2>
    {quotes_html}
  </section>

  <section>
    <h2>📝 隔夜行情综述</h2>
    <p>{report.get('market_summary', '')}</p>
  </section>

  <section>
    <h2>📰 重要新闻影响分析</h2>
    {news_html}
  </section>

  <section>
    <h2>🎯 今日A股综合研判</h2>
    <p><strong>整体情绪：{sentiment}</strong></p>
    <p>{report.get('a_share_impact', '').replace(chr(10), '<br>')}</p>
  </section>

  <section>
    <h2>⏰ 今日关注</h2>
    <p>{report.get('today_focus', '').replace(chr(10), '<br>')}</p>
  </section>

  <div class="footer">
    ⏱ 生成于 {report.get('analyzed_at','')} | 以上内容由AI分析，仅供参考，不构成投资建议
  </div>
</body>
</html>"""
    return html
