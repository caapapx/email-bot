# Task-Facing CLI Specification

日期：2026-03-26
状态：Implemented (mailbox, queue, context, thread, digest, action, review 命令已完成)

## 执行摘要

本规范定义 twinbox 的任务导向命令面（task-facing CLI），作为现有编排契约（orchestration contract）之上的稳定交互层。

**核心原则**：

- task-facing 命令是 phase artifacts 的投影视图，不是第二套推理管线
- 命令围绕任务和产品对象，不围绕内部阶段
- 每个命令默认支持 `--json` 结构化输出
- explainability 是默认能力，不是可选附加

**目标用户**：

- skill 和 agent runtime
- listener/action 服务
- 人工交互和调试
- 未来 review surface

## 命令树

> **注意**：`twinbox` 和 `twinbox-orchestrate` 是两个独立入口。
> `twinbox` = task-facing CLI（`twinbox_core.task_cli:main`）
> `twinbox-orchestrate` = 编排 CLI（`twinbox_core.orchestration:main`）

```text
twinbox                      # task-facing CLI 入口
  context                    # 用户上下文管理
    import-material
    material
      list
      set-intent
      remove
      preview
    upsert-fact
    profile-set
    refresh

  mailbox                    # 邮箱登录与只读预检
    preflight
    detect                   # 邮件服务器自动探测

  onboarding                 # 对话式引导配置
    start
    status
    next

  push                       # 推送通知订阅
    subscribe
    unsubscribe
    list
    dispatch

  queue                      # 队列视图
    list
    show
    explain

  thread                     # 线程检视
    inspect
    progress
    summarize                # 🚧 未实现
    explain

  digest                     # 摘要视图
    daily
    pulse
    weekly

  onboard                    # OpenClaw 安装总向导（宿主机；推荐）
    openclaw [--dry-run] [--json] ...

  config                     # Twinbox 单配置文件（state root/twinbox.json）
    show [--json]
    set-llm [--provider ... --model ... --api-url ... --json]
    import-llm-from-openclaw [--openclaw-json PATH] [--dry-run] [--json]
    mailbox-set [--email ... --json]
    set-preferences [--cc-downweight on|off --json]
    integration-set [--use-fragment yes|no --fragment-path PATH --json]
    openclaw-set [--home PATH] [--bin NAME] [...] [--json]

  deploy                     # OpenClaw 宿主接线（仅宿主机；高级入口）
    openclaw [--rollback] [--strict] [--fragment PATH] [--no-fragment] [--remove-config] [--dry-run] [--json] ...

  daemon                     # 后台 JSON-RPC（Unix socket；省 Python 冷启动）
    start | stop | restart | status [--json]

  vendor                     # 将 src/twinbox_core 同步到 $TWINBOX_STATE_ROOT/vendor
    install [--dry-run] [--json]
    status [--json]

  task                       # OpenClaw-facing thin task routes
    latest-mail
    todo
    progress
    weekly
    mailbox-status

  rule                       # 语义分拣规则管理
    list
    add
    remove
    test

  action                     # 动作建议
    suggest
    materialize
    apply                    # 🚧 未实现

  review                     # 审核面
    list
    show
    approve                  # 🚧 未实现
    reject                   # 🚧 未实现

twinbox-orchestrate          # 编排 CLI 入口（独立二进制）
  roots
  contract
  run [--phase N]            # 省略 --phase = 跑满 Phase 1–4
  schedule --job NAME        # 直接执行一个已解析的宿主调度作业
  bridge --event-text TEXT   # 解析 OpenClaw/system-event 文本并转发到 schedule
  bridge-poll                # 轮询 OpenClaw cron runs，并消费新的 Twinbox bridge 事件
```

## 分层语义

### 编排层（twinbox-orchestrate，独立入口）

- 独立二进制入口：`twinbox-orchestrate`（非 `twinbox` 的子命令）
- 面向实现层和 phase 驱动
- 保留给开发、调试、批处理和兼容旧脚本
- 直接操作 phase contract 和 step execution
- **`run` 子命令**：`twinbox-orchestrate run [--phase N]`，`N` 为 `1`–`4`。省略 `--phase` 时按契约顺序执行 Phase 1→4 全部步骤。示例：仅刷新 Phase 4 投影用 `twinbox-orchestrate run --phase 4`。
- **`schedule` 子命令**：执行已经确定好的宿主作业，例如 `twinbox-orchestrate schedule --job daytime-sync --format json`。
- **`bridge` 子命令**：解析 `system-event` 文本协议，再转发到 `schedule`。适合宿主 bridge/service 在拿到事件文本后调用，例如 `twinbox-orchestrate bridge --event-text '{"kind":"twinbox.schedule","job":"daytime-sync"}' --format json`。
- **`bridge-poll` 子命令**：轮询 OpenClaw Gateway 的 `cron.list` / `cron.runs`，识别新产生的 Twinbox `systemEvent` 运行记录，再转发到 `bridge`。适合用户态 systemd/service 定时调用，例如 `twinbox-orchestrate bridge-poll --format json`。

### 任务层（mailbox/context/queue/thread/digest/action/review）

- 面向产品层和任务调用
- skill、listener、review runtime 优先消费这层
- 不暴露 phase 内部细节

## 核心对象模型

### ThreadCard

线程状态的轻量投影。

```yaml
thread_id: string
state: string  # direct | cc_only | group_only | indirect | unknown
waiting_on: string | null
last_activity_at: string  # ISO 8601
confidence: float  # 0.0-1.0
evidence_refs: list[string]
context_refs: list[string]
why: string  # 简短解释，若为非 direct 则包含警告文案
```

