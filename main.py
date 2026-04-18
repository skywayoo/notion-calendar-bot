"""Entry point — webhook mode for Railway deployment."""
import asyncio
import logging
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.ext import MessageHandler, CallbackQueryHandler, filters
import pytz

from config import TELEGRAM_CHAT_ID, TELEGRAM_BOT_TOKEN
from bot import get_app, handle_message, handle_confirm
from scheduler import send_today_summary, send_tomorrow_summary, check_reminders

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)
TZ = pytz.timezone("Asia/Taipei")

WEBHOOK_URL = "https://calendar-bot-production-4ed8.up.railway.app"
PORT = int(os.environ.get("PORT", 8080))


async def main():
    app = get_app()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_confirm, pattern="^confirm:"))

    await app.initialize()
    await app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    await app.start()

    await app.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text="📅 行事曆 Bot 已啟動（Webhook 模式）！",
    )

    scheduler = AsyncIOScheduler(timezone=TZ)
    scheduler.add_job(send_today_summary, CronTrigger(hour=8, minute=0, timezone=TZ), args=[app.bot, TELEGRAM_CHAT_ID])
    scheduler.add_job(send_tomorrow_summary, CronTrigger(hour=20, minute=0, timezone=TZ), args=[app.bot, TELEGRAM_CHAT_ID])
    scheduler.add_job(check_reminders, "interval", minutes=1, args=[app.bot, TELEGRAM_CHAT_ID])
    scheduler.start()

    log.info(f"Starting webhook on port {PORT}")
    await app.updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=f"{WEBHOOK_URL}/webhook",
    )

    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
