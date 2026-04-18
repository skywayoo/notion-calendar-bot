"""Telegram bot handlers."""
import logging
from datetime import datetime, timedelta
import pytz
from telegram import Update
from telegram.ext import Application, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from gemini import parse_command, format_schedule
from notion import add_event, delete_event, update_event, search_events, get_events_range, mark_confirmed

log = logging.getLogger(__name__)
TZ = pytz.timezone("Asia/Taipei")


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    # Only respond to the owner
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return

    text = update.message.text.strip()
    await update.message.chat.send_action("typing")

    parsed = parse_command(text)
    action = parsed.get("action", "unknown")

    try:
        if action == "add":
            dt = parsed.get("datetime")
            title = parsed.get("title", "未命名事件")
            desc = parsed.get("description", "")
            if not dt:
                await update.message.reply_text("⚠️ 請告訴我事件的日期和時間")
                return
            event = add_event(title, dt, desc)
            try:
                t = datetime.fromisoformat(event["date"])
                time_str = t.strftime("%Y-%m-%d %H:%M")
            except Exception:
                time_str = event.get("date", "")
            await update.message.reply_text(
                f"✅ 已新增事件\n\n📌 {event['title']}\n🕐 {time_str}"
            )

        elif action == "delete":
            keyword = parsed.get("search_keyword", "")
            events = search_events(keyword)
            if not events:
                await update.message.reply_text(f"找不到包含「{keyword}」的事件")
            elif len(events) == 1:
                delete_event(events[0]["id"])
                await update.message.reply_text(f"🗑️ 已刪除：{events[0]['title']}")
            else:
                lines = ["找到多筆事件，請說更精確的名稱：\n"]
                for e in events[:5]:
                    lines.append(f"• {e['title']} ({e.get('date','')[:10]})")
                await update.message.reply_text("\n".join(lines))

        elif action == "edit":
            keyword = parsed.get("search_keyword", "")
            events = search_events(keyword)
            if not events:
                await update.message.reply_text(f"找不到包含「{keyword}」的事件")
            elif len(events) == 1:
                e = events[0]
                updated = update_event(
                    e["id"],
                    title=parsed.get("new_title") or None,
                    dt=parsed.get("new_datetime") or None,
                )
                await update.message.reply_text(f"✏️ 已更新：{updated['title']}")
            else:
                lines = ["找到多筆事件，請說更精確的名稱：\n"]
                for e in events[:5]:
                    lines.append(f"• {e['title']} ({e.get('date','')[:10]})")
                await update.message.reply_text("\n".join(lines))

        elif action == "query_date":
            qs = parsed.get("query_start")
            qe = parsed.get("query_end")
            if qs and qe:
                start = datetime.fromisoformat(qs)
                end = datetime.fromisoformat(qe)
            else:
                now = datetime.now(TZ)
                start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end = now.replace(hour=23, minute=59, second=59, microsecond=0)
            events = get_events_range(start, end)
            # build label from reply or date
            label = parsed.get("reply", "") or start.strftime("%m/%d")
            msg = format_schedule(events, label.replace("行程", "").strip() or start.strftime("%m/%d"))
            await update.message.reply_text(msg)

        elif action == "query_keyword":
            keyword = parsed.get("search_keyword", "")
            events = search_events(keyword)
            msg = format_schedule(events, f"「{keyword}」相關")
            await update.message.reply_text(msg)

        elif action == "query":  # fallback for old Gemini responses
            keyword = parsed.get("search_keyword", "")
            now = datetime.now(TZ)
            if keyword:
                events = search_events(keyword)
                msg = format_schedule(events, f"搜尋「{keyword}」")
            else:
                start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end = now.replace(hour=23, minute=59, second=59, microsecond=0)
                events = get_events_range(start, end)
                msg = format_schedule(events, "今天")
            await update.message.reply_text(msg)

        else:
            reply = parsed.get("reply", "")
            await update.message.reply_text(reply or "我不太懂你的意思，可以說「新增」、「刪除」、「修改」或「查詢」行程")

    except Exception as e:
        log.error(f"handle_message error: {e}")
        await update.message.reply_text(f"❌ 操作失敗：{e}")


async def handle_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if data.startswith("confirm:"):
        page_id = data[len("confirm:"):]
        mark_confirmed(page_id)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.edit_message_text(query.message.text + "\n\n✅ 已確認，不再提醒")


def get_app() -> Application:
    return Application.builder().token(TELEGRAM_BOT_TOKEN).build()