说明：
- `thread_id` 在 `task todo --json` 这类薄路由里，可能带有 `[CC]` 或 `[GRP]` 前缀，用来显式暴露 recipient routing 信号
- `[CC]` 表示邮箱 owner 在 `Cc` 列表中（含 `cc_only` 和 `indirect` 角色）
- `[GRP]` 表示邮箱 owner 不在 `To/Cc`，而是通过邮件组或别名收到该线程（`group_only` 角色）
- **recipient_role 降权策略**：
  - `direct`：1.0 (不降权)
  - `cc_only` / `indirect`：0.6 (默认乘数)
  - `group_only`：0.4 (大幅降权)
  - `unknown`：1.0 (样本不足，不降权)
- 所有非 `direct` 线程在 `why` 字段中会自动追加统一警告：`⚠️ 你不是主要收件人，请确认是否真的需要你处理`

### QueueView

队列的稳定视图。

```yaml
queue_type: string  # urgent | pending | sla_risk | stale
items: list[ThreadCard]
rank_reason: dict[thread_id, string]
review_required: bool
generated_at: string  # ISO 8601
stale: bool
```

### DigestView

摘要的结构化视图。

```yaml
digest_type: string  # daily | pulse | weekly
sections: dict[string, object]
generated_at: string  # ISO 8601
stale: bool
```

对于 `weekly` digest，`sections` 应至少包含：

```yaml
action_now: list[ThreadCard]  # 必须今天/下周一前处理
backlog: list[ThreadCard]     # 仍待处理但不紧急
important_changes: string     # 本周重要变化摘要
```

### ActionCard

动作建议（后续实现）。

```yaml
action_id: string
thread_id: string
action_type: string  # reply | forward | archive | flag
why_now: string
risk_level: string  # low | medium | high
required_review_fields: list[string]
suggested_draft_mode: string | null
```

### MailboxPreflightResult

OpenClaw 和 skill runtime 消费的邮箱登录/预检结果。

```yaml
login_mode: string  # password-env
login_stage: string  # unconfigured | validated | mailbox-connected
status: string  # success | warn | fail
error_code: string | null
exit_code: int
code_root: string
state_root: string
env_file: string | null
missing_env: list[string]
defaults_applied: dict[string, string]
effective_account: string
env_sources:
  mode: string
  state_root_env_file: string | null
  state_root_env_present: string
checks:
  env:
    status: string
    missing_env: list[string]
    fix_commands: list[string]
  config_render:
    status: string
    config_file: string | null
  imap:
    status: string
    error_code: string | null
    detail: string | null
  smtp:
    status: string
    error_code: string | null
    detail: string | null
actionable_hint: string
next_action: string
```

## 命令规范

### onboard openclaw

OpenClaw 安装总向导。默认交互式，负责按顺序完成 OpenClaw 风格的显式步骤向导：`Security`、`Quickstart/Manual`、`Mailbox`、`LLM`、`Twinbox tools integration`、`Apply setup`，再把状态交接到现有对话 onboarding。

**用法**：

```bash
twinbox onboard openclaw [--repo-root PATH] [--openclaw-home PATH] [--dry-run]
                         [--openclaw-bin NAME] [--json]
```

**说明**：

- 这是默认推荐入口，面向人工操作员。
- `quickstart`：默认推荐，但仍会逐页展示每个环节，已有值不会静默跳过。
- `manual`：同样逐页展示，并额外补充 repo root / state root / OpenClaw home 等宿主语义。
- `Security` 是第一页：交互默认选中 **No**，直接按 Enter 会退出；必须显式选 **Yes** 才会继续。
- `Mailbox` 不允许跳过；若检测到现有值，会先显示 `Existing config detected` 和 `Config handling`，再显式选择 `Use existing values` / `Update values` / `Reset`。
- `LLM` 只会在 `state root/twinbox.json` 中已经显式存在完整当前值（key + model + api-url/base-url）时显示同样的 `Existing config detected` + `Config handling`；否则直接显示 `Configure OpenAI` / `Configure Anthropic` / `Skip for now`。
- Twinbox 不再内置默认 LLM 模型或默认 API URL；必须显式配置。
- OpenAI 兼容链路：若只填 base（如讯飞星辰 MaaS 文档中的 `https://…/v2`），Twinbox 会在请求时自动补上 `/chat/completions`；鉴权仍为 `Authorization: Bearer <整段 API Key>`（控制台给出的 `appid:secret` 形式需原样粘贴，勿与 model 等字段粘在同一行）。
- 选择 `Configure OpenAI` / `Configure Anthropic` 时，会先按 `API URL -> API key -> Model ID` 的顺序采集覆盖值，再执行显式验证；验证阶段带超时失败出口，不会无限转圈。
- `Twinbox tools integration` 用 OpenClaw 风格的 `Yes (Recommended) / No` 单选确认是否并入 `openclaw.fragment.json`。
- `Apply setup` 会先汇总本轮选择，再显式决定 `Apply now` 或 `Skip for now`。
- 底层仍复用同一组 mailbox / llm / deploy primitive；当前 CLI 只保留这一条公开向导入口，并把配置统一维护在 `state root/twinbox.json`。
- 成功后的人类可读输出会把宿主接线表述为 **Phase 1 of 2**，并明确提示用户继续在 OpenClaw 的 `twinbox` agent 中完成 **Phase 2 of 2**。
- `--json` 仍输出低层 report JSON；非 JSON 路径则使用新的 journey shell。

### config show / set-llm / import-llm-from-openclaw / mailbox-set / set-preferences / integration-set / openclaw-set

Twinbox 单配置文件入口。所有手动配置都收口到 `state root/twinbox.json`；历史 `.env` 仅在迁移期继续被兼容读取。

**常用命令**：

