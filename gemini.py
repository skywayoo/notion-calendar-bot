"""Gemini NLP: parse natural language calendar commands."""
import json
import re
from datetime import datetime
import pytz
import google.generativeai as genai
from config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)

MODELS = ["gemma-4-26b-a4b-it", "gemini-2.5-flash", "gemini-2.0-flash"]

TZ = pytz.timezone("Asia/Taipei")

SYSTEM_PROMPT = """你是行事曆助理，解析繁體中文的行事曆指令並回傳 JSON。

現在時間：{now}（台灣時間，UTC+8）

回傳格式（只回傳 JSON，不要其他文字）：
{{
  "action": "add" | "delete" | "edit" | "query_date" | "query_keyword" | "unknown",
  "title": "事件名稱（add 用）",
  "datetime": "ISO8601 格式，例如 2026-04-18T14:00:00+08:00（add/edit 用）",
  "description": "備註（可空）",
  "query_start": "查詢開始時間 ISO8601（query_date 用，今天開始設為今天00:00:00+08:00）",
  "query_end": "查詢結束時間 ISO8601（query_date 用，今天結束設為今天23:59:59+08:00）",
  "search_keyword": "事件名稱關鍵字（query_keyword/delete/edit 用，不是時間詞）",
  "new_title": "新名稱（edit 時用，可空）",
  "new_datetime": "新時間（edit 時用，可空）",
  "reply": "給使用者看的確認訊息（繁體中文）"
}}

action 選擇規則：
- 「今天/明天/這週/有什麼行程」→ action=query_date，填 query_start/query_end，search_keyword 留空
- 「查 XX 的行程」XX 是事件名稱 → action=query_keyword，填 search_keyword
- 新增事件 → action=add
- 刪除事件 → action=delete，填 search_keyword（事件名稱）
- 修改事件 → action=edit，填 search_keyword（事件名稱）

時間規則：
- 「明天」= 明天日期，「後天」= 後天，「下週一」= 下週一
- 「早上/上午」= AM，「下午」= PM（12+小時），「晚上」= PM
- 沒給時間時設 datetime 為 null
"""


def parse_command(text: str) -> dict:
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M %A")
    prompt = SYSTEM_PROMPT.format(now=now) + f"\n\n使用者說：{text}"

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
