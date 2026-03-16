# email-bot

面向 OpenClaw 的 Himalaya 邮件代理脚手架。目标不是“自动发邮件”，而是把邮箱变成一个可控的 AI 工作台：先分拣、再产出本地草稿、最后由人工确认发送。

## 现在这个项目解决什么

这个仓库把三件容易散掉的能力收拢到一起：

1. 用 `himalaya` 作为邮件传输层，统一 IMAP/SMTP 与 JSON 输出。
2. 用 `SKILL.md` + `policy.default.yaml` 定义分拣、草稿、守护规则和学习闭环。
3. 用本地 `runtime/drafts/` 队列承接 Human-in-the-Loop，而不是把“生成草稿”和“发送”混成一个动作。

## Day-1 可见价值

用户第一次接入后，应立即看到：

- `今日紧急清单`：哪些邮件最需要今天处理
- `待确认草稿队列`：哪些回复已经能直接复核
- `可见指标`：已分拣数量、已生成草稿、SLA 风险、预估节省时间

这三项直接对应价值实现里的“价值清晰度”“价值感知”和“价值时间线”。

## 核心工作流

1. `himalaya envelope list --output json` 拉取信封列表
2. Agent 按 `config/policy.default.yaml` 输出 `intent + priority + suggested_folder + summary_3bullet`
3. 需要回复时，把草稿先写到 `runtime/drafts/{{thread_id}}.eml`
4. 人工复核草稿；必要时在本地邮件客户端继续编辑
5. 只有收到显式 `CONFIRM_SEND` 后，才允许 `himalaya template send`
6. 如果用户使用 `!learn` / `!rule` / `!edit`，系统提议一条新规则并写入 profile 规则文件

## 目录说明

- `.env`：本地凭证与运行参数，不提交
- `.env.example`：环境变量模板，已支持 `keyring`
- `SKILL.md`：OpenClaw 技能契约
- `config/policy.default.yaml`：全局策略、路由、安全、学习、指标
- `config/profiles/*.yaml`：角色配置
- `config/profiles/rules/*.md`：人工确认后的角色规则沉淀
- `docs/architecture.md`：架构拆分与实现原则
- `scripts/check_env.sh`：环境变量检查
- `scripts/render_himalaya_config.sh`：渲染 `runtime/himalaya/config.toml`

## 快速开始

1. 根据 `.env.example` 填写 `.env`
2. 执行 `bash scripts/check_env.sh`
3. 执行 `bash scripts/render_himalaya_config.sh`
4. 检查生成的 `runtime/himalaya/config.toml`
5. 将 `SKILL.md` 接入 OpenClaw

## 安全默认值

- 默认 `auto_send: false`
- 发送前必须出现显式令牌 `CONFIRM_SEND`
- 外部回复、法务/财务主题、带附件邮件默认进人工复核
- 原始邮件正文只允许停留在本地运行目录
- 学习闭环一次只允许提议一条规则，且必须人工确认后落盘

## Himalaya 对齐点

项目当前内容已对齐官方 Himalaya 的三项关键能力：

- `--output json`：便于 OpenClaw 直接消费结构化输出
- `backend.auth.keyring` / `message.send.backend.auth.keyring`：避免把密码硬编码进配置
- `template send`：支持“本地 `.eml` 草稿 -> 人工确认 -> 发送”的闭环

## 为什么这版比初始版更可用

初始版更像“邮箱连接脚手架”；当前版本已经补齐了更接近真实落地的四个缺口：

- 有明确的 Day-1 可见输出，而不是只描述架构
- 有本地草稿队列，而不是抽象地说“生成回复”
- 有 `CONFIRM_SEND` 守护规则，而不是笼统说“人工审批”
- 有 `!learn` 学习闭环，把人工修订沉淀为可复用规则
