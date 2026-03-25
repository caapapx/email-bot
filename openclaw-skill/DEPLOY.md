# OpenClaw Skill Deployment

目的：说明如何把 Twinbox 作为 `OpenClaw` 托管 skill 来准备、接入、验证，并明确当前哪些环节已经有基础、哪些仍处于待验证状态。

## 适用范围

这份文档关注的是“Twinbox skill 如何进入 OpenClaw 托管环境”。

不覆盖：

- OpenClaw 本体 Docker/Compose 安装细节
- Claude Code / Opencode 本地代理 skill

如果你还没把 OpenClaw 服务本身搭起来，先看：

- [../docs/guide/openclaw-compose.md](../docs/guide/openclaw-compose.md)

如果你要把已经验证过的 Compose 部署迁到原生 npm OpenClaw，优先看下文的“Native npm 迁移路径（已实测）”。

## 当前成熟度判断

### 已经有基础的部分

- 根级 [../SKILL.md](../SKILL.md) 已提供 `metadata.openclaw`
- `twinbox mailbox preflight --json` 已可作为登录预检接口
- `twinbox-orchestrate` 已是稳定的 phase 编排入口
- [../docs/ref/scheduling.md](../docs/ref/scheduling.md) 已定义 `schedules` 元数据和未来调度方向
- [../docs/ref/runtime.md](../docs/ref/runtime.md) 已定义 listener / action 的未来边界

### 仍未闭环或未验证的部分

- OpenClaw 是否已实际消费 `metadata.openclaw.schedules`
- OpenClaw 的 cron / heartbeat / background task 与 Twinbox phase 刷新如何对接
- listener / action / review runtime 如何在托管环境里运行
- 部署后的日志、通知、失败重试、stale fallback 责任边界
- 最终 skill 包是直接指向 repo 根，还是导出独立 package

## Native npm 迁移路径（已实测）

这条路径适用于：

- 之前已用 Docker Compose 跑通过 OpenClaw
- 已经在 Compose 版里验证过 Twinbox managed skill / xfyun 模型配置
- 现在希望切到官方默认的原生安装目录 `~/.openclaw`

### 1. 先停掉 Compose 版

在原 Compose 项目目录执行：

```bash
docker compose down
```

### 2. 备份 Compose 部署根

至少备份这三部分：

- Compose 项目目录本身
- `config/`
- `workspace/`

推荐做法是直接备份整个部署根，再迁移需要保留的状态。

### 3. 安装原生 npm 版 OpenClaw

```bash
npm install -g openclaw@latest
```

当前已实测可用版本：

- `openclaw 2026.3.23-2`

### 4. 迁到官方默认目录

原生目录默认使用：

- `~/.openclaw/openclaw.json`
- `~/.openclaw/skills/`
- `~/.openclaw/workspace/`

建议迁移：

- `config/openclaw.json`
- `config/skills/twinbox/SKILL.md`
- `config/identity/`
- `config/devices/`
- `config/memory/`
- `workspace/`

建议只备份、不直接恢复：

- `config/agents/main/sessions/`

原因：

- 该目录里的 `skillsSnapshot` 可能把旧的 skill 注入结果冻结住
- 之前的渐进式实测已经证明：旧 session snapshot 会影响 managed skill 是否进入 prompt
- 迁到 native 时，如果把这层状态原样恢复，容易误判成“skill 没迁成功”

### 5. 讯飞 MaaS / LLM key 迁移

Compose 版里如果使用了：

- `models.providers.xfyun-mass`
- `agents.defaults.model.primary = xfyun-mass/astron-code-latest`

则迁 native 时不能只复制 `openclaw.json`，还要把 `LLM_API_KEY` 一并迁走。

至少要保证二选一：

- native `openclaw.json` 中已经能解析到实际 key
- 或 native 启动环境稳定提供 `LLM_API_KEY`

否则 Gateway 会在启动期直接因为 secret 缺失失败。

### 6. Native 侧最小验证

```bash
openclaw config validate
openclaw skills info twinbox
openclaw tui
```

当前本机实测结论：

