# hermes-active-message

给 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 加上**主动私聊**能力 — 定时向用户发送自然、有温度的对话消息。

不是简单的定时提醒。它会读取最近的聊天上下文，由 LLM 判断要不要发、发什么，确保每条消息都自然不突兀。

---

## 效果

```
[周三 12:00] 中午了，今天吃啥呀？
[周三 18:20] 快六点啦，周三过半了，今晚打算吃点啥？
[周三 20:30] 今天过得怎么样？
```

用户回复"吃披萨"后，凯莉知道上下文：
```
[周三 21:00] 披萨好吃不？别忘了给悦悦带一份~
```

---

## 功能清单

### 一、防骚扰机制（6个功能）

| 功能 | 说明 | 配置项 |
|------|------|--------|
| 活跃时间窗口 | 只在指定时段发送消息 | `active_window_start`, `active_window_end` |
| 用户活跃检查 | 用户发送消息后冷却 N 分钟再触发 | `min_user_idle_minutes` |
| 主动消息冷却 | 两次主动消息间隔 N 分钟 | `min_proactive_gap_minutes` |
| 每日限制 | 每天最多发送 N 条主动消息 | `daily_send_limit` |
| 活跃聊天检测 | 用户正在聊天时（间隔<5分钟）不发送 | 硬编码5分钟 |
| 用户未回复追问 | 最多追问 3 次，之后停止 | 硬编码3次 |

#### 1. 活跃时间窗口

只在 `active_window_start` 到 `active_window_end` 之间发送消息。

```yaml
active_window_start: "06:30"  # 最早发送时间
active_window_end: "00:00"    # 最晚发送时间（00:00=午夜）
```

#### 2. 用户活跃检查

用户发送消息后，冷却 N 分钟再触发主动消息。

```yaml
min_user_idle_minutes: 15  # 用户空闲15分钟才触发
```

#### 3. 主动消息冷却

两次主动消息之间至少间隔 N 分钟。

```yaml
min_proactive_gap_minutes: 30  # 两次主动消息间隔至少30分钟
```

#### 4. 每日限制

每天最多发送 N 条主动消息。

```yaml
daily_send_limit: 8  # 每天最多8条
```

#### 5. 活跃聊天检测

当用户正在和凯莉聊天时（最近两条消息间隔 < 5分钟），不发送主动消息。

**实现：** `active_message_lib.py` → `in_active_conversation()`

```python
def in_active_conversation(recent_messages: list, minutes: int = 5) -> bool:
    """检测用户是否正在活跃聊天"""
    # 如果两条消息间隔小于N分钟，说明正在聊天
    gap = (last_time - prev_time).total_seconds() / 60
    return gap < minutes
```

#### 6. 用户未回复追问

当用户没有回复凯莉的主动消息时，凯莉会追问：

```
[凯莉] 到公司了吧？周三上午加油 💪
（5分钟后用户没回复）
[凯莉] 在忙吗？看到回我一声哈
（5分钟后用户没回复）
[凯莉] 好吧不打扰你了，忙完记得吃饭 😊
（之后不再追问，等用户回复）
```

**追问风格：**
- 第1次：关心型 — "在忙吗？看到回我一声哈"
- 第2次：轻松型 — "好吧不打扰你了，忙完记得吃饭 😊"
- 第3次：简短型 — "嗯嗯"

**实现：** `active_message_lib.py` → `user_not_replied()`

---

### 二、智能话题调度（5个功能）

| 功能 | 说明 |
|------|------|
| 话题知识库 | 15个预设话题，7个分类 |
| 时段过滤 | 根据当前时间选择合适的话题 |
| 冷却期 | 避免重复聊同一个话题 |
| 最近话题排除 | 最近2小时内聊过的话题不再选 |
| 加权随机 | 根据权重随机选择，避免单调 |

#### 1. 话题知识库

**文件：** `knowledge-base.json`

包含15个预设话题，分为7个分类：

