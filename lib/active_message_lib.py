from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml


DEFAULT_HERMES_HOME = Path.home() / ".hermes"


@dataclass
class OutputRecord:
    name: str
    path: Path
    text: str
    silent: bool
    created_at: datetime


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", str(DEFAULT_HERMES_HOME))).expanduser()


def default_config_path() -> Path:
    return hermes_home() / "active-message" / "config.yaml"


def _expand(value: str | Path) -> Path:
    return Path(str(value)).expanduser()


def load_feature_config(path: Path | None = None) -> dict[str, Any]:
    target = path or default_config_path()
    with target.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data


def get_timezone(config: dict[str, Any]) -> ZoneInfo:
    return ZoneInfo(config.get("timezone", "Asia/Shanghai"))


def get_now(config: dict[str, Any]) -> datetime:
    return datetime.now(get_timezone(config))


def read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError):
        pass
    return dict(default or {})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)


def ensure_runtime_state(config: dict[str, Any]) -> dict[str, Any]:
    path = _expand(config["state_file"])
    state = read_json(
        path,
        default={
            "last_restored_output": None,
            "last_restored_at": None,
            "last_seen_output": None,
        },
    )
    if not path.exists():
        write_json(path, state)
    return state


def save_runtime_state(config: dict[str, Any], state: dict[str, Any]) -> None:
    write_json(_expand(config["state_file"]), state)


def connect_db(config: dict[str, Any]) -> sqlite3.Connection:
    conn = sqlite3.connect(_expand(config["db_path"]))
    conn.row_factory = sqlite3.Row
    return conn


def resolve_job_id(config: dict[str, Any]) -> str | None:
    jobs_file = _expand(config["jobs_file"])
    if not jobs_file.exists():
        return None
    jobs = read_json(jobs_file, default={})
    items: list[dict[str, Any]]
    if isinstance(jobs, list):
        items = jobs
    elif isinstance(jobs, dict):
        raw_items = jobs.get("jobs", [])
        items = raw_items if isinstance(raw_items, list) else []
    else:
        items = []
    target_name = config.get("cron_job_name")
    for item in items:
        if item.get("name") == target_name and item.get("id"):
            return str(item["id"])
    return None


