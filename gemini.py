"""Gemini NLP: parse natural language calendar commands."""
import json
import re
from datetime import datetime, timedelta
import pytz
import google.generativeai as genai
from config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)

MODELS = ["gemma-4-26b-a4b-it", "gemini-2.5-flash", "gemini-2.0-flash"]

TZ = pytz.timezone("Asia/Taipei")

SYSTEM_PROMPT = """你是行事曆助理，只回傳 JSON，不要任何其他文字或 markdown。

現在時間：{now}（台灣時間，UTC+8）

輸出格式，嚴格只回傳這個 JSON：
{{"action":"...","title":"...","datetime":"...","description":"","query_start":"...","query_end":"...","search_keyword":"...","new_title":"...","new_datetime":"...","reply":"..."}}

欄位說明：
- action: "add"｜"delete"｜"edit"｜"query_date"｜"query_keyword"｜"unknown"
- title: 事件名稱（add 用）
- datetime: ISO8601 含時區，例如 2026-04-18T14:00:00+08:00（add/edit 用，不知道時間填 ""）
- description: 備註，沒有就填 ""（絕對不能是 null）
- query_start/query_end: ISO8601（query_date 用）
- search_keyword: 事件名稱關鍵字（delete/edit/query_keyword 用），不是時間詞
- new_title/new_datetime: edit 用，沒有就填 ""
- reply: 繁體中文確認訊息

action 判斷：
- 查今天/明天/後天/這週行程 → query_date
- 查某個事件名稱 → query_keyword
- 新增事件 → add
- 刪除事件 → delete
- 修改/改/更新事件 → edit

時間換算（請嚴格執行）：
- 今天={today}，明天={tomorrow}，後天={day_after}
- 早上/上午=AM，下午=PM（時間加12，例如下午3點=15:00），晚上=PM
- 「三點50」=15:50，「八點」=08:00，「十二點」=12:00
- 時區一律 +08:00
"""


def parse_command(text: str) -> dict:
    now_dt = datetime.now(TZ)
    now = now_dt.strftime("%Y-%m-%d %H:%M %A")
    tomorrow = (now_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    day_after = (now_dt + timedelta(days=2)).strftime("%Y-%m-%d")
    today = now_dt.strftime("%Y-%m-%d")
    prompt = SYSTEM_PROMPT.format(now=now, today=today, tomorrow=tomorrow, day_after=day_after) + f"\n\n使用者說：{text}"

    last_err = None
    for model_name in MODELS:
        try:
            model = genai.GenerativeModel(model_name)
            resp = model.generate_content(prompt)
            raw = resp.text.strip()
            # extract JSON
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception as e:
            last_err = e
            continue

    return {"action": "unknown", "reply": f"AI 解析失敗：{last_err}"}


def format_schedule(events: list[dict], label: str) -> str:
    if not events:
        return f"📅 {label}沒有行程"
    lines = [f"📅 {label}行程：\n"]
    for e in events:
        dt = e.get("date", "")
        time_str = ""
        if dt and "T" in dt:
            try:
                t = datetime.fromisoformat(dt)
                time_str = t.strftime("%H:%M ")
            except Exception:
                pass
        desc = f"\n   └ {e['description']}" if e.get("description") else ""
        lines.append(f"• {time_str}{e['title']}{desc}")
    return "\n".join(lines)
