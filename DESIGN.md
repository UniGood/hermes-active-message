# 主动消息 v2 — 设计方案（更新版）

## 一、核心目标

1. **保证上下文注入功能正常** — 这是基础，不能破坏
2. **合理稳定** — 渐进式改进，不要大改架构
3. **智能调度** — 话题多样化，避免骚扰

---

## 二、整体功能清单

### 已实现功能一览

| 功能 | 文件 | 说明 |
|------|------|------|
| 活跃时间窗口 | `active_message_lib.py:136` | `in_active_window()` |
| 用户活跃检查 | `active_message_lib.py:353-357` | 基于 `min_user_idle_minutes` |
| 主动消息冷却 | `active_message_lib.py:358-362` | 基于 `min_proactive_gap_minutes` |
| 每日限制 | `active_message_lib.py:363-365` | 基于 `daily_send_limit` |
| **活跃聊天检测** | `active_message_lib.py:161-182` | `in_active_conversation()` |
| **用户未回复追问** | `active_message_lib.py:185-195` | `user_not_replied()` |
| **话题知识库** | `knowledge-base.json` | 15个话题条目，7个分类 |
| **话题选择逻辑** | `active_message_lib.py:460-530` | `select_topic_entry()` |
| **历史记录** | `history.py` | `append_history()`, `update_topic_history()` |
| 上下文注入hook | `plugins/active-message/__init__.py` | `pre_llm_call` hook |
| 静默消息过滤 | `active_message_lib.py:220-239` | `_normalize_output_text()` |
| **早退逻辑** | `build_context.py:19-21` | SEND_DECISION=NO 时直接输出 `[SILENT]` |

### 功能分类说明

#### 1. 防骚扰机制

| 功能 | 效果 |
|------|------|
| 活跃时间窗口 | 只在 06:30-00:00 发送消息 |
| 用户活跃检查 | 用户发送消息后冷却 N 分钟 |
| 主动消息冷却 | 两次主动消息间隔 N 分钟 |
| 每日限制 | 每天最多发送 8 条主动消息 |
| 活跃聊天检测 | 用户正在聊天时（间隔<5分钟）不发送 |
| 用户未回复追问 | 最多追问 3 次，之后停止 |

#### 2. 智能调度

| 功能 | 效果 |
|------|------|
| 话题知识库 | 15个预设话题，7个分类 |
| 时段过滤 | 根据当前时间选择合适的话题 |
| 冷却期 | 避免重复聊同一个话题 |
| 最近话题排除 | 最近2小时内聊过的话题不再选 |
| 加权随机 | 根据权重随机选择，避免单调 |

#### 3. 上下文注入

| 功能 | 效果 |
|------|------|
| pre_llm_call hook | 用户回复时注入最近主动消息 |
| 静默消息过滤 | [SILENT] 消息不注入 |
| 状态文件 | 记录最后注入的输出，避免重复 |

#### 4. 历史记录

| 功能 | 效果 |
|------|------|
| history.jsonl | 记录每次触发的详细信息 |
| topic_history.json | 记录话题使用历史 |
| 避免重复 | 最近聊过的话题不再选 |

---

## 三、使用说明

### 3.1 配置文件

**文件位置：** `~/.hermes/active-message/config.yaml`

```yaml
enabled: true
target_platform: weixin
target_chat_id: "o9cq800B700qFq20-npef3QLNKSQ@im.wechat"
target_user_id: "o9cq800B700qFq20-npef3QLNKSQ@im.wechat"
timezone: Asia/Shanghai
heartbeat_schedule: 0,20,40 6-23 * * *
active_window_start: "06:30"
active_window_end: "00:00"

# 时间控制
min_user_idle_minutes: 0     # 测试: 0, 正式: 15
min_proactive_gap_minutes: 0 # 测试: 0, 正式: 30

# 限制
daily_send_limit: 8
recent_message_limit: 8
restore_message_limit: 3
```

**配置说明：**

| 配置项 | 测试阶段 | 正式使用 | 说明 |
|--------|----------|----------|------|
| `min_user_idle_minutes` | `0` | `15` | 用户发送消息后冷却时间 |
| `min_proactive_gap_minutes` | `0` | `30` | 两次主动消息间隔 |
| `daily_send_limit` | `8` | `8` | 每天最多发送条数 |
| `active_window_start` | `06:30` | `06:30` | 开始发送时间 |
| `active_window_end` | `00:00` | `00:00` | 结束发送时间 |

### 3.2 文件结构

```
~/.hermes/
├── active-message/
│   ├── DESIGN.md              # 本文档
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

### 3.3 常用命令

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
```

### 3.4 工作流程

```
每20分钟 Cron 触发
    ↓
运行 build_context.py 脚本
    ↓
检查各项条件：
  - 活跃时间窗口？
  - 用户最近活跃？
  - 主动消息冷却？
  - 每日限制？
  - 正在聊天？
  - 用户未回复追问？
    ↓
SEND_DECISION=NO → 输出 [SILENT]，结束
    ↓
SEND_DECISION=YES → 选择话题
    ↓
输出完整上下文 + 话题信息
    ↓
Agent 生成消息，发送给用户
    ↓
用户回复 → pre_llm_call hook 注入上下文
```

### 3.5 话题管理

**查看话题知识库：**
```bash
cat ~/.hermes/active-message/knowledge-base.json
```

**添加新话题：**
编辑 `knowledge-base.json`，添加新条目：

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

### 3.6 切换到正式使用

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

## 四、上下文注入机制（核心，必须保证）

### 官方文档验证 ✅

根据 [Hermes Agent 官方文档](https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks)：

