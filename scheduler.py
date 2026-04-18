"""Scheduled jobs: reminders, daily summaries."""
from datetime import datetime, timedelta
import pytz
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from notion import get_events_range, mark_reminded
from gemini import format_schedule

log = logging.getLogger(__name__)
TZ = pytz.timezone("Asia/Taipei")


async def send_today_summary(bot, chat_id: int):
    now = datetime.now(TZ)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    events = get_events_range(start, end)
    await bot.send_message(chat_id=chat_id, text=format_schedule(events, "今天"))


async def send_tomorrow_summary(bot, chat_id: int):
    now = datetime.now(TZ)
    tomorrow = now + timedelta(days=1)
    start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
    end = tomorrow.replace(hour=23, minute=59, second=59, microsecond=0)
    events = get_events_range(start, end)
    await bot.send_message(chat_id=chat_id, text=format_schedule(events, "明天"))


async def _send_reminder(bot, chat_id: int, event: dict, minutes: int, notion_field: str):
    try:
        dt = datetime.fromisoformat(event["date"])
        time_str = dt.strftime("%H:%M")
    except Exception:
        time_str = event.get("date", "")

    desc = f"\n備註：{event['description']}" if event.get("description") else ""
    label = {"已提醒": "30", "提醒10": "10", "提醒5": "5"}.get(notion_field, str(minutes))
    msg = f"⏰ {label} 分鐘後的行程\n\n📌 {event['title']}\n🕐 {time_str}{desc}"

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ 確認，不再提醒", callback_data=f"confirm:{event['id']}")
    ]])
    await bot.send_message(chat_id=chat_id, text=msg, reply_markup=keyboard)
    mark_reminded(event["id"], notion_field)
    log.info(f"Reminder ({label}min) sent for: {event['title']}")


async def check_reminders(bot, chat_id: int):
    now = datetime.now(TZ)

    checks = [
        (28, 32, "已提醒", "reminder_sent"),
        (8, 12, "提醒10", "reminder_10"),
        (3, 7, "提醒5", "reminder_5"),
    ]

    for w_start, w_end, field, key in checks:
        events = get_events_range(now + timedelta(minutes=w_start), now + timedelta(minutes=w_end))
        for e in events:
            if e.get("confirmed"):
                continue
            if e.get(key):
                continue
            await _send_reminder(bot, chat_id, e, w_start, field)