```bash
twinbox config show --json
twinbox config set-llm --provider openai --model MODEL --api-url URL --json
twinbox config import-llm-from-openclaw --json
TWINBOX_SETUP_IMAP_PASS=<app_password> twinbox config mailbox-set --email you@example.com --json
twinbox config set-preferences --cc-downweight off --json
twinbox config integration-set --use-fragment yes --fragment-path /path/to/openclaw.fragment.json --json
twinbox config openclaw-set --home ~/.openclaw --strict --json
```

**说明**：

- `config show` 会输出当前单配置文件，并自动对 secret 做 masked 展示。
- `config set-llm` 与向导中的 LLM 步骤共享同一份配置；写入后会立即做后端校验。
- `config import-llm-from-openclaw`：从宿主 `~/.openclaw/openclaw.json`（或 `--openclaw-json`）读取 `agents.defaults.model` 指向的 `models.providers.*`（需明文 `apiKey` 与 `baseUrl`），写入与 `set-llm` 相同的 `.env` 键并校验。`--dry-run` 只打印将应用的 provider/model/url（不落盘）。OpenClaw 使用 SecretRef 而非内联 key 时本命令会失败，请改用 `set-llm`。
- `config mailbox-set` 与 `mailbox setup` 共享同一份配置；若未显式传 IMAP/SMTP 主机参数，则自动探测。
- `config set-preferences --cc-downweight on|off` 用于控制 CC/group 线程是否做结构性分数衰减；`off` 时仍保留 `recipient_role` 标签，但不再乘 urgency score。
- `config integration-set` 用于设置 `fragment_path` 和 `use_fragment` 默认值；`onboard openclaw` 与 `deploy openclaw` 会读取这些默认值。
- `config openclaw-set` 用于设置 OpenClaw 默认值；`onboard openclaw` 与 `deploy openclaw` 会读取这些默认值。

### deploy openclaw

宿主机上把 Twinbox 接到 OpenClaw的高级/脚本化入口：**roots 初始化**、合并 `~/.openclaw/openclaw.json` 的 `skills.entries.twinbox`、按 **`deploy_host_system` / `deploy_host_machine`** 做 **`ensure_himalaya`**（`PATH` → `state_root/runtime/bin/himalaya` → 内置 **Linux x86_64 / aarch64** 解压；其它平台为 `skipped` 并提示自行安装）、将仓库根 `SKILL.md` 写入 **state root** 根下的 `SKILL.md` 并对 `~/.openclaw/skills/twinbox/SKILL.md` **创建符号链接**（不支持时回退复制）、`openclaw gateway restart`。JSON 报告含 `skill_canonical_dest` / `skill_dest` 及宿主字段。实现：`src/twinbox_core/openclaw_deploy.py`。

**用法**：

```bash
twinbox deploy openclaw [--repo-root PATH] [--openclaw-home PATH] [--dry-run] [--no-restart]
                        [--no-env-sync] [--strict] [--fragment PATH] [--no-fragment]
                        [--openclaw-bin NAME] [--json]
twinbox deploy openclaw --rollback [--remove-config] [--dry-run] [--no-restart] [--json]
```

**说明**：

- `--rollback`：撤销上述接线（删除 `skills.entries.twinbox`、`~/.openclaw/skills/twinbox/`），**不删除** `~/.twinbox`；全量卸载见 `openclaw-skill/DEPLOY.md` §5 `uninstall_openclaw_twinbox.sh`。
- `--remove-config`：仅在与 `--rollback` 联用时删除 `~/.config/twinbox/`（code-root / state-root 指针）。
- `--strict`：默认从 `state root/twinbox.json` 同步邮箱键时，若缺少 `SKILL.md` 声明的 `requires.env` 任一必填项，则失败并跳过后续写盘（与未加 `--strict` 时仅 warning 不同）。
- `--fragment` / `--no-fragment`：可选将 JSON 片段深度合并进 `openclaw.json`（在写入 `skills.entries.twinbox` 之前）；默认若存在 `openclaw-skill/openclaw.fragment.json` 则读取。示例见 `openclaw-skill/openclaw.fragment.example.json`。
- `scripts/reset_twinbox_state.sh` 只清 `runtime/` 与 twinbox 会话，不动 `openclaw.json` / skill 文件。

操作主路径见 [openclaw-skill/DEPLOY.md](../../openclaw-skill/DEPLOY.md)。

### mailbox preflight

执行 password-env 模式下的邮箱登录预检。该命令优先服务 OpenClaw 和 skill adapter，也可用于本地只读诊断。

**用法**：

```bash
twinbox mailbox preflight [--json] [--account NAME] [--folder INBOX] [--page-size 5] [--state-root PATH]
```

**参数**：

- `--json`：输出稳定 JSON 契约，供 OpenClaw 消费
- `--account NAME`：覆盖 `MAIL_ACCOUNT_NAME`
- `--folder INBOX`：用于只读 envelope list 的文件夹（默认 `INBOX`）
- `--page-size 5`：只读拉取条数（默认 `5`）
- `--state-root PATH`：覆盖 twinbox state root
- 默认 state root 解析顺序：`TWINBOX_STATE_ROOT` / `~/.config/twinbox/state-root` / legacy `TWINBOX_CANONICAL_ROOT` / `~/.config/twinbox/canonical-root` / 当前 code root

**状态语义**：

- `unconfigured`：缺少运行所需邮箱配置；不会尝试渲染 config 或连接 IMAP
- `validated`：env 已齐全且 himalaya config 已生成，但 IMAP 仍未通过
- `mailbox-connected`：IMAP 只读验证成功

**配置来源语义**：

- process env 优先，其次才是 `state root/twinbox.json`
- OpenClaw-native 部署推荐把邮箱配置注入 skill process env
- 历史 `.env` 仅作为迁移期 fallback；当前推荐单真源为 `state root/twinbox.json`

**只读边界**：

