# hermes-active-message

给 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 加上**主动私聊**能力 — 定时向用户发送自然、有温度的对话消息。

不是简单的定时提醒。它会读取最近的聊天上下文，由 LLM 判断要不要发、发什么，确保每条消息都自然不突兀。

## 效果

```
[周六 07:21] 周六早上好呀，今天天气不错，好好享受周末~
[周六 08:20] 昨天那窗户没再卡吧？周末有啥安排没？
[周六 09:20] 周六上午过的咋样，有没有赖床 😄
```

## 架构

```
┌─────────────────────────────────────────────────────────┐
│  Cron Scheduler (每 20 分钟)                              │
│  0,20,40 6-23 * * *                                      │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│  build_context.py — 硬规则判定                            │
│                                                          │
│  ✓ 当前时间在活跃窗口内？                                   │
│  ✓ 用户空闲超过阈值？                                      │
│  ✓ 距上次主动消息超过冷却期？                                │
│  ✓ 今日未达发送上限？                                      │
│                                                          │
│  → 输出 SEND_DECISION: YES / NO / MAYBE                  │
│  → 附带最近聊天摘要 + 最近主动消息记录                       │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│  LLM 决策                                                │
│                                                          │
│  输入: SEND_DECISION + 聊天上下文 + 主动消息历史            │
│  输出: [SILENT] 或一条 1-2 句的自然消息                     │
│                                                          │
│  模型可以基于上下文自由判断：                                │
│  - 延续昨天的话题                                          │
│  - 关心用户近况                                            │
│  - 分享有趣的事                                           │
│  - 或者什么都不发 ([SILENT])                               │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│  消息投递 → 用户微信 / Telegram / 飞书                     │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│  pre_llm_call Hook — 上下文恢复                            │
│                                                          │
│  用户下次回复时，plugin hook 自动注入:                      │
│  "你之前发了这些主动消息，不要重复说"                        │
│                                                          │
│  → 避免会话断裂，模型知道之前说过什么                        │
└─────────────────────────────────────────────────────────┘
```

## 特性

- **硬规则兜底** — 空闲阈值、冷却期、每日上限，不会刷屏
- **LLM 自主决策** — 模型可以选择不发 ([SILENT])，不是机械定时器
- **上下文感知** — 读取最近聊天记录，延续自然话题
- **上下文恢复** — 用户回复时自动注入之前的主动消息，避免会话断裂
- **平台无关** — 支持微信、Telegram、飞书等任何 Hermes 已接入的平台
- **纯插件实现** — 不修改 Hermes 核心代码，通过 plugin hook + cron 实现

## 安装

### 方法一: 自动安装

```bash
cd /tmp
git clone https://github.com/UniGood/hermes-active-message.git
cd hermes-active-message
bash install.sh
```

### 方法二: 手动安装

```bash
# 1. 安装依赖
pip3 install pyyaml

# 2. 复制核心库
mkdir -p ~/.hermes/active-message
cp lib/active_message_lib.py ~/.hermes/active-message/
cp scripts/build_context.py ~/.hermes/active-message/
cp prompts/cron_prompt.txt ~/.hermes/active-message/

# 3. 复制 plugin hook
mkdir -p ~/.hermes/plugins/active-message
cp plugin/__init__.py ~/.hermes/plugins/active-message/
cp plugin/plugin.yaml ~/.hermes/plugins/active-message/

# 4. 复制 cron 入口脚本
mkdir -p ~/.hermes/scripts
cp scripts/cron_entry.py ~/.hermes/scripts/active-message-build-context.py
chmod +x ~/.hermes/scripts/active-message-build-context.py

# 5. 创建配置文件
cp config.example.yaml ~/.hermes/active-message/config.yaml
# 编辑配置，填入你的 target_chat_id 和 target_user_id
```

## 配置

编辑 `~/.hermes/active-message/config.yaml`:

```yaml
enabled: true

# 目标平台
target_platform: weixin          # weixin / telegram / feishu
target_chat_id: "xxx@im.wechat"  # 你的 chat_id
target_user_id: "xxx@im.wechat"  # 你的 user_id

# 活跃窗口
active_window_start: "06:30"     # 最早发送时间
active_window_end: "00:00"       # 最晚发送时间 (00:00 = 午夜)

# 触发条件
min_user_idle_minutes: 15        # 用户空闲多久才触发
min_proactive_gap_minutes: 30    # 两次主动消息最小间隔
daily_send_limit: 8              # 每天最多几条
```

### 参数调优