| 分类 | 数量 | 示例话题 |
|------|------|----------|
| food | 4 | 午饭话题、晚饭话题、早饭话题、喝水提醒 |
| health | 2 | 久坐提醒、眼睛休息 |
| emotion | 2 | 表达喜欢、担心曹凡不开心 |
| life | 4 | 上午工作加油、晚上放松话题、下班路上、周末安排 |
| tech | 1 | 程序员段子 |
| hobby | 1 | 推荐歌曲 |
| greeting | 1 | 时段问候 |

**话题结构：**

```json
{
  "id": "food_001",
  "category": "food",
  "topic": "午饭话题",
  "prompt": "现在是中午，问曹凡今天中午吃什么...",
  "time_relevance": ["noon"],
  "weight": 1.2,
  "cooldown_hours": 4,
  "require_reply": false,
  "last_used": null,
  "reply_count": 0,
  "success_count": 0
}
```

**字段说明：**

| 字段 | 说明 |
|------|------|
| `id` | 唯一标识 |
| `category` | 分类（food、health、emotion、life、tech、hobby、greeting） |
| `topic` | 主题简述 |
| `prompt` | 发给 LLM 的内容 |
| `time_relevance` | 适用时段（morning/noon/afternoon/evening/night/any） |
| `weight` | 权重（越高越容易被选中） |
| `cooldown_hours` | 冷却时间（小时） |
| `require_reply` | 是否需要用户回复才继续 |
| `last_used` | 上次使用时间 |
| `reply_count` | 用户回复次数 |
| `success_count` | 成功发送次数 |

#### 2. 时段过滤

根据当前时间自动选择合适的话题：

| 时段 | 时间范围 | 适用话题 |
|------|----------|----------|
| morning | 6-11点 | 早饭、工作加油、天气 |
| noon | 12-13点 | 午饭 |
| afternoon | 14-17点 | 喝水、久坐、眼睛休息 |
| evening | 18-19点 | 晚饭、下班、放松 |
| night | 20-23点 | 晚上放松、推荐歌曲 |
| late_night | 0-5点 | 不发送 |

#### 3. 冷却期

每个话题有独立的冷却时间（`cooldown_hours`），避免短时间内重复聊同一个话题。

```python
def in_cooldown(entry: dict, now: datetime) -> bool:
    """检查条目是否在冷却期"""
    last_used = entry.get("last_used")
    if not last_used:
        return False
    cooldown_hours = entry.get("cooldown_hours", 4)
    return now < last_used_dt + timedelta(hours=cooldown_hours)
```

#### 4. 最近话题排除

最近2小时内聊过的话题不会再被选中。

```python
def get_recent_topic_ids(hours: int = 2) -> list[str]:
    """获取最近N小时内使用过的话题ID"""
```

#### 5. 加权随机

根据话题权重进行加权随机选择，避免单调：

```python
def calc_weight(entry: dict) -> float:
    w = entry.get("weight", 1.0)
    # 周末调整
    if weekday >= 5:
        if entry.get("category") in ("hobby", "life", "emotion"):
            w *= 1.3  # 周末多聊生活和情感
        if entry.get("category") == "tech":
            w *= 0.8  # 周末少聊工作
    return w
```

---

### 三、上下文注入机制

| 功能 | 说明 |
|------|------|
| pre_llm_call hook | 用户回复时注入最近主动消息 |
| 静默消息过滤 | [SILENT] 消息不注入 |
| 状态文件 | 记录最后注入的输出，避免重复 |

#### 1. pre_llm_call hook

**官方文档：** [Hermes Agent Event Hooks](https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks)

当用户回复凯莉的主动消息时，`pre_llm_call` hook 自动注入最近的主动消息到上下文中：

```
⚠️ 重要上下文：你（凯莉）最近主动发给曹凡的消息，这些消息不在当前对话历史中：
[凯莉主动发送] 2026-06-10 06:40:25 CST: 中午了，今天吃啥呀？

👆 用户的回复是在延续上面的话题，请根据这些主动消息的内容来理解和回应用户。
```