- `openclaw config validate` 已通过
- `openclaw skills info twinbox` 已显示 `Ready`
- `openclaw tui` 已成功连上 Gateway
- `openclaw agent --agent main --message "Reply with exactly: native-openclaw-ok"` 已成功完成原生模型调用
- `twinbox mailbox preflight --json` 已在宿主机直接跑通，当前返回 read-only `warn`

补充边界：

- 让 agent 在对话里“自行执行 Twinbox preflight”仍不能视为已验证
- 当前实测里，agent 在提示下返回了错误的 preflight 结论，说明 managed skill 已挂载，不等于 `preflightCommand` 或显式命令执行链已经由平台可靠消费

### 6.5 OpenClaw-native env 注入与 session 快照

这是当前 native 部署里最容易误判的一层。

实测结论：

- `openclaw skills info twinbox` 显示 `Ready`，不等于当前 agent 会话一定已经把 `twinbox` 注入到系统提示词
- Skills 是否真正进入 prompt，取决于当前 run 的 eligibility 和该会话的 `skillsSnapshot`
- 如果 Gateway 运行时拿不到 Twinbox 所需的邮箱 env，`twinbox` 会在 run 级被过滤掉，即使 `~/.openclaw/skills/twinbox/SKILL.md` 已安装

当前推荐做法不是继续依赖 repo 根 `.env` 被“碰巧读到”，而是把邮箱配置显式写进 OpenClaw config：

```json
{
  "skills": {
    "entries": {
      "twinbox": {
        "enabled": true,
        "env": {
          "IMAP_HOST": "...",
          "IMAP_PORT": "...",
          "IMAP_LOGIN": "...",
          "IMAP_PASS": "...",
          "SMTP_HOST": "...",
          "SMTP_PORT": "...",
          "SMTP_LOGIN": "...",
          "SMTP_PASS": "...",
          "MAIL_ADDRESS": "..."
        }
      }
    }
  }
}
```

然后：

1. 重启 Gateway
2. 用一个**新会话**重新起 agent turn
3. 再检查该会话的 `systemPromptReport.skills.entries` 或 `skillsSnapshot`

2026-03-25 本机实测结果：

- 在 `skills.entries.twinbox.env` 写入邮箱 env 之前
  - `twinbox` 虽然 `Ready`
  - 但 `agent:main:main` 和新建的 `agent:twinbox:main` session 都没有把 `twinbox` 注入 prompt
- 写入 `skills.entries.twinbox.env`、重启 Gateway、清掉旧 `agent:twinbox:main` 快照后
  - 新 session 的 `systemPromptReport.skills.entries` 已明确出现 `twinbox`
  - 这才算真正完成 OpenClaw-native skill 注入验证

因此：

- `state root/.env` 解决的是 Twinbox CLI 自己怎么找配置
- `skills.entries.twinbox.env` 解决的是 OpenClaw agent run 怎么让 `twinbox` 成为有资格的 skill
- 这两层不能互相替代

## 推荐部署路径

### 1. 先把 Twinbox 本地运行面跑通

最低要求：

- Twinbox 代码可安装 / 可执行
- 邮箱 env 已配置
- `twinbox mailbox preflight --json` 能返回结构化结果
- 至少能手动运行一次：

```bash
twinbox-orchestrate run --phase 4
```

如果连本地 CLI 和 phase 刷新都没跑通，不要先上 OpenClaw 托管。

### 1.5 初始化 Twinbox code root / state root

这是当前 native OpenClaw 部署里最容易遗漏、但影响很大的初始化步骤。

原因：

- Twinbox 的 `mailbox preflight`、`task_cli`、`daytime-slice` 默认都依赖 `state root`
- 如果命令是在 `~/.openclaw/workspace` 下执行，且没有 `TWINBOX_STATE_ROOT`
- Twinbox 会把 `~/.openclaw/workspace` 当成 state root，并尝试读取那里的 `.env`
- 你的真实邮箱配置通常在 Twinbox 仓库根 `.env`

结果就是：

- 宿主机直接在仓库根跑 `twinbox mailbox preflight --json` 可能成功
- 但 agent / workspace 视角下的同一命令可能表现成“缺少 IMAP/SMTP env”

当前推荐做法不是复制 secrets 到多个目录，而是一次性初始化 roots：

```bash
bash scripts/install_openclaw_twinbox_init.sh
```

它会：

