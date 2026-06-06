#!/usr/bin/env python3

from __future__ import annotations

from active_message_lib import (
    build_context_payload,
    format_dt,
    format_recent_messages,
    format_recent_outputs,
    load_feature_config,
)


def main() -> None:
    config = load_feature_config()
    payload = build_context_payload(config)
    latest_session = payload["latest_session"]

    print("ACTIVE_MESSAGE_CONTEXT_START")
    print("FEATURE=active-message")
    print(f"SEND_DECISION={payload['decision']}")
    print(f"REASON={','.join(payload['reasons'])}")
    print(f"NEXT_ELIGIBLE_AT={format_dt(payload['next_eligible_at'])}")
    print(f"NOW={format_dt(payload['now'])}")
    # System date for double confirmation
    import subprocess
    try:
        sys_date = subprocess.check_output(["date", "+%Y-%m-%d %H:%M:%S %A %Z"], text=True).strip()
        print(f"SYSTEM_DATE={sys_date}")
    except Exception:
        pass
    print(f"TARGET_PLATFORM={config['target_platform']}")
    print(f"TARGET_CHAT_ID={config['target_chat_id']}")
    print(f"TARGET_USER_ID={config['target_user_id']}")
    print(f"LAST_USER_MESSAGE_AT={format_dt(payload['last_user_message_at'])}")
    print(f"LAST_PROACTIVE_MESSAGE_AT={format_dt(payload['last_proactive_at'])}")
    print(f"TODAY_PROACTIVE_COUNT={payload['today_count']}")
    print(f"RECENT_SESSION_ID={latest_session['id'] if latest_session else 'N/A'}")
    print(f"RECENT_SESSION_TITLE={(latest_session['title'] or '').strip() if latest_session else 'N/A'}")
    print("RECENT_MESSAGES_START")
    print(format_recent_messages(payload["recent_messages"], payload["timezone"]))
    print("RECENT_MESSAGES_END")
    print("RECENT_PROACTIVE_OUTPUTS_START")
    print(format_recent_outputs(payload["recent_outputs"]))
    print("RECENT_PROACTIVE_OUTPUTS_END")
    print("ACTIVE_MESSAGE_CONTEXT_END")


if __name__ == "__main__":
    main()