**实现：** `plugin/__init__.py` → `restore_recent_proactive_messages()`

```python
def restore_recent_proactive_messages(session_id: str, platform: str, **kwargs):
    config = load_feature_config()
    if platform != str(config.get("target_platform")):
        return None  # 只对目标平台生效
    
    state = ensure_runtime_state(config)
    pending = pending_restore_outputs(config, state)
    if not pending:
        return None
    
    # 注入到 user message
    context = _format_restore_context(selected)
    return {"context": context}
```

#### 2. 静默消息过滤

只注入非静默消息（发送成功的），`[SILENT]` 消息不注入。

```python
def _normalize_output_text(text: str) -> str:
    value = text.strip()
    if value.startswith("[SILENT]"):
        return "[SILENT]"
    # ... 提取实际内容
```

#### 3. 状态文件

**文件：** `state.json`

```json
{
  "last_restored_output": "2026-06-10_17-00-52.md",
  "last_seen_output": "2026-06-10_17-00-52.md",
  "last_restored_at": "2026-06-10T17:03:31+08:00",
  "unanswered_count": 0
}
```

| 字段 | 说明 |
|------|------|
| `last_restored_output` | 最后注入的输出文件名 |
| `last_seen_output` | 最后看到的输出文件名 |
| `last_restored_at` | 最后注入时间 |
| `unanswered_count` | 连续未回复次数（追问用） |

---

### 四、历史记录

| 功能 | 说明 |
|------|------|
| history.jsonl | 每次触发的详细记录 |
| topic_history.json | 话题使用历史 |

#### 1. history.jsonl

每次触发都会记录：

```json
{
  "timestamp": "2026-06-10T07:20:16+08:00",
  "decision": "YES",
  "reason": "eligible",
  "topic_id": "food_001",
  "topic_category": "food",
  "delivered": true,
  "user_replied": false
}
```

#### 2. topic_history.json

话题使用历史：

```json
{
  "food_001": {
    "last_used": "2026-06-10T12:00:00+08:00",
    "use_count": 5,
    "reply_count": 3
  }
}
```

**作用：**
- 避免重复：最近聊过的话题不会再次选中
- 效果分析：统计用户回复率
- 权重调整：根据回复率调整话题权重

---

### 五、早退逻辑

当 `SEND_DECISION=NO` 时，脚本直接输出 `[SILENT]`，不触发 Agent，节省 token。

```python
# build_context.py
if payload["decision"] == "NO":
    print("[SILENT]")
    return
```

**效果：** 不调用 LLM，零 token 消耗。

---

### 六、Prompt 优化

**文件：** `cron_prompt.txt`

```
1. 检查脚本输出是否为 [SILENT]
2. 如果脚本输出 [SILENT] → 立即输出 [SILENT]，不要思考
3. 如果脚本输出包含 SEND_DECISION 字段：
   - SEND_DECISION=NO → 立即输出 [SILENT]
   - SEND_DECISION=YES → 必须发送一条消息
```

**效果：** Agent 看到脚本输出 `[SILENT]` 时，直接输出 `[SILENT]`，消耗很少 token。

---

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
│  ✓ 用户正在聊天？                                         │
│  ✓ 用户未回复追问次数？                                     │
│  → 输出 SEND_DECISION: YES / NO / FOLLOWUP               │
│  → 附带最近聊天摘要 + 最近主动消息记录 + 话题信息            │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│  LLM 决策                                                │
│                                                          │
│  输入: SEND_DECISION + 聊天上下文 + 话题提示                │
│  输出: [SILENT] 或一条 1-2 句的自然消息                     │
│                                                          │
│  模型可以基于上下文自由判断：                                │
│  - 延续昨天的话题                                          │
│  - 关心用户近况                                            │
│  - 参考话题提示生成消息                                     │
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

---

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
cp lib/history.py ~/.hermes/active-message/
cp lib/knowledge-base.json ~/.hermes/active-message/
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

---

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