- 写入 `~/.config/twinbox/code-root`
- 写入 `~/.config/twinbox/state-root`
- 兼容写入 `~/.config/twinbox/canonical-root`
- 默认再从 `~/.openclaw/workspace` 视角执行一次 `twinbox mailbox preflight --json` 验证链路

这个步骤完成后，即使命令从 OpenClaw workspace 发起，Twinbox 也会回到已配置的 `state root` 读取 `.env` 和 `runtime/`。

当前实例的默认布局仍然是：

- `code root == state root == Twinbox 仓库根`

但这只是当前自托管实例的默认值，不应再被写成唯一标准。新的正式入口是：

- `TWINBOX_CODE_ROOT` / `~/.config/twinbox/code-root`
- `TWINBOX_STATE_ROOT` / `~/.config/twinbox/state-root`
- `TWINBOX_CANONICAL_ROOT` / `canonical-root` 仅保留为 legacy alias

配置源优先级也要分开写：

- OpenClaw skill 注入的 process env 优先
- `state root/.env` 次之
- 不推荐继续依赖“当前工作目录碰巧就是 repo 根”

补充边界：

- 这只能解决“路径和状态根漂移”
- 不能证明 agent 自然语言一定会真实调用 `preflightCommand`
- 如果 agent 没有真正执行命令，而只是根据 skill manifest 自由回答，仍可能给出错误的“缺 env”结论

### 2. 校准 OpenClaw skill manifest

当前 manifest source of truth 是：

- [../SKILL.md](../SKILL.md)

重点检查：

- `metadata.openclaw.requires.env`
- `metadata.openclaw.login`
- `metadata.openclaw.schedules`

至少确认这些字段与当前实现一致：

- `preflightCommand` 使用 `twinbox mailbox preflight --json`
- schedule command 使用 `twinbox-orchestrate schedule --job ...` 或 `twinbox-orchestrate run ...`
- 不再引用 `twinbox orchestrate ...`

补充说明：

- `metadata.openclaw.schedules` 目前仍只能当“设计契约 + manifest 声明”
- 当前没有把它写成“平台已经自动消费”的证据

### 3. 决定 skill 包挂载方式

当前建议先按两种方式评估，不要过早锁死：

#### 方案 A：直接使用仓库根

适合：

- 本地自托管
- 开发期快速联调
- manifest / docs / CLI 都还在快速变化

优点：

- 不需要额外导出包
- root `SKILL.md` 就是 manifest source of truth

风险：

- 仓库内容较多，不够像最终交付物
- `.claude/`、测试、文档会一起暴露到包视角

## 推荐 session / agent 策略

对 Twinbox 这类“固定状态根 + 固定 skill + 后台调度 + 人工查进展”场景，最稳的做法不是把所有交互都放进默认 `main` 会话。

当前推荐策略：

- `main` agent：保留给通用对话
- `twinbox` agent：专门处理 Twinbox 相关问题
- `system-event / cron`：只走宿主 bridge，不写进人工会话

原因：

- `session` 会冻结自己的 `skillsSnapshot`
- `main` 会话容易携带历史 prompt、无关记忆和旧快照
- Twinbox 需要稳定命中 `twinbox` skill，而不是依赖模型在混合上下文里“自己想到要去查产物”
- 后台调度和人工聊天共用一个会话，会把“系统任务上下文”和“人工问题上下文”搅在一起

推荐操作语义：

1. 日常聊天继续用 `main`
2. 所有“看邮件 / 看产物 / 查进展 / 跑 preflight / 解释 queue”的问题，固定用 `twinbox` agent
3. Twinbox skill 或 env 配置变更后，不复用旧 Twinbox 会话，直接起一个新 session
4. `daytime-sync` / `nightly-full` / `friday-weekly` 只由 `system-event -> host service -> twinbox-orchestrate schedule --job ...` 驱动

不推荐：

- 让 `main` 会话兼做 Twinbox 专用助手
- 让 cron/system-event 把运行结果直接写回人工对话 session
- 把“skill 已安装”和“skill 已进入该会话 prompt”混成一个概念

## 多渠道 / 多 session 策略

如果后面接入 Telegram、Discord、Slack 或多个群，不能把“每个 session 都自己跑 Twinbox”当成稳定架构。