- 只读预检只用 IMAP envelope list 作为连接证据
- SMTP 在只读模式下不阻塞 Phase 1-4，统一返回 `warn` + `smtp_skipped_read_only`

**退出码**：

- `0`：成功，或只存在只读模式下的 SMTP warn
- `2`：配置缺失或 config render 失败
- `3`：IMAP 网络/TLS/命令级失败
- `4`：IMAP 认证失败
- `5`：内部错误（例如 `himalaya` 缺失）

**输出字段**：

- `status`：`success | warn | fail`
- `missing_env`：缺失 env 列表
- `actionable_hint`：可直接显示给用户的修复提示
- `next_action`：下一步建议，例如重新预检或运行 Phase 1

**实现映射**：

- 解析 `state root/twinbox.json` 与进程环境变量
- 应用默认值：`MAIL_ACCOUNT_NAME=myTwinbox`、`MAIL_DISPLAY_NAME={MAIL_ACCOUNT_NAME}`、`IMAP_ENCRYPTION=tls`、`SMTP_ENCRYPTION=tls`
- 解析 `himalaya` 可执行文件：先 `PATH`，再 `$TWINBOX_STATE_ROOT/runtime/bin/himalaya`；若仍没有且在 **Linux x86_64 / aarch64** 上，则从随 `twinbox_core` 分发的官方 `himalaya.*-linux.tgz` 解压到 `runtime/bin/himalaya`（便于离线宿主）
- 渲染 `runtime/himalaya/config.toml`
- 执行 `himalaya envelope list --output json`
- 写入 `runtime/validation/preflight/mailbox-smoke.json`

### mailbox detect

自动探测邮件服务器配置（IMAP/SMTP 主机和端口）。

**用法**：

```bash
twinbox mailbox detect EMAIL [--json]
```

**参数**：

- `EMAIL`：邮箱地址（必需）
- `--json`：输出 JSON 格式

**探测逻辑**：

1. TCP 连接测试
2. TLS 握手验证
3. 协议 banner 验证（IMAP/SMTP）
4. 智能选择：优先 mail.* 统一主机，其次 imap.*/smtp.* 分离主机

**输出字段**（JSON）：

- `IMAP_HOST`、`IMAP_PORT`、`IMAP_ENCRYPTION`
- `SMTP_HOST`、`SMTP_PORT`、`SMTP_ENCRYPTION`
- `_confidence`：high | medium | low
- `_note`：探测说明

### onboarding start

启动对话式引导配置流程。

**用法**：

```bash
twinbox onboarding start [--json]
```

**阶段**：mailbox_login → llm_setup → profile_setup → material_import → routing_rules → push_subscription

**人类可读输出**：

- 以 “Twinbox Onboarding Journey / Phase 2 of 2” 开头，作为宿主态接线完成后的连续旅程文案。

### onboarding status

查看当前引导进度。

**用法**：

```bash
twinbox onboarding status [--json]
```

**人类可读输出**：

- 以 “Twinbox Onboarding Journey / Phase 2 of 2” 开头，强调这是 OpenClaw handoff 后的继续阶段。

### onboarding next

完成当前阶段并推进到下一阶段，用于对话式渐进配置流程。

**用法**：

```bash
twinbox onboarding next [--json] [--profile-notes TEXT] [--calibration-notes TEXT] [--cc-downweight on|off]
```

**输出字段**（JSON）：

- `completed_stage`：本次刚完成的阶段（首次从未开始推进时为 `mailbox_login`）
- `current_stage`：推进后的当前阶段（可能为 `completed`）
- `completed_stages`：已完成阶段列表
- `prompt`：下一阶段提示文案

**阶段特定写入**：

- 当当前阶段为 `profile_setup` 时，可用 `--profile-notes` 保存职位/习惯/偏好摘要到 `runtime/context/human-context.yaml` 的 `profile_notes`
- 同阶段可用 `--calibration-notes` 保存“关注谁/忽略什么/本周重点”摘要到同文件的 `calibration`
- 同阶段可用 `--cc-downweight on|off` 写入 `twinbox.json.preferences.cc_downweight.enabled`；`off` 适合大量通过 CC 跟进工作的角色
- Phase 2/3/4 loading 统一从 `runtime/context/human-context.yaml` 读取；旧的 `manual-facts.yaml` / `manual-habits.yaml` / `instance-calibration-notes.md` / onboarding `profile_data.*` 会在首次读取时自动迁移

**人类可读输出**：

- 以 “Twinbox Onboarding Journey / Phase 2 of 2” 开头，并展示刚完成阶段和当前阶段，保持与 `onboard openclaw` 的 handoff 语言一致。

### push subscribe

订阅推送通知。

**用法**：

```bash
twinbox push subscribe SESSION_ID [--min-urgency high|medium|low] [--json]
```

### push unsubscribe

取消订阅。

**用法**：

```bash
twinbox push unsubscribe SESSION_ID [--json]
```

### push list

列出所有订阅。

**用法**：

```bash
twinbox push list [--json]
```

### push dispatch

手动触发推送分发（测试用）。

**用法**：

```bash
twinbox push dispatch [--openclaw-bin PATH] [--json]
```

### queue list

列出所有队列概览。

**用法**：

```bash
twinbox queue list [--json]
```

**参数**：

- `--json`：输出 JSON 格式

> 注：当前实现固定返回 urgent、pending、sla_risk 三个队列，无 `--type` 过滤。

**输出**（文本模式）：

```text
Queue: urgent (3 items, generated 2026-03-23T09:00:00Z)
  - thread-abc123: Waiting on me, last activity 2 days ago
  - thread-def456: Waiting on me, last activity 1 day ago
  - thread-ghi789: Monitor only, high risk

Queue: pending (5 items, generated 2026-03-23T09:00:00Z)
  ...
```

