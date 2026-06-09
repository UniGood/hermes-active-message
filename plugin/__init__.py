from __future__ import annotations

import os
import sys
from pathlib import Path


LIB_DIR = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser() / "active-message"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from active_message_lib import (  # noqa: E402
    connect_db,
    ensure_runtime_state,
    fetch_latest_session,
    format_dt,
    get_now,
    load_feature_config,
    pending_restore_outputs,
    save_runtime_state,
    truncate_text,
)


def _format_restore_context(records):
    lines = [
        "以下是你最近主动发给用户的消息，这些消息不在当前对话历史中：",
    ]
    for record in records:
        lines.append(f"[AI助手] {format_dt(record.created_at)} {truncate_text(record.text, max_chars=220)}")
    lines.append("这些是你已经发过的消息，请勿重复发送。")
    return "\n".join(lines)


def restore_recent_proactive_messages(session_id: str, platform: str, **kwargs):
    config = load_feature_config()
    if platform != str(config.get("target_platform", "telegram")):
        return None
    if not config.get("enabled", True):
        return None

    with connect_db(config) as conn:
        session = fetch_latest_session(conn, config["target_user_id"], config.get("target_platform", "telegram"))

    if session is None:
        return None

    state = ensure_runtime_state(config)
    pending = pending_restore_outputs(config, state)
    if not pending:
        return None

    limit = int(config["restore_message_limit"])
    selected = pending[-limit:]
    latest = selected[-1]
    state["last_restored_output"] = latest.name
    state["last_restored_at"] = get_now(config).isoformat()
    state["last_seen_output"] = latest.name
    save_runtime_state(config, state)
    return {"context": _format_restore_context(selected)}


def register(ctx):
    ctx.register_hook("pre_llm_call", restore_recent_proactive_messages)