更稳的边界应该是三层：

1. **全局 truth layer**
   - 所有 Twinbox 事实只来自同一个 `state root`
   - `daytime-sync` / `nightly-full` / `friday-weekly` 只跑一次
   - 不允许每个群、每个聊天窗口各自维护一份 phase 产物
2. **订阅 / 投递 layer**
   - 哪些渠道接收推送、哪些群静默、哪些只收周报，不放在 session history 里
   - 应放进显式配置或状态文件，由宿主 bridge / notify adapter 读取
3. **交互 layer**
   - 任意 session 都可以发起“看下邮件”“看某个事情进展”“有哪些待办”
   - 但这些调用本质上都是读同一个 Twinbox truth，而不是读各自 session 的私有记忆

因此：

- **推送类任务**应该是 `job -> 产物 -> 订阅路由 -> 投递`
- **主动拉取类任务**应该是 `任意 session -> twinbox task CLI -> 同一 state root`

不应该是：

- `每个 session 各自跑一遍 phase4`
- `某个群里停推` 通过“让那个 session 自己少说话”来实现
- `主会话记住我想推给哪个群`，再把它当成唯一真相

当前仓库已经有的基础：

- 全局 truth / scheduler：`twinbox-orchestrate schedule --job ...`
- 日内最小推送载荷：`twinbox digest pulse`
- 某事进展查询：`twinbox thread progress QUERY`

当前还没有做完的，是“订阅 / 投递 layer”的持久化选择器。也就是：

- 哪些 channel 开启 Twinbox 推送
- 某个群是否只收 urgent，不收 weekly
- 某个群是否暂停推送

这部分后续应该做成显式 registry，而不是继续依赖 session。

## 为什么会出现“Read ~/.openclaw/skills/twinbox/SKILL.md”而不是返回邮件

这是当前自然语言调用链的一个硬边界。

`SKILL.md` 的作用是“教模型有哪些能力”，不是“替代命令执行结果”。所以当用户说：

- “帮我查看下最新的邮件情况”

模型完全可能只做下面这件事：

1. 发现有个 `twinbox` skill
2. 先去读 `~/.openclaw/skills/twinbox/SKILL.md`
3. 但没有继续执行 `twinbox digest pulse` / `twinbox queue list` / `twinbox mailbox preflight`

于是你看到的就会是：

- “Read with from ~/.openclaw/skills/twinbox/SKILL.md”

而不是邮件结果。

这说明：

- skill 注入成功了
- 但任务入口仍是**模型自由发挥**
- 还没有变成**确定性命令面**

更稳的做法应该是把常用 Twinbox 任务收成显式入口，而不是继续赌模型理解：

- “看最新邮件 / 今天发生了什么” -> `twinbox task latest-mail --json`
- “我有哪些待办 / 待回复” -> `twinbox task todo --json`
- “某个事情进展如何” -> `twinbox task progress QUERY --json`
- “邮箱有没有配好” -> `twinbox task mailbox-status --json`

这类入口一旦固定，任意 session 都可以调用，因为它们读的是同一个 Twinbox state root，不依赖该 session 之前聊过什么。

#### 方案 B：从 `openclaw-skill/` 导出独立 skill package

适合：

- 后续发布
- 版本化部署
- 限定 OpenClaw 只看到最小 skill 交付物

优点：

- 交付边界清楚
- 更适合升级 / 回滚 / 发布管理

风险：

- 需要额外维护导出流程
- 当前仓库还没把 package build 这件事真正做起来

## OpenClaw 官方文档与 twinbox 映射（调研备忘）