**输出**（JSON 模式）：

```json
{
  "queues": [
    {
      "queue_type": "urgent",
      "items": [...],
      "rank_reason": {...},
      "review_required": false,
      "generated_at": "2026-03-23T09:00:00Z",
      "stale": false
    },
    ...
  ]
}
```

**实现映射**：

- 读取 `runtime/validation/phase-4/daily-urgent.yaml`
- 读取 `runtime/validation/phase-4/pending-replies.yaml`
- 读取 `runtime/validation/phase-4/sla-risks.yaml`
- 投影为 `QueueView` 对象

### queue show

显示指定队列的详细信息。

**用法**：

```bash
twinbox queue show TYPE [--json]
```

**参数**：

- `TYPE`：队列类型，必选，可选值：`urgent`、`pending`、`sla_risk`
- `--json`：输出 JSON 格式

**输出**（文本模式）：

```text
Queue: urgent
Generated: 2026-03-23T09:00:00Z
Status: fresh
Items: 3

1. thread-abc123
   State: waiting_on_me
   Last activity: 2 days ago
   Confidence: 0.85
   Why: Customer escalation, no response in 48h

2. thread-def456
   ...
```

**输出**（JSON 模式）：

```json
{
  "queue_type": "urgent",
  "items": [
    {
      "thread_id": "thread-abc123",
      "state": "waiting_on_me",
      "waiting_on": "me",
      "last_activity_at": "2026-03-21T10:30:00Z",
      "confidence": 0.85,
      "evidence_refs": ["envelope-5", "envelope-8"],
      "context_refs": ["escalation-policy"],
      "why": "Customer escalation, no response in 48h"
    },
    ...
  ],
  "rank_reason": {
    "thread-abc123": "High priority: customer escalation + SLA risk"
  },
  "review_required": false,
  "generated_at": "2026-03-23T09:00:00Z",
  "stale": false
}
```

### queue explain

输出队列投影机制的静态说明。

**用法**：

```bash
twinbox queue explain
```

> 注：当前实现为静态文本输出，不接受参数，不支持 `--json`。
> 未来可扩展为按 `TYPE THREAD_ID` 解释具体排名。

**输出**（文本模式）：

```text
队列投影说明
============

twinbox 的队列视图从 Phase 4 artifacts 投影而来，不是独立的数据管道。

数据源映射：
- urgent 队列 <- runtime/validation/phase-4/daily-urgent.yaml
- pending 队列 <- runtime/validation/phase-4/pending-replies.yaml
- sla_risk 队列 <- runtime/validation/phase-4/sla-risks.yaml
...
```

### thread inspect

检视线程的当前状态。

**用法**：

```bash
twinbox thread inspect THREAD_ID [--json]
```

**参数**：

- `THREAD_ID`：线程 ID
- `--json`：输出 JSON 格式

**输出**（文本模式）：

```text
Thread: thread-abc123
State: waiting_on_me
Waiting on: me
Last activity: 2 days ago (2026-03-21T10:30:00Z)
Confidence: 0.85

Evidence:
- envelope-5: customer escalation
- envelope-8: follow-up reminder

Context:
- escalation-policy: response within 24h
- customer-tier: premium

Why: Customer escalation, no response in 48h
```

**输出**（JSON 模式）：

```json
{
  "thread_id": "thread-abc123",
  "state": "waiting_on_me",
  "waiting_on": "me",
  "last_activity_at": "2026-03-21T10:30:00Z",
  "confidence": 0.85,
  "evidence_refs": ["envelope-5", "envelope-8"],
  "context_refs": ["escalation-policy", "customer-tier"],
  "why": "Customer escalation, no response in 48h",
  "explainability": {
    "state_reasoning": "Last message from customer with escalation keywords",
    "confidence_factors": [
      "Clear action request in last message",
      "No response from me in 48h",
      "Escalation policy triggered"
    ]
  }
}
```

### thread explain

解释线程状态的推断依据。

**用法**：

```bash
twinbox thread explain THREAD_ID [--json]
```

**参数**：

- `THREAD_ID`：线程 ID
- `--json`：输出 JSON 格式

**输出**（文本模式）：

```text
Thread: thread-abc123
Current state: waiting_on_me

Why this state:
1. Last message from customer (envelope-8, 2026-03-21T10:30:00Z)
2. Message contains action request: "Please confirm by EOD"
3. No response from me in 48h
4. Escalation policy triggered (customer-tier: premium)

Confidence: 0.85
- Clear action request: +0.3
- Recent activity: +0.2
- Context match: +0.35

Alternative interpretations:
- Could be "monitor_only" if customer is just FYI (confidence: 0.15)
```

**输出**（JSON 模式）：

```json
{
  "thread_id": "thread-abc123",
  "state": "waiting_on_me",
  "explainability": {
    "reasoning_steps": [
      "Last message from customer (envelope-8, 2026-03-21T10:30:00Z)",
      "Message contains action request: \"Please confirm by EOD\"",
      "No response from me in 48h",
      "Escalation policy triggered (customer-tier: premium)"
    ],
    "confidence": 0.85,
    "confidence_breakdown": {
      "clear_action_request": 0.3,
      "recent_activity": 0.2,
      "context_match": 0.35
    },
    "alternative_states": [
      {
        "state": "monitor_only",
        "confidence": 0.15,
        "reason": "Could be just FYI if no explicit action required"
      }
    ]
  }
}
```

### thread progress

从 `activity-pulse` 中按线程 key、主题片段或业务关键词查询当前进展。

**用法**：

```bash
twinbox thread progress QUERY [--limit 5] [--json]
```

**参数**：

- `QUERY`：线程 key、主题片段或业务关键词
- `--limit 5`：最多返回 5 条匹配
- `--json`：输出 JSON 格式

**实现映射**：