| 场景 | idle_min | gap_min | daily | cron频率 |
|------|----------|---------|-------|----------|
| 保守模式 | 60 | 120 | 4 | every 30m |
| 正常使用 | 15 | 30 | 8 | 每20分钟 |
| 激进测试 | 5 | 15 | 12 | every 10m |

### 获取 chat_id

**微信**: 通过 Hermes 查看 gateway 日志，找到 `chat_id` 格式类似 `xxx@im.wechat`

**Telegram**: 发送 `/start` 给 [@userinfobot](https://t.me/userinfobot) 获取你的数字 ID

## Hermes 配置

在 Hermes 的 `config.yaml` 中需要两处配置:

### 1. 启用 plugin hook

```yaml
plugins:
  enabled:
    - active-message
```

> ⚠️ 不加这行，`pre_llm_call` hook 不会执行，上下文恢复不工作

### 2. 关闭 cron 响应包装

```yaml
cron:
  wrap_response: false
```

### 3. 创建 cron job

在 Hermes 对话中让 Agent 执行:

```
hermes cron create "0,20,40 6-23 * * *" \
  "$(< ~/.hermes/active-message/cron_prompt.txt)" \
  --name active-message \
  --script active-message-build-context.py \
  --deliver weixin:YOUR_CHAT_ID
```

或直接让 Hermes Agent 帮你创建，告诉它:
> 帮我创建一个 cron job，每 20 分钟跑一次主动消息脚本，deliver 到微信

### 4. 重启 gateway

```bash
hermes gateway restart
```

## 验证

```bash
# 测试脚本是否正常
python3 ~/.hermes/active-message/build_context.py

# 检查输出:
# SEND_DECISION=YES → 允许发送
# SEND_DECISION=NO  → 不满足条件 (看 REASON)
```

## 文件结构

安装后的文件分布:

```
~/.hermes/
├── active-message/
│   ├── active_message_lib.py    # 核心库
│   ├── build_context.py         # 上下文构建脚本
│   ├── cron_prompt.txt          # LLM prompt
│   ├── config.yaml              # 配置文件 (不入库)
│   ├── state.json               # 运行时状态 (不入库)
│   └── .gitignore
├── plugins/active-message/
│   ├── __init__.py              # pre_llm_call hook
│   └── plugin.yaml
└── scripts/
    └── active-message-build-context.py  # cron 入口
```

## 工作原理详解

### 硬规则判定 (build_context.py)

脚本从 Hermes 的 state.db 中查询:
- 最近的用户消息时间 → 判断空闲
- 最近的主动消息 → 判断冷却
- 当天发送计数 → 判断上限

所有条件满足 → `SEND_DECISION=YES`

### LLM 决策

prompt 告诉模型:
- 如果 `SEND_DECISION=NO`，必须输出 `[SILENT]`
- 如果 YES，可以基于聊天上下文发送 1-2 句自然消息
- 不能暴露 cron/脚本等机制
- 不能重复最近发过的内容

### 上下文恢复 (plugin hook)

cron job 的输出不在用户对话的 session 中，所以用户回复时模型不知道之前发了什么。`pre_llm_call` hook 会:
1. 找到游标之后的新主动消息
2. 注入为上下文: "你之前发了这些消息，不要重复"
3. 更新游标避免重复注入

## 踩坑记录

### plugins.enabled 必须配置

Hermes plugin 系统是 **opt-in** 的。不加 `plugins.enabled: [active-message]`，hook 永远不执行。

### cron.wrap_response: false

不设置的话，cron 响应会被包装成系统消息，用户看到的格式不对。

### session_id 格式不匹配

Gateway 传给 hook 的 session_id 格式 (`agent:main:weixin:dm:USER_ID`) 和数据库里存的格式 (`20260605_102238_xxx`) 不同。本项目使用 `fetch_latest_session()` 按 platform+user_id 查询，绕过了这个问题。

### active_window_end: "24:00" 会报错

Python 的 `datetime.replace(hour=24)` 直接抛异常。用 `"00:00"` 代替，代码里已处理。

### 凌晨不跑省 token

即使活跃窗口外，cron 仍会触发脚本+LLM。如果窗口是 06:30-00:00，cron 设为 `0,20,40 6-23 * * *`，凌晨完全不触发。

## 微信平台适配

原项目默认为 Telegram 设计，微信需要修改:

1. **plugin/__init__.py** — "Telegram user" → "the user"
2. **prompts/cron_prompt.txt** — 所有 "Telegram" → "微信"
3. **config.yaml** — `target_platform: weixin`

详见 [references/weixin-adaptation.md](references/weixin-adaptation.md)

## 许可

MIT