本节汇总 [docs.openclaw.ai](https://docs.openclaw.ai) 一手入口、社区参考与 twinbox 仓库契约的对应关系，便于后续扩展 skill / bridge / 插件时不偏离架构。权威顺序：官方当前文档 > 本仓库 [README.md](./README.md) 与本文实测记录 > 社区镜像站。

### 官方文档索引与精读清单

| 主题 | URL | 与 twinbox 的关系 |
|------|-----|-------------------|
| 全站索引（机器可读） | [llms.txt](https://docs.openclaw.ai/llms.txt) | 快速定位 skill / gateway / plugin / automation 页面 |
| 编写 Skill | [Creating Skills](https://docs.openclaw.ai/tools/creating-skills) | `name` / `description`、`openclaw agent` 冒烟流程 |
| 加载与优先级 | [Skills](https://docs.openclaw.ai/tools/skills) | `/skills` → `~/.openclaw/skills` → bundled；`metadata` 须单行 JSON；session 技能快照与 watcher |
| 配置模式 | [Skills Config](https://docs.openclaw.ai/tools/skills-config) | `skills.entries.twinbox.env`；**sandbox 不继承宿主 env**（见 `agents.defaults.sandbox.docker.env`） |
| CLI | [skills](https://docs.openclaw.ai/cli/skills.md) / [cron](https://docs.openclaw.ai/cli/cron.md) / [gateway](https://docs.openclaw.ai/cli/gateway.md) | 与托管安装、定时、Gateway 运维对齐 |
| HTTP 调工具 | [Tools Invoke API](https://docs.openclaw.ai/gateway/tools-invoke-http-api) | 可信操作员用 Bearer 调 `POST /tools/invoke`；**默认 HTTP 拒绝列表含 `cron`**，勿假设可用其替代 `openclaw cron` CLI |
| 定时 | [Cron Jobs](https://docs.openclaw.ai/automation/cron-jobs) | 任务存 `~/.openclaw/cron/`；`system-event` / isolated / main 等执行风格 |
| Cron vs Heartbeat | [Cron vs Heartbeat](https://docs.openclaw.ai/automation/cron-vs-heartbeat) | 精确时刻用 cron；批量「收件箱类」巡检可考虑 Heartbeat + `HEARTBEAT.md`（与 twinbox 推送策略独立评估） |
| 频道 Poll | [Polls](https://docs.openclaw.ai/automation/poll) | **指 IM 投票消息**，不是宿主机轮询 Gateway；twinbox poller 仍见 [scripts/twinbox_openclaw_bridge_poll.sh](../scripts/twinbox_openclaw_bridge_poll.sh) |
| Hooks | [Hooks](https://docs.openclaw.ai/automation/hooks.md) | 与扩展事件面相关；当前 twinbox 闭环以 cron + 宿主 bridge 为主 |
| 沙箱与策略 | [Sandboxing](https://docs.openclaw.ai/gateway/sandboxing.md) / [Sandbox vs Tool Policy](https://docs.openclaw.ai/gateway/sandbox-vs-tool-policy-vs-elevated.md) | 与 Phase 1–4 只读、限制 `exec` 面一致评估 |
| 插件 | [Building Plugins](https://docs.openclaw.ai/plugins/building-plugins.md) / [SDK Entry Points](https://docs.openclaw.ai/plugins/sdk-entrypoints.md) / [Manifest](https://docs.openclaw.ai/plugins/manifest.md) | 见下文「何时升级到插件」 |

### OpenClaw 能力 ↔ twinbox 模块

| OpenClaw 能力 | twinbox 侧落点 |
|---------------|----------------|
| `skills.entries.<name>.env` / `apiKey` | 邮箱与 Twinbox 宿主 env 的一等来源；见 [README.md](./README.md) |
| `metadata.openclaw.requires.env` / `login.preflightCommand` | 与 [SKILL.md](../SKILL.md) 及 [docs/ref/cli.md](../docs/ref/cli.md) 预检契约一致 |
| `metadata.openclaw.schedules` | 声明层；是否被平台自动消费需单独验证；调度契约见 [docs/ref/scheduling.md](../docs/ref/scheduling.md) |
| Gateway `cron` + `system-event` | 与 [scripts/twinbox_openclaw_bridge.sh](../scripts/twinbox_openclaw_bridge.sh)、poller、[`openclaw_bridge.py`](../src/twinbox_core/openclaw_bridge.py) 消费逻辑衔接 |
| `openclaw skills list` / `skills info` | 部署验证；不等于当前 session 已注入 skill |
| 插件 `api.registerTool()` | 可选：将固定 CLI 调用做成确定性工具，缓解「只读 SKILL 不执行命令」问题（见本文「方案 B」上文与下节） |

### 与根 `SKILL.md` / playbook 的对照要点

- **Frontmatter**：官方要求 `metadata` 为单行 JSON；编写规范见 [docs/ref/skill-authoring-playbook.md](../docs/ref/skill-authoring-playbook.md) 第 2 节说明。
- **Gating**：`requires.env` 与 `skills.entries.twinbox.env` 需同时满足，否则 skill 在 run 级被过滤（README 已述）。
- **`schedules`**：SKILL 内嵌的 cron 声明与 OpenClaw Gateway 原生 `openclaw cron` 任务无自动等价关系；宿主 bridge 路径仍以 Gateway 实际 job 为准。

### 何时保留 Markdown skill，何时考虑插件

| 方式 | 适用 | twinbox 现状 |
|------|------|----------------|
| Markdown `SKILL.md` + 模型选择 `exec` | 迭代快、依赖已有 `twinbox` CLI | **当前默认** |
| 插件 `registerTool`（Node/TS） | 需要稳定 schema、减少「读 skill 不跑命令」、或与 HTTP/自动化强绑定 | **按需**：维护成本更高，适合确定性任务面固化之后 |

### ClawHub / 社区样例（写法模式，非业务复制）

以下用于对照 **说明结构、凭据与前置条件**，安装第三方 skill 前仍须自行审代码（官方亦提示将第三方 skill 视为不可信）。

1. **[Ai Provider Bridge](https://clawhub.com/skills/ai-provider-bridge)**：能力表格 + 分提供商 env；正文含用法片段与免责声明；与 twinbox「命令表 + 环境变量清单」式 SKILL 结构相近。
2. **Summarize 类 skill**（如 [ClawHub: summarize](https://clawhub.ai/skills/summarize)）：依赖外部 CLI + `requires.bins` 思路；与「宿主必须安装 `twinbox` 且可执行」同一类部署约束（若要在 metadata 中声明二进制，可对照官方 [Skills](https://docs.openclaw.ai/tools/skills) gating）。
3. **[agent-zero-bridge](https://playbooks.com/skills/openclaw/skills/agent-zero-bridge)**（playbooks）：委托外部 agent 的前置条件与网关配置说明；可借鉴「何时委托、写清依赖」，不等同于邮箱只读流水线。

### 裁决顺序（与官方冲突时）

1. [docs.openclaw.ai](https://docs.openclaw.ai) 当前页面。
2. 本目录 [README.md](./README.md) 与本文档中的实测与清单。
3. 社区镜像（openclawlab、howtouseopenclaw、clawdocs 等）仅作补充。

## 部署前检查清单

以下勾选以 2026-03-25 本机 native OpenClaw + Twinbox smoke 为准；未勾选表示“仍待验证/待补证据”，不等于“尚未开始”。

- [x] `twinbox mailbox preflight --json` 本地成功
- [x] `twinbox-orchestrate run --phase 4` 本地成功
- [x] root `SKILL.md` 元数据与实现一致
- [x] schedule command 全部使用 `twinbox-orchestrate`
- [x] 未实现命令未出现在托管入口里
- [x] OpenClaw 宿主环境能拿到 Twinbox 需要的 env
- [x] `~/.config/twinbox/code-root` / `state-root` 已初始化
- [x] 如果走 native 安装，`~/.openclaw/openclaw.json` 已完成模型 / secret 迁移
- [ ] 如果从 Compose 迁来，旧 `agents/main/sessions/` 已单独备份，而不是直接恢复

## 托管接入检查清单

- [x] OpenClaw 能读取 skill manifest
- [x] `openclaw skills info twinbox` 能展示 `requires.env` gating
- [ ] 平台交互层是否会自动收集 / 透传这些 env
- [ ] OpenClaw 能调用 `preflightCommand`
- [ ] preflight 失败时，平台能把 `missing_env` / `actionable_hint` 呈现出来
- [x] preflight 成功后，宿主侧已能进入 phase 运行验证
- [x] `openclaw skills info twinbox` 显示 `Ready`
- [x] 根 `SKILL.md` 已提供显式 `twinbox task ...` 入口
- [x] agent 对话层显式触发 Twinbox 命令的路径已验证，而不是仅靠 prompt 提示“自行执行”

2026-03-25 至 2026-03-26 本机补充证据：

- 已通过真实 `openclaw agent --agent twinbox ...` prompt 验证 `twinbox task latest-mail --json`
- 已通过真实 `openclaw agent --agent twinbox ...` prompt 验证 `twinbox task todo --json`
- 已通过真实 `openclaw agent --agent twinbox ...` prompt 验证 `twinbox task progress QUERY --json`
- `twinbox task mailbox-status --json` 在真实 prompt 中暴露了参数漂移 bug：`run_preflight() got an unexpected keyword argument 'account'`
- 该 bug 已在仓库内修复为 `account_override=...`，并已通过本地 `twinbox task mailbox-status --json` 复验返回结构化 preflight 结果
- 上述证据只证明“显式 task 路由可被对话层触发”；**不等于** 平台已经自动消费 `metadata.openclaw.login.preflightCommand`

补充测试口径：

- 这些带明文命令的 prompt 是**探针式 smoke**，目标是确认 agent 有没有真的执行 Twinbox 命令
- 更接近真实用户的话术仍应单独验证，例如“帮我查看下最新的邮件情况”“这个事情现在进展如何”
- 当前本机实测里，自然话术“帮我查看下最新的邮件情况”也已经命中过一次 `twinbox task latest-mail --json`
- 但 2026-03-25 继续实测时，`agent:twinbox:main` 上两条自然话术都出现了“turn completed 但 `assistant.content=[]`”的空响应现象
- 该现象下 CLI `--json` 仍显示 `status=ok`、`summary=completed`、`usage.output>0`，说明不是超时，而是返回内容在当前主会话链路里丢失
- 继续尝试 `openclaw agent --agent twinbox --session-id ...` 与 `--to +1555...` 也没有真正创建新的 Twinbox 对话；`meta.agentMeta.sessionId` 仍回到 `39149542-a32b-400d-a9c2-aa92d89b6f02`
- 因此当前更准确的结论是：显式 task 探针已验证，但自然话术验收仍受 `agent:twinbox:main` 空响应 / session 复用问题影响

## 为什么会出现“缺少 env”回复

当前已验证，至少有两种完全不同的成因：

### 成因 A：agent 没有真实执行 `preflight`

- `openclaw skills info twinbox` 只能证明 skill metadata 已挂载
- 不能证明 agent 在自然语言对话里真的执行了 `twinbox mailbox preflight --json`
- 如果只是根据 `SKILL.md` 的 `requires.env` / `login.runtimeRequiredEnv` 自由发挥，就可能把“需要这些字段”说成“当前缺这些字段”

这也是为什么当前文档一直把“agent 在对话里自己执行 Twinbox preflight”标成未验证。

### 成因 B：state root 漂移到 `~/.openclaw/workspace`

- Twinbox 会优先从 `TWINBOX_STATE_ROOT` 或 `~/.config/twinbox/state-root` 解析 state root
- 兼容层才会再回退到 `TWINBOX_CANONICAL_ROOT` / `~/.config/twinbox/canonical-root`
- 如果两者都没有，默认就会把当前工作目录当作 state root
- 在 OpenClaw agent / workspace 场景下，这通常意味着去找 `~/.openclaw/workspace/.env`
- 而不是你的 Twinbox 仓库根 `.env`

所以初始化部署时，必须把“初始化 code root / state root”当成一等步骤，而不是可选优化。

## 调度与心跳专项检查清单

这部分当前是重点待梳理区，不应默认视为已完成。

- [x] OpenClaw Gateway 认证直连已通过：`openclaw health --url ... --token ...`
- [x] OpenClaw `system-event` 能被 Gateway 接收：`openclaw system event --mode now --json`
- [x] OpenClaw `cron` 能创建 / debug run `systemEvent` 类型 job
- [x] OpenClaw `system-event` 最小 smoke 已能稳定落到宿主机 service
- [x] 宿主机 service 已有最小消费器实现：`scripts/twinbox_openclaw_bridge_poll.sh`
- [x] 用户态宿主 service 已实际安装 [twinbox-openclaw-bridge.timer](./twinbox-openclaw-bridge.timer)
- [x] 宿主机 poller 已在非 dry-run 下调用 `twinbox-orchestrate schedule --job daytime-sync --format json`
- [x] 一次性 `agentTurn` cron job 已能生成独立 Twinbox cron session，并产出可查看摘要
- [ ] `metadata.openclaw.schedules` 是否已被平台解析
- [x] Gateway `cron -> system-event -> host poller -> schedule --job daytime-sync` 已真实触发一次
- [ ] 失败后平台是否有重试 / 告警
- [ ] stale surface 出现时，谁负责补刷
- [ ] 平台是否有 heartbeat / worker / daemon 模型
- [ ] Twinbox 是否需要实现自己的 listener manager
- [x] 当前已确认 `daytime-sync` 仍在复用最近一次 `Phase 4` overlay，而不是轻量 attention 重算

## 上线后验证清单

- [x] 至少一次日内 schedule smoke 已跑通
- [ ] weekly refresh 至少成功跑通一次
- [x] phase4 产物生成后，queue / digest 可被消费
- [x] 至少一次 chat-visible timed push smoke 已生成独立 cron session 摘要
- [ ] preflight 错误能回显给平台用户
- [ ] stale 队列能被识别并恢复
- [x] 没有自动发送 / destructive mailbox 操作
- [ ] 原生 OpenClaw 与 Compose 版的 managed skill / model config 没有漂移

## 当前建议

现阶段不要把 OpenClaw 方案写成“已具备完整托管能力”。

更准确的状态是：

- Twinbox 已经准备好了 `manifest + preflight + orchestration CLI + scheduling contract`
- OpenClaw native 安装、managed skill 迁移、TUI 连通性已经有了实测基础
- OpenClaw 的 `cron -> system-event` 这半段已经有 authenticated smoke 证据
- chat-visible 定时推送当前更准确地说是“生成独立 cron session + summary”，而不是“把摘要直接回写 `agent:twinbox:main`”
- 但 OpenClaw 托管接入，尤其是 `schedule / heartbeat / listener / action runtime`，仍然需要单独推进和验证
- 当前 `cron add` 只支持 agent message 或 `system-event` payload，没有“直接执行宿主命令”的现成入口，所以 `system-event -> 宿主机 service -> twinbox-orchestrate bridge --event-text ...` 的 bridge 仍然是刚需
- `openclaw cron add --announce` 对 `system-event` 不适合直接投到 `agent:twinbox:main`；当前实测要求非 main 的 agentTurn session，且在未配置 channel 时会报 `Channel is required`
- Twinbox 侧已经补出 bridge dispatcher：宿主 service 在拿到事件文本后，可以稳定调用 `scripts/twinbox_openclaw_bridge.sh --event-text ... --format json`；wrapper 会统一 `TWINBOX_CODE_ROOT`、`TWINBOX_STATE_ROOT` 和工作目录，再由它转发到 `schedule --job ...`
- Twinbox 侧也已经补出 host poller：宿主 service 可直接调用 `scripts/twinbox_openclaw_bridge_poll.sh --format json`，由它轮询 Gateway `cron.list` / `cron.runs`，识别新完成的 Twinbox `systemEvent` run，再转发到 `schedule`
- 本仓库已提供最小用户态 systemd 样例：
  - [twinbox-openclaw-bridge.service](./twinbox-openclaw-bridge.service)
  - [twinbox-openclaw-bridge.timer](./twinbox-openclaw-bridge.timer)
  - [twinbox-openclaw-bridge.env.example](./twinbox-openclaw-bridge.env.example)
  - [../scripts/install_openclaw_bridge_user_units.sh](../scripts/install_openclaw_bridge_user_units.sh)
- 当前推荐安装路径：
  - `openclaw gateway install --force`
  - `bash scripts/install_openclaw_bridge_user_units.sh`
- 日内链路当前仍处于“`Phase 1` truth + `activity-pulse` overlay 最近一次 `Phase 4` 队列”的阶段，不应误写成终态

下一步建议优先级：

1. 跑通 OpenClaw 对 `preflightCommand` 的真实消费
2. 把用户态宿主 service 真正安装为 [twinbox-openclaw-bridge.timer](./twinbox-openclaw-bridge.timer)，形成 `OpenClaw cron -> Gateway cron.runs -> host poller -> bridge -> schedule` 最小闭环
3. 再验证 `metadata.openclaw.schedules` 是否会被真实执行，或明确继续只把它当声明层
4. 再决定是直接用 repo 根，还是从 `openclaw-skill/` 导出独立包