- 读取 `runtime/validation/phase-4/activity-pulse.json`
- 在 `thread_index` 中做轻量规则匹配，不依赖额外语义检索

### digest daily

显示每日摘要。

**用法**：

```bash
twinbox digest daily [--json]
```

**说明**：

- 文本模式输出为 Markdown（`#` / `##` / `-`），便于直接贴给人看
- 稳定集成或下游消费请使用 `--json`

### digest pulse

显示小时级日内脉冲，用于“今天发生了什么 / 哪些线程有推进 / 哪些待我跟进”的最小推送载荷。

**用法**：

```bash
twinbox digest pulse [--json]
```

**参数**：

- `--json`：输出 JSON 格式

**说明**：

- 文本模式输出为 Markdown（概览 + 分节列表）
- 稳定集成或下游消费请使用 `--json`

**实现映射**：

- 读取 `runtime/validation/phase-4/activity-pulse.json`
- 返回 `notifiable`、`recent_activity`、`needs_attention` 三段视图
- 同时带上最小推送载荷 `notify_payload`

> 注：`activity-pulse.json` 不会由 `digest pulse` 现算；需先运行 `twinbox-orchestrate schedule --job daytime-sync`。

## Task 路由选型标准

`task ...` 子命令不是第二套 CLI 领域模型，而是面向 hosted skill / agent runtime 的薄路由层。

设计约束：

- 必须薄包装现有只读能力，不能引入新的推理链路
- 必须服务通用用户意图，而不是某个团队特有术语
- 必须适合作为 prompt smoke 和默认 skill 入口
- 必须能清晰暴露“命令是否真的执行”这一事实

按当前实现，核心 task 维度分为：

- `latest-mail`：总览型问题，“今天发生了什么 / 最新邮件情况”
- `todo`：待办型问题，“我现在要处理什么”
- `progress`：下钻型问题，“某件事现在进展如何”
- `mailbox-status`：健康检查型问题，“邮箱配好没 / skill 能不能跑”

补充说明：

- `weekly` 保留为时间尺度更长的补充入口，但不是 hosted smoke 的第一优先级
- 如果未来想新增 task 路由，应先证明它仍然是“薄包装 + 通用意图 + 只读高可靠”，否则应考虑扩到底层命令组，而不是继续堆 `task`

### task latest-mail

为 OpenClaw / skill 场景提供的稳定任务入口，对“帮我看下最新邮件情况 / 今天发生了什么”这类提问返回统一投影。

**用法**：

```bash
twinbox task latest-mail [--json]
```

**实现语义**：

- 薄包装 `digest pulse`
- 返回 `summary`、`urgent_top_k`、`recent_activity`、`needs_attention`
- 不新增推理链路，不直接访问邮箱

### task todo

为“我有哪些待办 / 待回复 / 最值得关注的线程”提供统一任务入口。

**用法**：

```bash
twinbox task todo [--json]
```

**实现语义**：

- 薄包装 `queue urgent` + `queue pending`
- 同时附带现有 `action suggest` 与 `review list` 投影
- 不新增动作生成能力

### task progress

为“某个事情进展如何”提供统一任务入口。

**用法**：

```bash
twinbox task progress QUERY [--limit 5] [--json]
```

**实现语义**：

- 薄包装 `thread progress`
- 按 thread key、主题片段或业务关键词匹配
- JSON 输出会额外补 `recipient_role` 与 `thread_key_display`
- 当线程在 Phase 3 已被识别为 `cc_only` / `group_only` / `indirect` 时，`thread_key_display` 会带 `[CC]` 或 `[GRP]` 前缀，避免 hosted skill 在“查进展”问法下丢失收件角色信号

### task weekly

为“看当前周报/周简报”提供统一任务入口。

**用法**：

```bash
twinbox task weekly [--json]
```

**实现语义**：

- 薄包装 `digest weekly`
- 不新增周报推理逻辑

### task mailbox-status

为“邮箱配好没 / preflight 状态如何”提供统一任务入口。

**用法**：

```bash
twinbox task mailbox-status [--json]
```

**实现语义**：

- 薄包装 `mailbox preflight`
- 保留原有 `login_stage` / `status` / `missing_env` 语义

**参数**：

- `--json`：输出 JSON 格式

**输出**（文本模式）：

```text
Daily Digest (2026-03-23T09:00:00Z)

Urgent (3 items):
- thread-abc123: Customer escalation, no response in 48h
- thread-def456: ...
- thread-ghi789: ...

Pending replies (5 items):
- thread-jkl012: ...
- ...

SLA risks (2 items):
- thread-mno345: ...
- ...
```

**输出**（JSON 模式）：

```json
{
  "digest_type": "daily",
  "sections": {
    "urgent": {
      "items": [...]
    },
    "pending": {
      "items": [...]
    },
    "sla_risks": {
      "items": [...]
    }
  },
  "generated_at": "2026-03-23T09:00:00Z",
  "stale": false
}
```

### digest weekly

显示每周摘要。

**用法**：

```bash
twinbox digest weekly [--json]
```

**参数**：

- `--json`：输出 JSON 格式

**说明**：

- 文本模式输出为 Markdown
- 周报文本模式按 `config/weekly-template.md` 的默认章节渲染；如存在最新导入的 `template_hint` 材料，则优先采用该模板的标题和章节顺序
- 默认模板会把 `flow_summary` + `action_now` 合并到“本周完成”，`important_changes` + `sla_risks` 合并到“遇到的问题”，`backlog` 映射到“下周计划”，`rhythm_observation` 映射到“本周节奏”
- 若 `runtime/validation/phase-4/daily-ledger/` 内已有本周 daily snapshots，weekly 的 `important_changes` 会补回“本周早些时候进入行动面、当前已退出”的线程轨迹
- `digest weekly` 当前表示“当前周视图快照”，基于当前邮箱状态生成，不是本周 daily 的自动累计
- 稳定集成或下游消费请使用 `--json`

