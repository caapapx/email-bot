# Skill Authoring Playbook

日期：2026-03-26
状态：Active

本文档是 twinbox 接入 OpenClaw Skill 和 Claude Code 命令模板的编写规范。

---

## 1. MVP 已验证命令白名单

以下命令已实现、参数已验证、支持 `--json` 输出，可安全用于 Skill 和模板。

### 读路径（只读，无副作用）

| 命令 | 用途 | JSON 支持 | 示例 |
|------|------|-----------|------|
| `twinbox mailbox preflight --json` | 邮箱登录预检 | ✅ | `twinbox mailbox preflight --json` |
| `twinbox task mailbox-status --json` | OpenClaw 侧邮箱状态 / env 诊断 | ✅ | `twinbox task mailbox-status --json` |
| `twinbox task latest-mail --json` | OpenClaw 常见“最新邮件情况”入口 | ✅ | `twinbox task latest-mail --json` |
| `twinbox task todo --json` | OpenClaw 常见“待办 / 待回复”入口 | ✅ | `twinbox task todo --json` |
| `twinbox task progress QUERY --json` | OpenClaw 常见“某事进展如何”入口 | ✅ | `twinbox task progress 北京云平台部署资源申请 --json` |
| `twinbox task weekly --json` | OpenClaw 常见周报入口 | ✅ | `twinbox task weekly --json` |
| `twinbox queue list --json` | 列出全部队列概览 | ✅ | `twinbox queue list --json` |
| `twinbox queue show TYPE --json` | 队列详情 | ✅ | `twinbox queue show urgent --json` |
| `twinbox queue explain` | 队列投影说明（静态文本） | ❌ | `twinbox queue explain` |
| `twinbox thread inspect ID --json` | 线程状态检视 | ✅ | `twinbox thread inspect thread-abc --json` |
| `twinbox thread explain ID --json` | 线程状态推断 | ✅ | `twinbox thread explain thread-abc --json` |
| `twinbox digest daily --json` | 每日摘要 | ✅ | `twinbox digest daily --json` |
| `twinbox digest pulse --json` | 日内 pulse 投影 | ✅ | `twinbox digest pulse --json` |
| `twinbox digest weekly --json` | 每周简报 | ✅ | `twinbox digest weekly --json` |
| `twinbox action suggest --json` | 行动建议列表 | ✅ | `twinbox action suggest --json` |
| `twinbox action materialize ID --json` | 行动详情 | ✅ | `twinbox action materialize action-urgent-1 --json` |
| `twinbox review list --json` | 待审核项列表 | ✅ | `twinbox review list --json` |
| `twinbox review show ID --json` | 审核项详情 | ✅ | `twinbox review show review-daily_urgent-1 --json` |

补充约定：

- OpenClaw 的自然语言高频请求，默认优先 `twinbox task ... --json`
- `queue` / `thread` / `digest` / `review` 适合在意图已经足够具体时直接调用

### 写路径（有副作用，Skill 应二次确认）

| 命令 | 用途 | JSON 支持 | 注意 |
|------|------|-----------|------|
| `twinbox context import-material SOURCE` | 导入材料文件 | ❌ | 位置参数，非 `--file` |
| `twinbox context upsert-fact --id ID --type TYPE --content TEXT` | 写入事实 | ❌ | 参数与 cli.md 不同 |
| `twinbox context profile-set PROFILE --key K --value V` | 设置画像 | ❌ | 需要位置参数 `profile` |

### 编排路径（独立入口 `twinbox-orchestrate`）

| 命令 | 用途 | 说明 |
|------|------|------|
| `twinbox-orchestrate run --phase 4` | Phase 4 局部刷新 | 快速，~2min |
| `twinbox-orchestrate run` | 全量 Phase 1–4（不传 `--phase`） | 慢，~15min |
| `twinbox-orchestrate roots` | 显示路径根 | 调试用 |
| `twinbox-orchestrate contract` | 显示 phase 契约 | 调试用 |

### 🚧 未实现（勿引用）

- `thread summarize`
- `action apply`
- `review approve`
- `review reject`

---

## 2. OpenClaw Metadata 模板

OpenClaw 解析器要求 **`metadata` 在 `SKILL.md` 里写成单行 JSON**（与多行 YAML 等价信息可读性较差，但可避免 frontmatter 解析失败）。仓库根 [SKILL.md](../../SKILL.md) 为已上线的单行形式；下面 YAML 块仅用于人类编辑与文档说明，落地时请折叠为与根 `SKILL.md` 一致的单行 `metadata: {"openclaw":{...}}`。