# 上下文注入
recent_message_limit: 8          # 注入最近几条聊天记录
restore_message_limit: 3         # 注入最近几条主动消息
```

### 参数调优

| 场景 | idle_min | gap_min | daily | cron频率 |
|------|----------|---------|-------|----------|
| 保守模式 | 60 | 120 | 4 | every 30m |
| 正常使用 | 15 | 30 | 8 | 每20分钟 |
| 激进测试 | 5 | 15 | 12 | every 10m |
| 开发测试 | 0 | 0 | 20 | 每10分钟 |

### 获取 chat_id

**微信**: 通过 Hermes 查看 gateway 日志，找到 `chat_id` 格式类似 `xxx@im.wechat`

**Telegram**: 发送 `/start` 给 [@userinfobot](https://t.me/userinfobot) 获取你的数字 ID

---

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

---

## 使用

### 常用命令

```bash
# 1. 手动触发主动消息
hermes cron run 1798926f7133

# 2. 查看最近的输出
cat ~/.hermes/cron/output/1798926f7133/$(ls -t ~/.hermes/cron/output/1798926f7133/ | head -1)

# 3. 检查hook日志（上下文注入）
grep "active-message hook" ~/.hermes/logs/gateway.log | tail -5

# 4. 检查运行时状态
cat ~/.hermes/active-message/state.json

# 5. 检查历史记录
cat ~/.hermes/active-message/history.jsonl

# 6. 检查话题历史
cat ~/.hermes/active-message/topic_history.json

# 7. 查看知识库
cat ~/.hermes/active-message/knowledge-base.json

# 8. 测试脚本是否正常
python3 ~/.hermes/active-message/build_context.py
```

### 验证

```bash
# 测试脚本是否正常
python3 ~/.hermes/active-message/build_context.py

# 检查输出:
# SEND_DECISION=YES → 允许发送
# SEND_DECISION=NO  → 不满足条件 (看 REASON)
# [SILENT]          → 不需要发送（节省token）
```

---

## 高级功能

### 自定义 AI 助手和用户名称

如果你想让主动消息显示特定的 AI 助手名称（如"凯莉"）和用户名称（如"曹凡"），可以修改 `plugin/__init__.py` 文件：

```python
# 找到 _format_restore_context 函数，修改以下两行：
lines = [
    "以下是你（凯莉）最近主动发给曹凡的消息，这些消息不在当前对话历史中：",
]
for record in records:
    lines.append(f"[凯莉主动发送] {format_dt(record.created_at)} {truncate_text(record.text, max_chars=220)}")
```

### 添加新话题

编辑 `~/.hermes/active-message/knowledge-base.json`，添加新条目：

```json
{
  "id": "new_001",
  "category": "new_category",
  "topic": "话题简述",
  "prompt": "发给 LLM 的内容",
  "time_relevance": ["morning", "afternoon"],
  "weight": 1.0,
  "cooldown_hours": 4,
  "require_reply": false,
  "last_used": null,
  "reply_count": 0,
  "success_count": 0
}
```

**时段标签：**
- `morning` — 早上 6-11
- `noon` — 中午 12-13
- `afternoon` — 下午 14-17
- `evening` — 傍晚 18-19
- `night` — 晚上 20-23
- `late_night` — 凌晨 0-5
- `any` — 任何时段

### 切换到正式使用

当测试完成，准备正式使用时：

1. 修改 `config.yaml`：
```yaml
min_user_idle_minutes: 15    # 从 0 改为 15
min_proactive_gap_minutes: 30 # 从 0 改为 30
```

2. 重启 gateway：
```bash
hermes gateway restart
```

---

## 文件结构

### 仓库文件

```
hermes-active-message/
├── README.md                   # 本文档
├── DESIGN.md                   # 设计文档（详细功能说明）
├── LICENSE                     # MIT 许可
├── install.sh                  # 自动安装脚本
├── config.example.yaml         # 配置示例
├── lib/
│   ├── active_message_lib.py   # 核心逻辑库
│   ├── history.py              # 历史记录模块
│   └── knowledge-base.json     # 话题知识库
├── plugin/
│   ├── __init__.py             # pre_llm_call hook
│   └── plugin.yaml             # 插件声明
├── prompts/
│   └── cron_prompt.txt         # LLM prompt
├── scripts/
│   ├── build_context.py        # 脚本入口
│   └── cron_entry.py           # cron 入口脚本
└── references/
    └── weixin-adaptation.md    # 微信适配说明