**输出**（文本模式）：

```markdown
# 周报 · 2026-03-18 ~ 2026-03-24

> 当前周视图快照：基于当前邮箱状态生成，不是本周 daily 的自动累计。

- 窗口周期: 2026-03-18 ~ 2026-03-24
- 窗口线程数: 12

## 本周完成

- [部署] 3 条线程: 审批链条仍是主要阻塞
- [deploy] thread-abc123: 回复审批意见 (今天要确认)

## 遇到的问题

- thread-mno345: 需求已确认 -> 可进入部署
- thread-risk-001: 客户还未确认部署窗口 (waiting_on=customer, 5d)

## 下周计划

- [support] thread-ghi789: 周三前追问供应商 (仍需跟进)

## 本周节奏

本周上午审批类线程明显增多。
```

**输出**（JSON 模式）：

```json
{
  "digest_type": "weekly",
  "sections": {
    "action_now": [
      {
        "thread_id": "thread-abc123",
        "state": "waiting_on_me",
        ...
      },
      ...
    ],
    "backlog": [
      {
        "thread_id": "thread-ghi789",
        ...
      },
      ...
    ],
    "important_changes": "3 new escalations, 5 threads closed, 2 threads moved to monitor_only"
  },
  "generated_at": "2026-03-23T09:00:00Z",
  "stale": false
}
```

## context 命令（焦点 2）

### context import-material

导入用户材料（文件）。

**用法**：

```bash
twinbox context import-material SOURCE [--intent INTENT]
```

**参数**：

- `SOURCE`：材料文件路径（位置参数）
- `--intent INTENT`：材料意图（可选，默认 `reference`）
  - `reference`：参考数据，用于排序和判断提示；如标记为 synthetic 会隔离到 material_summary
  - `template_hint`：输出格式参考，LLM 会按类似结构组织相关数据；忽略 synthetic 标记

**标准路径**：

- 会议纪要、项目台账、外部 CSV/XLSX/Markdown 等需要进入周报的材料，统一走 `twinbox context import-material FILE --intent reference`
- 导入后重新运行 `twinbox-orchestrate run --phase 4` 或常规调度，Phase 4 会把抽取内容合并进 `human_context.material_extracts_notes`
- `digest weekly` 的 `material_summary`、`action_now`、`backlog` 会基于这些 reference 材料和当前邮件线程一起生成
- 如果材料只是“周报模板长什么样”的提示，不是业务事实，请改用 `--intent template_hint`
- 默认模板文件位于 `config/weekly-template.md`；用户想改周报标题、章节顺序或措辞时，可让 agent 基于自然语言生成 Markdown 模板后用 `--intent template_hint` 导入

**输出**：

```text
已导入材料: policy.md -> runtime/context/material-extracts/policy.md
更新清单: runtime/context/material-manifest.json
已生成抽取 Markdown（供 Phase 4 引用）: runtime/context/material-extracts/policy_md.extracted.md
```

对 `.csv`、`.xlsx` / `.xlsm`、`.docx`、`.pptx`、`.md`、`.txt` 会额外生成同目录下的 `*.extracted.md`（表格转 Markdown 表，Office 为 OOXML 内文本抽取）。`twinbox-orchestrate run --phase 4` 的 context-pack 会将这些抽取合并进 `human_context.material_extracts_notes`。旧版 `.doc` / `.ppt` 需先另存为 `.docx` / `.pptx`；`.xlsx` 需安装 `openpyxl`。

**周报示例**：

```bash
twinbox context import-material weekly-notes.md --intent reference
twinbox-orchestrate run --phase 4
twinbox digest weekly
```

> 注：当前不支持 `--json` 输出。

### context material list

列出所有已导入的材料及其 intent。

**用法**：

```bash
twinbox context material list
```

**输出示例**：

```text
weekly-deployment-ledger-sample.md       intent=template_hint   imported=2026-03-24T18:18:28
project-priorities.csv                   intent=reference       imported=2026-03-25T10:30:00
```

### context material set-intent

修改材料的 intent 类型。

**用法**：

```bash
twinbox context material set-intent FILENAME INTENT
```

**参数**：

- `FILENAME`：材料文件名
- `INTENT`：新的 intent 类型（`reference` 或 `template_hint`）

**示例**：

```bash
twinbox context material set-intent weekly-deployment-ledger.md template_hint
```

### context material remove

删除已导入的材料。

**用法**：

```bash
twinbox context material remove FILENAME
```

**参数**：

- `FILENAME`：材料文件名

### context material preview

预览材料对 Phase 4 输出的影响。

**用法**：

```bash
twinbox context material preview FILENAME
```

**输出示例**：

```text
材料: weekly-deployment-ledger-sample.md
Intent: template_hint
导入时间: 2026-03-24T18:18:28

表格结构: 7 列
表头: | 资源/版本 | 产品 | 出库日 | 部署起止 | 结果 | 是否达预期 | 问题反馈 |

本周线程分布:
  LF1: 12
  UNMODELED: 20

预期影响:
- 将作为输出格式参考注入 Phase 4
- LLM 会尝试按类似结构组织相关数据
- 不会被 synthetic 规则隔离
```

### context upsert-fact

更新或插入用户确认的事实。

**用法**：

```bash
twinbox context upsert-fact --id ID --type TYPE --content CONTENT [--source SRC]
```

**参数**：

- `--id ID`：事实 ID（必选）
- `--type TYPE`：事实类型（必选）
- `--content CONTENT`：事实内容（必选）
- `--source SRC`：来源（默认 `user_confirmed_fact`）

**输出**：