```yaml
---
name: <skill-name>
description: <一句话描述>
metadata:
  openclaw:
    requires:
      env: [<必需环境变量列表>]
    primaryEnv: <主账号标识字段>
    login:
      mode: password-env
      runtimeRequiredEnv: [<运行时必需字段>]
      optionalDefaults:
        <KEY>: <默认值>
      stages:
        - unconfigured
        - validated
        - mailbox-connected
      preflightCommand: "twinbox mailbox preflight --json"
    schedules:
      - name: <schedule-id>
        cron: "<5-field cron>"
        command: "twinbox-orchestrate run --phase 4"
        description: "<说明>"
---
```

**关键约束：**
- `schedules[].command` 必须使用 `twinbox-orchestrate`（独立入口），不是 `twinbox orchestrate`；单 phase 用 `run --phase N`，全量用 `run`（无 `--phase`）
- `preflightCommand` 使用 `twinbox mailbox preflight --json`（task CLI 入口）
- `stages` 固定为三阶段：`unconfigured` → `validated` → `mailbox-connected`

---

## 3. Claude Code 命令模板规范

### 模板文件位置

`.claude/commands/twinbox-<场景>.md`

### 模板结构

```markdown
用 twinbox CLI <做什么>，以对话形式呈现。

参数（$ARGUMENTS）：
- 空：<默认行为>
- "<参数值>"：<对应行为>

## 执行步骤

1. 解析 $ARGUMENTS → 确定要执行的 twinbox 命令
2. 执行命令，始终加 `--json`
3. 解析 JSON 输出，格式化为友好文本
4. 末尾提示下一步可用操作（引用其他 /twinbox-* 命令）

## 错误处理

- 命令返回非零退出码 → 显示 stderr 并提示用户检查
- artifact 不存在 → 提示运行 `twinbox-orchestrate run --phase 4`（或全量 `twinbox-orchestrate run`）
- 队列标记 STALE → 提醒用户数据过期
```

### 模板命名约定

| 模板 | 对应命令组 |
|------|-----------|
| `twinbox-queue.md` | `twinbox queue list/show` |
| `twinbox-digest.md` | `twinbox digest daily/weekly` |
| `twinbox-action.md` | `twinbox action suggest/materialize` |
| `twinbox-review.md` | `twinbox review list/show` |

---

## 4. 错误处理规范

### 退出码契约

| 退出码 | 含义 | Skill 处理 |
|--------|------|-----------|
| 0 | 成功（含只读模式的 SMTP warn） | 正常处理 JSON |
| 1 | 业务错误（未找到线程/队列） | 显示 stderr，提示修正输入 |
| 2 | 配置缺失 | 显示 `missing_env`，引导配置 |
| 3 | IMAP 网络失败 | 提示检查网络/防火墙 |
| 4 | IMAP 认证失败 | 提示检查密码 |
| 5 | 内部错误 | 提示联系维护者 |

### JSON 错误响应模式

所有 `--json` 命令在成功时返回数据对象；在失败时 Skill 应捕获 stderr + 退出码。当前实现中失败信息输出到 stderr，不输出 JSON。

---

## 5. JSON 输出契约检查清单

新命令接入 Skill 前，验证：

- [ ] `--json` 参数已注册到 argparse
- [ ] 成功时 stdout 输出合法 JSON
- [ ] JSON 结构与 cli.md 规范一致
- [ ] `generated_at` 字段存在且为 ISO 8601 格式
- [ ] `stale` 字段由 `_is_stale()` 计算，非硬编码
- [ ] 退出码遵循上述契约
- [ ] 错误信息输出到 stderr，不混入 stdout

---

## 6. 统一显示结构

OpenClaw 侧消费 JSON 时期望以下顶层字段（如适用）：

```json
{
  "status": "success | warn | fail",
  "missing_env": [],
  "actionable_hint": "可直接显示给用户的修复提示",
  "next_action": "下一步建议"
}
```

目前只有 `mailbox preflight` 完整实现了此结构。其他命令的 JSON 输出是数据投影（QueueView/DigestView 等），不含 status 包装。扩展时可考虑统一。

---

## 7. 全链路测试集（中文用户提问）

- 清单与场景：`.claude/skills/twinbox/evals/full-chain-2026-03-24.json`（`user_prompt_zh`、`live_steps` 与命令对照；合成夹具在 `evals/fixtures/synthetic/`）
- Live 只读跑法：`evals/run-full-chain-live.sh`（从上述 JSON 读取 `user_prompt_zh` 打印场景，再执行命令；在仓库根运行）
