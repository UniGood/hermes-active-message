# 微信平台适配指南

hermes-active-message 原版为 Telegram 设计，在微信平台上使用需要以下适配。

## 需要修改的地方

### 1. plugin/__init__.py

将 `_format_restore_context` 函数中的 `Telegram user` 改为平台无关的表述:

```python
# 修改前
"Recent proactive outgoing messages you already sent to this Telegram user..."

# 修改后
"Recent proactive outgoing messages you already sent to the user..."
```

### 2. prompts/cron_prompt.txt

将所有 `Telegram` 替换为 `微信`:

```
# 修改前
- 最近 Telegram 私聊会话摘要
- 最近主动外发消息摘要
- 优先延续最近 Telegram 聊天里的自然话题

# 修改后
- 最近微信私聊会话摘要
- 最近主动外发消息摘要
- 优先延续最近微信聊天里的自然话题
```

### 3. plugin/plugin.yaml

description 改为平台无关:

```yaml
# 修改前
description: Restore recent proactive Telegram messages into the next user turn.

# 修改后
description: Restore recent proactive messages into the next user turn.
```

### 4. config.yaml

```yaml
target_platform: weixin
target_chat_id: "xxx@im.wechat"
target_user_id: "xxx@im.wechat"
```

## 微信 chat_id 格式

微信的 chat_id 格式为 `随机字符串@im.wechat`，例如:
```
o9cq800B700qFq20-npef3QLNKSQ@im.wechat
```

user_id 和 chat_id 通常是同一个值。

## 微信特有的注意事项

### 消息实时性

Hermes 消息在会话结束或上下文压缩时才批量写入数据库。会话进行中的消息在内存里。这意味着:
- build_context.py 查询到的最近消息可能不是最新的
- 用户刚发的消息可能还没入库

但这不影响主动消息功能 — 最坏情况是多发一条，因为脚本认为用户空闲了。

### Gateway 重启

微信平台的 gateway 重启会导致短暂断连。重启前确保:
1. 备份 state.db
2. 通知用户

## 调参建议 (微信)

微信聊天频率通常比 Telegram 高，建议:

```yaml
# 微信推荐配置
min_user_idle_minutes: 15     # 微信用户回复较快，15分钟空闲合理
min_proactive_gap_minutes: 30  # 半小时一条不会刷屏
daily_send_limit: 8           # 每天最多8条
active_window_start: "06:30"  # 早起可能看到
active_window_end: "00:00"    # 不打扰深夜
```

如果用户反馈消息太多，调大 `min_user_idle_minutes` 和 `min_proactive_gap_minutes`。

## 飞书等其他平台

适配方式类似:
1. `config.yaml` 设置 `target_platform: feishu`
2. 填入对应的 chat_id / user_id
3. 修改 prompt 中的平台名称
4. 确保 Hermes gateway 已配置该平台
