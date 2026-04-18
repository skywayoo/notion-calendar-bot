"""Notion Calendar database CRUD."""
import requests
from datetime import datetime, date
from typing import Optional
from config import NOTION_API_KEY, NOTION_CALENDAR_DB_ID

HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def _get(p, key):
    prop = p.get(key, {})
    t = prop.get("type", "")
    if t == "title":
        items = prop.get("title", [])
        return items[0]["plain_text"] if items else ""
    if t == "rich_text":
        items = prop.get("rich_text", [])
        return items[0]["plain_text"] if items else ""
    if t == "date":
        d = prop.get("date")
        return d.get("start") if d else None
    if t == "checkbox":
        return prop.get("checkbox", False)
    return None


def _parse_event(page: dict) -> dict:
    p = page["properties"]
    return {
        "id": page["id"],
        "title": _get(p, "名稱"),
        "date": _get(p, "日期"),
        "description": _get(p, "備註"),
        "reminder_sent": _get(p, "已提醒"),
        "reminder_10": _get(p, "提醒10"),
        "reminder_5": _get(p, "提醒5"),
        "confirmed": _get(p, "已確認"),
    }


def create_database(parent_page_id: str) -> str:
    """Create the calendar database under a Notion page. Returns DB ID."""
    url = "https://api.notion.com/v1/databases"
    body = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": "行事曆"}}],
        "properties": {
            "名稱": {"title": {}},
            "日期": {"date": {}},
            "備註": {"rich_text": {}},
            "已提醒": {"checkbox": {}},
        },
    }
    r = requests.post(url, headers=HEADERS, json=body)
    r.raise_for_status()
    return r.json()["id"]


def get_events(start: str, end: str) -> list[dict]:
    """Query events between start and end (ISO date strings)."""
    url = f"https://api.notion.com/v1/databases/{NOTION_CALENDAR_DB_ID.replace('-','')}/query"
    body = {
        "filter": {
            "and": [
                {"property": "日期", "date": {"on_or_after": start}},
                {"property": "日期", "date": {"on_or_before": end}},
            ]
        },
        "sorts": [{"property": "日期", "direction": "ascending"}],
    }
    r = requests.post(url, headers=HEADERS, json=body)
    if not r.ok:
        print(f"[notion] query error: {r.text}")
        return []
    return [_parse_event(p) for p in r.json().get("results", [])]


def get_events_range(start_dt: datetime, end_dt: datetime) -> list[dict]:
    return get_events(start_dt.isoformat(), end_dt.isoformat())


def add_event(title: str, dt: str, description: str | None = "") -> dict:
    description = description or ""
    """Create a new event. dt is ISO datetime string e.g. '2026-04-18T14:00:00+08:00'"""
    url = "https://api.notion.com/v1/pages"
    body = {
        "parent": {"database_id": NOTION_CALENDAR_DB_ID},
        "properties": {
            "名稱": {"title": [{"text": {"content": title}}]},
            "日期": {"date": {"start": dt}},
            "備註": {"rich_text": [{"text": {"content": description}}]},
            "已提醒": {"checkbox": False},
        },
    }
    r = requests.post(url, headers=HEADERS, json=body)
    r.raise_for_status()
    return _parse_event(r.json())


def update_event(page_id: str, title: Optional[str] = None, dt: Optional[str] = None, description: Optional[str] = None) -> dict:
    url = f"https://api.notion.com/v1/pages/{page_id}"
    props = {}
    if title is not None:
        props["名稱"] = {"title": [{"text": {"content": title}}]}
    if dt is not None:
        props["日期"] = {"date": {"start": dt}}
        props["已提醒"] = {"checkbox": False}  # reset reminder on reschedule
    if description is not None:
        props["備註"] = {"rich_text": [{"text": {"content": description}}]}
    r = requests.patch(url, headers=HEADERS, json={"properties": props})
    r.raise_for_status()
    return _parse_event(r.json())


def delete_event(page_id: str):
    """Archive (delete) a page."""
    url = f"https://api.notion.com/v1/pages/{page_id}"
    requests.patch(url, headers=HEADERS, json={"archived": True})


def mark_reminded(page_id: str, field: str = "已提醒"):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    requests.patch(url, headers=HEADERS, json={"properties": {field: {"checkbox": True}}})


def mark_confirmed(page_id: str):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    requests.patch(url, headers=HEADERS, json={"properties": {"已確認": {"checkbox": True}}})


def search_events(keyword: str, days: int = 30) -> list[dict]:
    from datetime import timedelta
    import pytz
    tz = pytz.timezone("Asia/Taipei")
    now = datetime.now(tz)
    end = now + timedelta(days=days)
    events = get_events(now.isoformat(), end.isoformat())
    return [e for e in events if keyword.lower() in (e["title"] or "").lower() or keyword in (e["description"] or "")]
