---
name: email-himalaya-assistant
description: 通过 Himalaya CLI 同步邮箱、做优先级分拣、生成本地草稿队列，并在人工确认后发送。适用于“同步收件箱”“整理未读邮件”“生成回复草稿”“输出日报/周报”等场景。
metadata:
  openclaw:
    requires:
      bins: ["himalaya"]
      env:
        [
          "IMAP_HOST",
          "IMAP_PORT",
          "IMAP_LOGIN",
          "SMTP_HOST",
          "SMTP_PORT",
          "SMTP_LOGIN",
        ]
    primaryEnv: IMAP_LOGIN
---

本技能用于 OpenClaw + Himalaya 邮件工作流，默认采用“本地草稿 + 人工确认 + 学习闭环”的安全模式。

## 用户价值

- Day-1 就能看到三类可见输出：紧急队列、待确认草稿队列、预估节省时间
- 持续做四件事：收件箱分拣、优先级判断、回复草稿、日报/周报摘要
- 把用户修改过的草稿沉淀为 profile 规则，减少后续重复编辑

## 前置条件

- 已安装 `himalaya`
- 已生成 `runtime/himalaya/config.toml`
- 邮件凭证通过 `.env` 提供；推荐优先使用 `keyring`
- 允许写入 `runtime/drafts/` 与 `runtime/metrics/`

## 动作契约

### `fetch_inbox_envelopes`

用途：抓取收件箱信封列表，供分拣器做第一页 triage。  
命令：

```bash
himalaya --account {{account}} envelope list --folder "{{folder|INBOX}}" --page {{page|1}} --page-size {{page_size|50}} --output json
```

执行要求：

- 优先读取 `INBOX`
- 由上层策略自行过滤“未读、重点发件人、SLA 风险”邮件
- 原始 JSON 仅在本地内存或 `runtime/` 内使用

### `read_message`

用途：读取正文，补充分拣和草稿上下文。  
命令：

```bash
himalaya --account {{account}} message read {{id}}
```

### `export_message_raw`

用途：在需要保留完整 MIME、附件判断或追踪 `Message-ID` 时导出原文。  
命令：

```bash
himalaya --account {{account}} message export {{id}} --full
```

### `create_local_draft`

用途：把 AI 草稿先写到本地模板文件，等待人工复核。  
输出路径：

```text
runtime/drafts/{{thread_id}}.eml
```

模板要求：

- 使用标准邮件模板格式：`Header: value` + 空行 + 正文
- 必须包含 `To`、`Subject`
- 回复场景应补 `In-Reply-To`
- 允许正文使用纯文本；需要附件时再升级为 MML

### `open_local_draft_optional`

用途：在桌面端把本地草稿交给人工继续编辑。  
仅在 macOS 且用户明确需要时执行：

```bash
open -a "Mail" runtime/drafts/{{thread_id}}.eml
```

### `send_confirmed_draft`

用途：仅在人工明确确认后发送本地草稿。  
命令：

```bash
himalaya --account {{account}} template send < runtime/drafts/{{thread_id}}.eml
```

硬性要求：

- 只有当人工明确给出 `CONFIRM_SEND` 时才能执行
- 未确认前只能停留在本地草稿队列

## 分类输出契约

`classify_priority` 必须输出 YAML，字段固定为：

```yaml
intent: human
priority: 2
suggested_folder: Follow-Up
summary_3bullet:
  - 发件人要点
  - 当前风险或机会
  - 建议下一步
reply_recommended: true
review_required: true
```

约束：

- `priority` 使用 1-5，1 最高
- `intent` 必须来自策略定义的标签集
- `summary_3bullet` 必须是用户可直接阅读的中文要点

## 学习闭环

触发词：

- `!learn`
- `!rule`
- `!edit`

执行流程：

1. 对比 `runtime/drafts/{{thread_id}}.eml` 与人工修改后的版本
2. 推断“为什么用户这样改”
3. 一次只提出一条可执行规则
4. 等待人工确认
5. 追加到 `config/profiles/rules/{{profile}}.md`

规则示例：

- “如果用户把措辞改得更正式，则将 tone 向 professional 收紧”
- “如果是高管 profile，结论必须前置”

## 安全规则

- NEVER 在没有 `CONFIRM_SEND` 的情况下调用任何发送动作
- NEVER 自动删除邮件
- NEVER 将原始邮件正文外传到本地运行目录之外
- 所有外部回复、法务/财务主题、带附件邮件默认进入人工复核
- 所有草稿都必须先落到 `runtime/drafts/`

## 可见输出

- `今日紧急清单`：最晚当天必须处理的邮件
- `待确认草稿队列`：可立即复核的本地 `.eml` 草稿
- `日报/周报摘要`：包含 triaged 数量、草稿数量、SLA 风险、预估节省时间

## 触发短语

- “同步我的邮箱”
- “整理今天的未读邮件”
- “给这个发件人起草回复”
- “生成今天的邮件日报”
- “生成本周邮件摘要”