```text
已添加事实: customer-tier
保存到: runtime/context/human-context.yaml
```

> 注：当前不支持 `--json` 输出。

### context profile-set

设置用户画像配置。

**用法**：

```bash
twinbox context profile-set PROFILE [--key KEY --value VALUE]
```

**参数**：

- `PROFILE`：画像名称（位置参数，必选）
- `--key KEY`：配置键（支持嵌套如 `style.language`）
- `--value VALUE`：配置值
- 不带 `--key`/`--value` 时显示当前画像内容

**输出**：

```text
已更新配置: default.style.language = formal
```

> 注：当前不支持 `--json` 输出。

### context refresh

触发 context 更新后的局部重算。

**用法**：

```bash
twinbox context refresh
```

> 注：当前实现不接受 `--full` 或 `--json` 参数。仅打印提示文本建议用户手动运行 `twinbox-orchestrate run --phase 1`。

**输出**：

```text
刷新 Phase 1 context-pack...
提示: 使用 'twinbox-orchestrate run --phase 1' 重新生成 Phase 1 artifacts
```

## 实现状态

### ✅ 阶段 1：queue 命令（已完成）

- ✅ 创建 `src/twinbox_core/task_cli.py`
- ✅ 实现 `queue list`、`queue show`、`queue explain`
- ✅ 从现有 Phase 4 artifacts 投影出 `QueueView`
- ✅ 添加 `scripts/twinbox` 作为统一入口

### ✅ 阶段 2：context 命令（已完成）

- ✅ 实现 `context import-material`、`context upsert-fact`、`context profile-set`
- ✅ 实现 `context refresh` 触发局部重算
- ✅ 定义 context 存储格式和更新协议

### ✅ 阶段 3：thread 命令（已完成）

- ✅ 实现 `thread inspect`、`thread explain`
- ✅ 从 Phase 3/4 artifacts 投影出 `ThreadCard`
- ✅ 补充 explainability 支持

### ✅ 阶段 4：digest 命令（已完成）

- ✅ 实现 `digest daily`、`digest weekly`
- ✅ 从 Phase 4 artifacts 投影出 `DigestView`
- ✅ 支持 weekly 的分层结构

### ✅ 阶段 5：action 和 review 命令（已完成）

1. ✅ 实现 `action suggest`、`action materialize`
2. ✅ 实现 `review list`、`review show`
3. ✅ 实现 `ActionCard`、`ReviewItem` 数据对象（含 `to_dict()`）
4. ✅ 添加完整单元测试覆盖（27 个测试全部通过）

### ✅ 阶段 6：rule 命令（已完成）

- ✅ 实现 `rule list`、`rule add`、`rule remove`、`rule test`
- ✅ 支持 `config/routing-rules.yaml` 的读写与回测

### 🚧 未实现命令

以下命令在命令树中声明但尚未实现，Skill 和模板不应引用：

- `thread summarize` — 线程摘要
- `action apply` — 执行行动
- `review approve` — 批准审核项
- `review reject` — 拒绝审核项

## 非目标

本规范不涉及：

- listener/action 常驻服务的实现
- 远程 runtime 的部署
- UI 或 web 界面
- 多邮箱并行支持
- 自动发送邮件（仍在 Phase Gate 控制下）

## 与现有架构的关系

- `orchestration.py`：编排层，保留不变
- `task_cli.py`：任务层，新增
- Phase 1-4 artifacts：真相源，不变
- `renderer.py`：视图层，可能需要扩展以支持 task-facing 输出

## daemon 与可选 Go 入口

- **Python daemon**：`twinbox daemon start|stop|restart|status [--json]`；协议与路径见 [daemon-and-runtime-slice.md](./daemon-and-runtime-slice.md)。
- **Go 薄客户端**：源码目录仍在 `cmd/twinbox-go/`，但**交付给用户时默认应构建为 `twinbox`**（构建与 `TWINBOX_DAEMON_SOCKET` 等见该目录 `README.md`）。当前 fallback 已会自动补 `PYTHONPATH` / `TWINBOX_STATE_ROOT` / `TWINBOX_CANONICAL_ROOT`，并在 Python import 前处理 `--profile`，因此可作为 PATH 上替代 `scripts/twinbox` 的单一入口；若走 vendor 模式，会校验 `vendor/MANIFEST.json.twinbox_version` 与 Go 客户端版本一致。
- **模组化模拟邮箱（无 IMAP）**：`python3 -m twinbox_core.modular_mail_sim` 或 `bash scripts/seed_modular_mail_sim.sh`，用于 OpenClaw 对话验收前灌数据。

## vendor（state-root 下的 Python 包副本）

- **`twinbox vendor install`**：从当前 **code root** 的 `src/twinbox_core/` 复制到 `$TWINBOX_STATE_ROOT/vendor/twinbox_core/`，并写入 `vendor/MANIFEST.json`（`--dry-run` 仅打印路径；`--json` 输出结构化结果）。
- **`twinbox vendor status`**：是否已安装、`MANIFEST` 摘要、`.py` 文件数量等（`--json`）。
- **`twinbox install --archive …`**：也会写 `vendor/MANIFEST.json`，供 Go fallback 做 `twinbox_version` attestation。若你手工把二进制命名为 `twinbox-go`，子命令形状保持不变。
- 不改变默认 `resolve_code_root` / `resolve_state_root`；宿主使用方式见 [daemon-and-runtime-slice.md](./daemon-and-runtime-slice.md)。实现：`twinbox_core.vendor_sync`、`task_cli_vendor.py`。

## 参考文档

- [ROADMAP.md](../../ROADMAP.md)
- [daemon-and-runtime-slice.md](./daemon-and-runtime-slice.md)
- [architecture.md](./architecture.md)
- [pipeline-orchestration-contract.md](./orchestration.md)
