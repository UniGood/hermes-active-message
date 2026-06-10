#!/usr/bin/env python3
"""主动消息历史记录管理"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _history_path() -> Path:
    return Path.home() / ".hermes" / "active-message" / "history.jsonl"


def _topic_history_path() -> Path:
    return Path.home() / ".hermes" / "active-message" / "topic_history.json"


def append_history(record: dict[str, Any]) -> None:
    """追加一条历史记录到 history.jsonl"""
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_topic_history() -> dict[str, Any]:
    """加载话题使用历史"""
    path = _topic_history_path()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_topic_history(data: dict[str, Any]) -> None:
    """保存话题使用历史"""
    path = _topic_history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def update_topic_history(topic_id: str, now: datetime, user_replied: bool = False) -> None:
    """更新话题使用历史"""
    history = load_topic_history()
    if topic_id not in history:
        history[topic_id] = {
            "last_used": None,
            "use_count": 0,
            "reply_count": 0,
            "avg_reply_delay_seconds": None,
        }
    
    entry = history[topic_id]
    entry["last_used"] = now.isoformat()
    entry["use_count"] = entry.get("use_count", 0) + 1
    if user_replied:
        entry["reply_count"] = entry.get("reply_count", 0) + 1
    
    save_topic_history(history)


def get_recent_topic_ids(hours: int = 2) -> list[str]:
    """获取最近N小时内使用过的话题ID"""
    history = load_topic_history()
    if not history:
        return []
    
    now = datetime.now()
    recent_ids = []
    for topic_id, entry in history.items():
        last_used = entry.get("last_used")
        if not last_used:
            continue
        try:
            last_used_dt = datetime.fromisoformat(last_used)
            if (now - last_used_dt).total_seconds() / 3600 < hours:
                recent_ids.append(topic_id)
        except (ValueError, TypeError):
            continue
    
    return recent_ids