```

### 安装后的文件分布

```
~/.hermes/
├── active-message/
│   ├── DESIGN.md              # 设计文档
│   ├── build_context.py       # 脚本入口
│   ├── active_message_lib.py  # 核心逻辑库
│   ├── history.py             # 历史记录模块
│   ├── knowledge-base.json    # 话题知识库
│   ├── config.yaml            # 功能配置
│   ├── cron_prompt.txt        # cron job 的 prompt 规则
│   ├── history.jsonl          # 每次触发的详细记录
│   ├── topic_history.json     # 话题使用历史
│   └── state.json             # 运行时状态
├── plugins/
│   └── active-message/
│       ├── __init__.py        # hook 注册 + context 注入逻辑
│       └── plugin.yaml        # 插件声明
├── scripts/
│   └── active-message-build-context.py  # 薄包装
└── cron/
    └── output/
        └── <job_id>/
            └── *.md           # 每次 cron job 运行的完整记录
```

---

## 工作原理详解

### 硬规则判定 (build_context.py)

脚本从 Hermes 的 state.db 中查询:
- 最近的用户消息时间 → 判断空闲
- 最近的主动消息 → 判断冷却
- 当天发送计数 → 判断上限
- 最近两条消息间隔 → 判断是否正在聊天
- 用户最后消息时间 vs 凯莉最后主动消息时间 → 判断是否未回复

所有条件满足 → `SEND_DECISION=YES`

### 话题选择 (active_message_lib.py)

1. 按当前时段过滤话题
2. 排除冷却中的
3. 排除最近2小时内聊过的
4. 加权随机选择

### LLM 决策

prompt 告诉模型:
- 如果 `SEND_DECISION=NO`，必须输出 `[SILENT]`
- 如果 `SEND_DECISION=YES`，可以基于聊天上下文发送 1-2 句自然消息
- 如果有 `TOPIC_PROMPT`，参考话题提示生成消息
- 如果有 `FOLLOWUP_CONTEXT`，追问用户
- 不能暴露 cron/脚本等机制
- 不能重复最近发过的内容

### 上下文恢复 (plugin hook)

cron job 的输出不在用户对话的 session 中，所以用户回复时模型不知道之前发了什么。`pre_llm_call` hook 会:
1. 找到游标之后的新主动消息
2. 注入为上下文: "你之前发了这些消息，不要重复"
3. 更新游标避免重复注入

---

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

### 早退逻辑节省 token

当 `SEND_DECISION=NO` 时，脚本直接输出 `[SILENT]`，不触发 Agent，零 token 消耗。

---

## 微信平台适配

原项目默认为 Telegram 设计，微信需要修改:

1. **plugin/__init__.py** — "Telegram user" → "the user"
2. **prompts/cron_prompt.txt** — 所有 "Telegram" → "微信"
3. **config.yaml** — `target_platform: weixin`

详见 [references/weixin-adaptation.md](references/weixin-adaptation.md)

---

## 开发阶段回顾

| 阶段 | 状态 | 功能 |
|------|------|------|
| 第一阶段：验证上下文注入 | ✅ 完成 | 验证 hook 机制正常工作 |
| 第二阶段：防骚扰 | ✅ 完成 | 活跃聊天检测、早退逻辑 |
| 第三阶段：用户未回复追问 | ✅ 完成 | 追问逻辑、最多3次 |
| 第四阶段：话题知识库 | ✅ 完成 | 15个话题、7个分类 |
| 第五阶段：历史记录 | ✅ 完成 | history.jsonl、topic_history.json |

---

## 许可

MIT
