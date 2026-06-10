from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

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
        "⚠️ 重要上下文：你（凯莉）最近主动发给曹凡的消息，这些消息不在当前对话历史中，但曹凡的回复很可能是针对这些消息的：",
    ]
    for record in records:
        # 格式：周三 19:37
        time_str = record.created_at.strftime("%a %H:%M") if record.created_at else "N/A"
        # 中文星期映射
        weekday_map = {"Mon": "周一", "Tue": "周二", "Wed": "周三", "Thu": "周四", "Fri": "周五", "Sat": "周六", "Sun": "周日"}
        for en, cn in weekday_map.items():
            time_str = time_str.replace(en, cn)
        lines.append(f"[凯莉主动发送] {time_str}: {truncate_text(record.text, max_chars=220)}")
    lines.append("")
    lines.append("👆 用户的回复是在延续上面的话题，请根据这些主动消息的内容来理解和回应用户，不要答非所问。")
    return "\n".join(lines)


def restore_recent_proactive_messages(session_id: str, platform: str, **kwargs):
    config = load_feature_config()
    if platform != str(config.get("target_platform", "telegram")):
        logger.debug("active-message hook: platform=%s != target, skip", platform)
        return None
    if not config.get("enabled", True):
        logger.debug("active-message hook: disabled")
        return None

    with connect_db(config) as conn:
        session = fetch_latest_session(conn, config["target_user_id"], config.get("target_platform", "telegram"))

    if session is None:
        logger.warning("active-message hook: no session found for user=%s source=%s",
                        config["target_user_id"], config.get("target_platform"))
        return None

    state = ensure_runtime_state(config)
    pending = pending_restore_outputs(config, state)
    if not pending:
        logger.debug("active-message hook: no pending outputs (last_restored=%s)", state.get("last_restored_output"))
        return None

    limit = int(config["restore_message_limit"])
    selected = pending[-limit:]
    latest = selected[-1]
    state["last_restored_output"] = latest.name
    state["last_restored_at"] = get_now(config).isoformat()
    state["last_seen_output"] = latest.name
    save_runtime_state(config, state)

    context = _format_restore_context(selected)
    logger.info("active-message hook: injected %d pending message(s) into context, latest=%s, preview=%s",
                len(selected), latest.name, truncate_text(latest.text, 60))
    return {"context": context}


def register(ctx):
    ctx.register_hook("pre_llm_call", restore_recent_proactive_messages)