| Hook | 触发时机 | 返回值 |
|------|----------|--------|
| `pre_llm_call` | 每个turn触发一次，tool loop之前 | `{"context": str}` 注入到user message |

**我们的实现完全符合官方设计：**
- ✅ 使用 `pre_llm_call` hook
- ✅ 返回 `{"context": str}` 格式
- ✅ 注入到 user message（不是 system prompt）
- ✅ 非阻塞，错误被捕获

### 注入流程

```
用户回复消息
    ↓
pre_llm_call hook 触发
    ↓
读取 ~/.hermes/cron/output/<job_id>/*.md
    ↓
过滤静默消息（[SILENT]开头）
    ↓
返回比 last_restored_output 更新的非静默输出
    ↓
注入到 user message（不存入 session DB）
    ↓
更新 state.json（last_restored_output, last_seen_output）
```

### 注入格式

```
⚠️ 重要上下文：你（凯莉）最近主动发给曹凡的消息，这些消息不在当前对话历史中，但曹凡的回复很可能是针对这些消息的：
[凯莉主动发送] 2026-06-10 06:40:25 CST: 中午了，今天吃啥呀？

👆 用户的回复是在延续上面的话题，请根据这些主动消息的内容来理解和回应用户，不要答非所问。
```

### 状态文件

```json
// ~/.hermes/active-message/state.json
{
  "last_restored_output": "2026-06-10_17-00-52.md",
  "last_seen_output": "2026-06-10_17-00-52.md",
  "last_restored_at": "2026-06-10T17:03:31+08:00",
  "unanswered_count": 0
}
```

---

## 五、防骚扰机制

### 活跃聊天检测

```python
def in_active_conversation(recent_messages: list, minutes: int = 5) -> bool:
    """检测用户是否正在活跃聊天（最近N分钟内有消息来往）"""
```

**效果：** 用户正在聊天时，不发送主动消息。

### 早退逻辑

```python
if payload["decision"] == "NO":
    print("[SILENT]")
    return
```

**效果：** SEND_DECISION=NO 时，脚本直接输出 `[SILENT]`，不触发 Agent，节省 token。

---

## 六、用户未回复追问

### 追问逻辑

```python
def user_not_replied(last_user_message_at, last_proactive_at) -> bool:
    """检查用户是否未回复凯莉的上一条主动消息"""
```

### 追问次数限制

- 未回复 < 3次 → 追问
- 未回复 >= 3次 → 停止追问

### 追问风格

| 次数 | 风格 | 示例 |
|------|------|------|
| 第1次 | 关心型 | "在忙吗？看到回我一声哈" |
| 第2次 | 轻松型 | "好吧不打扰你了，忙完记得吃饭 😊" |
| 第3次 | 简短型 | "嗯嗯" |

---

## 七、话题知识库

### 知识库结构

```json
{
  "version": "1.0",
  "entries": [
    {
      "id": "food_001",
      "category": "food",
      "topic": "午饭话题",
      "prompt": "现在是中午，问曹凡今天中午吃什么...",
      "time_relevance": ["noon"],
      "weight": 1.2,
      "cooldown_hours": 4
    }
  ]
}
```

### 话题分类

| 分类 | 数量 | 说明 |
|------|------|------|
| food | 4 | 食物相关（午饭、晚饭、早饭、喝水） |
| health | 2 | 健康提醒（久坐、眼睛休息） |
| emotion | 2 | 情感表达（喜欢、担心） |
| life | 4 | 生活话题（工作加油、晚上放松、下班路上、周末安排） |
| tech | 1 | 科技话题（程序员段子） |
| hobby | 1 | 兴趣话题（推荐歌曲） |
| greeting | 1 | 问候话题（时段问候） |

### 选择逻辑

1. 按当前时段过滤
2. 排除冷却中的
3. 排除最近2小时内聊过的
4. 加权随机选择

---

## 八、历史记录

### history.jsonl

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

### topic_history.json

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

### 作用

- **避免重复**：最近聊过的话题不会再次选中
- **效果分析**：统计用户回复率
- **权重调整**：根据回复率调整话题权重

---

## 九、Prompt 规则

```
1. 检查脚本输出是否为 [SILENT]
2. 如果脚本输出 [SILENT] → 立即输出 [SILENT]
3. 如果脚本输出包含 SEND_DECISION 字段：
   - SEND_DECISION=NO → 立即输出 [SILENT]
   - SEND_DECISION=YES → 必须发送一条消息
```

**效果：** Agent 看到脚本输出 `[SILENT]` 时，直接输出 `[SILENT]`，消耗很少 token。

---

## 十、开发阶段回顾

| 阶段 | 状态 | 功能 |
|------|------|------|
| 第一阶段：验证上下文注入 | ✅ 完成 | 验证 hook 机制正常工作 |
| 第二阶段：防骚扰 | ✅ 完成 | 活跃聊天检测、早退逻辑 |
| 第三阶段：用户未回复追问 | ✅ 完成 | 追问逻辑、最多3次 |
| 第四阶段：话题知识库 | ✅ 完成 | 15个话题、7个分类 |
| 第五阶段：历史记录 | ✅ 完成 | history.jsonl、topic_history.json |

---

## 十一、注意事项

### 不能破坏的

1. **上下文注入机制** — `pre_llm_call` hook 必须正常工作
2. **静默消息过滤** — `[SILENT]` 消息不能注入
3. **状态文件** — `last_restored_output` 逻辑不能乱改

### 可以优化的

1. **配置值** — 根据实际使用调整
2. **知识库** — 可以添加更多话题条目
3. **prompt模板** — 可以更智能，但不要破坏基本规则
