"""Entry point."""
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.ext import MessageHandler, CallbackQueryHandler, filters
import pytz

from config import TELEGRAM_CHAT_ID
from bot import get_app, handle_message, handle_confirm
from scheduler import send_today_summary, send_tomorrow_summary, check_reminders

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)
TZ = pytz.timezone("Asia/Taipei")


async def main():
    app = get_app()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_confirm, pattern="^confirm:"))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    bot = app.bot
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="📅 行事曆 Bot 已啟動！\n\n你可以說：\n• 新增明天下午3點開會\n• 刪除明天的開會\n• 修改開會時間到4點\n• 今天有什麼行程")

    scheduler = AsyncIOScheduler(timezone=TZ)
    # 8am today summary
    scheduler.add_job(send_today_summary, CronTrigger(hour=8, minute=0, timezone=TZ), args=[bot, TELEGRAM_CHAT_ID])
    # 8pm tomorrow summary
    scheduler.add_job(send_tomorrow_summary, CronTrigger(hour=20, minute=0, timezone=TZ), args=[bot, TELEGRAM_CHAT_ID])
    # every minute: check 30min reminders
    scheduler.add_job(check_reminders, "interval", minutes=1, args=[bot, TELEGRAM_CHAT_ID])
    scheduler.start()

    log.info("Calendar bot running. Press Ctrl+C to stop.")
    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