def active_window_bounds(now: datetime, config: dict[str, Any]) -> tuple[datetime, datetime]:
    start_h, start_m = [int(part) for part in str(config["active_window_start"]).split(":", 1)]
    end_h, end_m = [int(part) for part in str(config["active_window_end"]).split(":", 1)]
    start_dt = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    if end_h == 0 and end_m == 0:
        end_dt = (start_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        if now < start_dt:
            end_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start_dt, end_dt
    end_dt = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
        if now < start_dt:
            start_dt -= timedelta(days=1)
            end_dt -= timedelta(days=1)
    return start_dt, end_dt


def in_active_window(now: datetime, config: dict[str, Any]) -> bool:
    start_dt, end_dt = active_window_bounds(now, config)
    return start_dt <= now < end_dt


def next_window_start(now: datetime, config: dict[str, Any]) -> datetime:
    start_h, start_m = [int(part) for part in str(config["active_window_start"]).split(":", 1)]
    candidate = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    if now < candidate:
        return candidate
    return candidate + timedelta(days=1)


def format_dt(value: datetime | None) -> str:
    if value is None:
        return "N/A"
    return value.strftime("%Y-%m-%d %H:%M:%S %Z")


def ts_to_dt(ts: float | int | None, tz: ZoneInfo) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(float(ts), tz=tz)


def fetch_latest_session(conn: sqlite3.Connection, target_user_id: str, source: str) -> sqlite3.Row | None:
    query = """
        SELECT
            s.id,
            s.title,
            s.started_at,
            s.ended_at,
            MAX(m.timestamp) AS last_message_at
        FROM sessions s
        LEFT JOIN messages m ON m.session_id = s.id
        WHERE s.source = ? AND s.user_id = ?
        GROUP BY s.id, s.title, s.started_at, s.ended_at
        ORDER BY COALESCE(MAX(m.timestamp), s.started_at) DESC
        LIMIT 1
    """
    return conn.execute(query, (source, target_user_id)).fetchone()


def fetch_session_by_id(conn: sqlite3.Connection, session_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id, source, user_id, title, started_at, ended_at FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()


def fetch_recent_messages(conn: sqlite3.Connection, session_id: str, limit: int) -> list[sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT role, content, timestamp
        FROM messages
        WHERE session_id = ?
          AND role IN ('user', 'assistant')
          AND content IS NOT NULL
          AND TRIM(content) <> ''
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (session_id, limit),
    ).fetchall()
    return list(reversed(rows))


def fetch_last_user_message_time(conn: sqlite3.Connection, target_user_id: str, source: str) -> float | None:
    row = conn.execute(
        """
        SELECT MAX(m.timestamp) AS ts
        FROM messages m
        JOIN sessions s ON s.id = m.session_id
        WHERE s.source = ?
          AND s.user_id = ?
          AND m.role = 'user'
        """,
        (source, target_user_id),
    ).fetchone()
    if row is None:
        return None
    return row["ts"]


def _normalize_output_text(text: str) -> str:
    value = text.strip()
    if "\n## Response\n" in value:
        response = value.split("\n## Response\n", 1)[1].strip()
        return response
    if not value.startswith("Cronjob Response:"):
        return value
    lines = value.splitlines()
    if len(lines) < 4:
        return value
    if lines[0].startswith("Cronjob Response:") and lines[1].startswith("-------------"):
        core = "\n".join(lines[3:])
        footer = "\n\nNote: The agent cannot see this message, and therefore cannot respond to it."
        if core.endswith(footer):
            core = core[: -len(footer)]
        return core.strip()
    return value


def list_output_records(config: dict[str, Any]) -> list[OutputRecord]:
    job_id = resolve_job_id(config)
    if not job_id:
        return []
    root = _expand(config["output_root"]) / job_id
    if not root.exists():
        return []
    records: list[OutputRecord] = []
    for path in sorted(root.glob("*.md")):
        try:
            raw = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        text = _normalize_output_text(raw)
        silent = text.startswith("[SILENT]")
        created_at = datetime.fromtimestamp(path.stat().st_mtime, tz=get_timezone(config))
        records.append(OutputRecord(name=path.name, path=path, text=text, silent=silent, created_at=created_at))
    return records


def non_silent_outputs(config: dict[str, Any]) -> list[OutputRecord]:
    return [record for record in list_output_records(config) if not record.silent]


def recent_proactive_outputs(config: dict[str, Any], limit: int) -> list[OutputRecord]:
    return non_silent_outputs(config)[-limit:]


def pending_restore_outputs(config: dict[str, Any], state: dict[str, Any]) -> list[OutputRecord]:
    last_restored = state.get("last_restored_output")
    records = non_silent_outputs(config)
    if not last_restored:
        return records
    return [record for record in records if record.name > str(last_restored)]


def today_proactive_count(config: dict[str, Any], now: datetime) -> int:
    return sum(1 for record in non_silent_outputs(config) if record.created_at.date() == now.date())


def last_proactive_time(config: dict[str, Any]) -> datetime | None:
    records = non_silent_outputs(config)
    return records[-1].created_at if records else None


def truncate_text(value: str, max_chars: int = 160) -> str:
    compact = " ".join(value.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "…"


def format_recent_messages(rows: list[sqlite3.Row], tz: ZoneInfo) -> str:
    if not rows:
        return "- none"
    lines = []
    for row in rows:
        dt = ts_to_dt(row["timestamp"], tz)
        label = "user" if row["role"] == "user" else "assistant"
        lines.append(f"- {format_dt(dt)} [{label}] {truncate_text(row['content'] or '')}")
    return "\n".join(lines)


def format_recent_outputs(records: list[OutputRecord]) -> str:
    if not records:
        return "- none"
    return "\n".join(f"- {format_dt(record.created_at)} {truncate_text(record.text)}" for record in records)


def compute_next_eligible_at(
    now: datetime,
    config: dict[str, Any],
    last_user_message_at: datetime | None,
    last_proactive_at: datetime | None,
    today_count: int,
) -> datetime:
    candidates: list[datetime] = []
    if not in_active_window(now, config):
        candidates.append(next_window_start(now, config))
    if last_user_message_at is not None:
        candidates.append(last_user_message_at + timedelta(minutes=int(config["min_user_idle_minutes"])))
    if last_proactive_at is not None:
        candidates.append(last_proactive_at + timedelta(minutes=int(config["min_proactive_gap_minutes"])))
    if today_count >= int(config["daily_send_limit"]):
        candidates.append(next_window_start(now + timedelta(days=1), config))
    return max(candidates) if candidates else now


def build_context_payload(config: dict[str, Any]) -> dict[str, Any]:
    tz = get_timezone(config)
    now = get_now(config)
    state = ensure_runtime_state(config)
    target_user_id = str(config["target_user_id"])
    target_source = str(config.get("target_platform", "telegram"))

    with connect_db(config) as conn:
        latest_session = fetch_latest_session(conn, target_user_id, target_source)
        latest_session_id = latest_session["id"] if latest_session else None
        recent_messages = fetch_recent_messages(conn, latest_session_id, int(config["recent_message_limit"])) if latest_session_id else []
        last_user_ts = fetch_last_user_message_time(conn, target_user_id, target_source)

    last_user_message_at = ts_to_dt(last_user_ts, tz)
    last_proactive_at = last_proactive_time(config)
    recent_outputs = recent_proactive_outputs(config, int(config["restore_message_limit"]))
    today_count = today_proactive_count(config, now)

    reasons: list[str] = []
    decision = "YES"
    if not in_active_window(now, config):
        decision = "NO"
        reasons.append("outside_active_window")
    if last_user_message_at is not None:
        min_idle_at = last_user_message_at + timedelta(minutes=int(config["min_user_idle_minutes"]))
        if now < min_idle_at:
            decision = "NO"
            reasons.append("user_recently_active")
    if last_proactive_at is not None:
        min_gap_at = last_proactive_at + timedelta(minutes=int(config["min_proactive_gap_minutes"]))
        if now < min_gap_at:
            decision = "NO"
            reasons.append("proactive_cooldown")
    if today_count >= int(config["daily_send_limit"]):
        decision = "NO"
        reasons.append("daily_limit_reached")
    if decision != "NO" and (latest_session is None or not recent_messages):
        decision = "MAYBE"
        reasons.append("thin_context")

    next_eligible = compute_next_eligible_at(now, config, last_user_message_at, last_proactive_at, today_count)
    return {
        "now": now,
        "decision": decision,
        "reasons": reasons or ["eligible"],
        "next_eligible_at": next_eligible,
        "latest_session": latest_session,
        "recent_messages": recent_messages,
        "recent_outputs": recent_outputs,
        "last_user_message_at": last_user_message_at,
        "last_proactive_at": last_proactive_at,
        "today_count": today_count,
        "state": state,
        "timezone": tz,
    }
