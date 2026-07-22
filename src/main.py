"""
股票国际市场早报 Agent - 主入口

启动方式：
    python main.py              # 启动飞书机器人（长连接 + 定时推送）
    python main.py test         # 测试飞书连接
    python main.py report       # 立即生成并推送一次早报
    python main.py fetch        # 仅采集数据（调试用）
    python main.py analyze      # 仅生成分析（调试用，输出到本地HTML）
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

from config import Config


def setup_logging():
    """配置日志：同时输出到控制台和文件"""
    Config.ensure_dirs()
    log_file = Config.LOG_DIR / f"morning_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=Config.LOG_LEVEL,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def cmd_test():
    """测试飞书连接"""
    from feishu_bot import FeishuBot

    bot = FeishuBot()
    print("发送测试卡片到飞书...")
    if bot.test_send():
        print("✅ 测试成功！请到飞书查看是否收到消息")
    else:
        print("❌ 测试失败，请检查配置和网络")


def cmd_report():
    """立即生成并推送早报"""
    from feishu_bot import FeishuBot

    bot = FeishuBot()
    bot.generate_and_push_report()


def cmd_fetch():
    """仅采集数据，打印结果"""
    from data_fetcher import collect_all_data

    data = collect_all_data()
    print(f"\n{'='*60}")
    print(f"采集时间: {data['collected_at']}")
    print(f"{'='*60}")

    print(f"\n📊 行情 ({len(data['quotes'])} 个标的):")
    for symbol, q in data["quotes"].items():
        print(
            f"  {q['category']:>8} | {q['name']:<12} | {q['price']:>10} | {q['direction']}{q['change_pct']}%"
        )

    print(f"\n📰 新闻 ({len(data['news'])} 条):")
    for n in data["news"][:10]:
        print(f"  [{n.get('time','')}] {n.get('title','')[:60]}")

    print(f"\n📅 今日事件 ({len(data['events'])} 条):")
    for e in data["events"][:10]:
        print(f"  {e.get('country','')} - {e.get('event','')}")


def cmd_analyze():
    """生成分析并保存为本地 HTML 文件"""
    from analyzer import MarketAnalyzer
    from data_fetcher import collect_all_data
    from formatter import format_html, format_markdown

    print("Step 1: 采集数据...")
    data = collect_all_data()

    print("Step 2: AI 研判...")
    analyzer = MarketAnalyzer()
    report = analyzer.generate_morning_report(data)

    print("Step 3: 生成文件...")
    html = format_html(report, data["quotes"])
    html_path = Config.OUTPUT_DIR / f"morning_{datetime.now().strftime('%Y%m%d')}.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"  ✅ HTML: {html_path}")

    md = format_markdown(report, data["quotes"])
    md_path = Config.OUTPUT_DIR / f"morning_{datetime.now().strftime('%Y%m%d')}.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"  ✅ Markdown: {md_path}")

    print(f"\n{'='*60}")
    print(f"📊 {report['date']} 星期{report['weekday']} 市场早报")
    print(f"{'='*60}")
    print(f"\n情绪: {report['overall_sentiment']}")
    print(f"\n【行情综述】\n{report['market_summary']}")
    print(f"\n【重要新闻】")
    for n in report["key_news"]:
        print(f"  [{n.get('sentiment','')}] {n.get('title','')}")
        print(f"    → {n.get('impact_chain','')}")
    print(f"\n【A股研判】\n{report['a_share_impact']}")
    print(f"\n【今日关注】\n{report['today_focus']}")


def cmd_serve():
    """启动飞书机器人服务（长连接 + 定时推送）"""
    from feishu_bot import FeishuBot
    from scheduler import ReportScheduler

    bot = FeishuBot()

    scheduler = ReportScheduler(bot)
    scheduler.start()

    print("\n" + "=" * 60)
    print("🚀 股票市场早报 Agent 已启动")
    print("=" * 60)
    print(f"  📅 定时推送: 每日 {Config.PUSH_HOUR:02d}:{Config.PUSH_MINUTE:02d}")
    print(f"  💬 对话方式: 飞书中 @机器人 提问")
    print(f"  📦 推送目标: {Config.FEISHU_RECEIVE_ID_TYPE}={Config.FEISHU_RECEIVE_ID}")
    print("=" * 60)
    print("\n按 Ctrl+C 退出\n")

    try:
        bot.start_listener()
    except KeyboardInterrupt:
        print("\n\n👋 正在退出...")
        scheduler.stop()


def main():
    setup_logging()

    missing = Config.validate()
    if missing and len(sys.argv) <= 1 or (len(sys.argv) > 1 and sys.argv[1] not in ["fetch"]):
        if missing:
            print("⚠️  配置不完整，缺少以下项：")
            for m in missing:
                print(f"   - {m}")
            print("\n请复制 .env.example 为 .env 并填写对应值")
            print("（fetch 命令不需要 LLM 和飞书配置，可直接使用）")
            sys.exit(1)

    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"

    commands = {
        "serve": cmd_serve,
        "test": cmd_test,
        "report": cmd_report,
        "fetch": cmd_fetch,
        "analyze": cmd_analyze,
    }

    if cmd not in commands:
        print(f"未知命令: {cmd}")
        print(f"可用命令: {', '.join(commands.keys())}")
        sys.exit(1)

    commands[cmd]()


if __name__ == "__main__":
    main()
