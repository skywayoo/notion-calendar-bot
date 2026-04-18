"""Entry point — aiohttp webhook mode for Railway."""
import asyncio
import logging
import os
import json
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Update
from telegram.ext import MessageHandler, CallbackQueryHandler, filters
import pytz

from config import TELEGRAM_CHAT_ID, TELEGRAM_BOT_TOKEN
from bot import get_app, handle_message, handle_confirm
from scheduler import send_today_summary, send_tomorrow_summary, check_reminders

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)
TZ = pytz.timezone("Asia/Taipei")

WEBHOOK_HOST = "https://calendar-bot-production-4ed8.up.railway.app"
PORT = int(os.environ.get("PORT", 8080))


async def main():
    app = get_app()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_confirm, pattern="^confirm:"))
    await app.initialize()
    await app.start()

    # Register webhook
    webhook_url = f"{WEBHOOK_HOST}/webhook"
    await app.bot.set_webhook(url=webhook_url, drop_pending_updates=True)
    log.info(f"Webhook set: {webhook_url}")

    # aiohttp handler
    async def handle_webhook(request: web.Request) -> web.Response:
        try:
            data = await request.json()
            update = Update.de_json(data, app.bot)
            await app.process_update(update)
        except Exception as e:
            log.error(f"Webhook error: {e}")
        return web.Response(text="ok")

    async def health(request: web.Request) -> web.Response:
        return web.Response(text="ok")

    # Start web server
    aio_app = web.Application()
    aio_app.router.add_post("/webhook", handle_webhook)
    aio_app.router.add_get("/", health)
    runner = web.AppRunner(aio_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    log.info(f"Server started on port {PORT}")

    await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="📅 行事曆 Bot 已啟動（Webhook）！")

    # Scheduler
    scheduler = AsyncIOScheduler(timezone=TZ)
    scheduler.add_job(send_today_summary, CronTrigger(hour=8, minute=0, timezone=TZ), args=[app.bot, TELEGRAM_CHAT_ID])
    scheduler.add_job(send_tomorrow_summary, CronTrigger(hour=20, minute=0, timezone=TZ), args=[app.bot, TELEGRAM_CHAT_ID])
    scheduler.add_job(check_reminders, "interval", minutes=1, args=[app.bot, TELEGRAM_CHAT_ID])
    scheduler.start()

    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown()
        await runner.cleanup()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
