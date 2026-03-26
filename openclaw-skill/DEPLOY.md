# Twinbox × OpenClaw 部署指南

本文档是 **Twinbox 在 OpenClaw 托管环境下的正式部署说明**：前置条件、从零安装顺序、配置要点、可选插件、验证清单、排障与回滚。与仓库根 [SKILL.md](../SKILL.md)（manifest / 运行时契约）分工为：**SKILL.md 面向 agent 行为；本文面向运维与集成。**

---

## 1. 导读

### 1.1 适用范围

- **覆盖**：Twinbox 作为 OpenClaw **托管 Markdown skill**（及可选 **插件工具**）的安装路径、`openclaw.json` 配置、roots 初始化、验证与常见误判。
- **不覆盖**：OpenClaw 本体的安装与升级（以 [docs.openclaw.ai](https://docs.openclaw.ai) 与你选用的发行方式为准）；Claude Code / Opencode 本地 `.claude/` skill。

### 1.2 「人性化引导」与本文的关系

- **应用内配置**：`twinbox onboarding` 等对话式流程覆盖邮箱探测、画像、路由规则等 **用户态配置**，详见 [docs/ref/cli.md](../docs/ref/cli.md)。**这不等于** OpenClaw Gateway、skill 文件、宿主 env 会自动配好。
- **宿主部署**：OpenClaw 安装、skill 同步、`skills.entries.twinbox.env`、Gateway 重启、bridge/systemd 等 **必须由运维按本文或脚本执行**；仓库内 **没有** 统一的「一键向导」或聊天内闭环部署产品。
- 目录说明 [README.md](./README.md) 中的策略与 smoke 摘要仍有效；**逐步命令以本文 §2 为准**（避免与 README 中「从 `openclaw-skill/` 相对路径」混用时的 cwd 歧义）。

### 1.3 你该先看哪一节

| 情况 | 下一步 |
|------|--------|
| 还没有 OpenClaw 服务 | 先按官方文档完成安装并使 Gateway 可用 |
| 全新 **原生 npm** OpenClaw，要接 Twinbox | **§2 从零部署（主路径）** |
| 只更新仓库或改了 CLI / Tool | **§3 维护与升级** |
| 希望确定性工具而非「只读 SKILL」 | **§4 可选：`plugin-twinbox-task`** |

### 1.4 路径约定

- 文中 `bash scripts/...` 默认在 **Twinbox 仓库根目录** 执行。
- 若你当前在 `openclaw-skill/` 下，请使用 `bash ../scripts/...`。

---

## 2. 从零部署（主路径）

按顺序执行；任一步失败先排障，不要跳到 OpenClaw 托管验证。

### 2.1 前置：OpenClaw 可用

- 已安装并可执行 `openclaw`（示例：`npm install -g openclaw@latest`）。
- 至少能完成：`openclaw config validate`、按需启动 Gateway（以你环境为准）。

### 2.2 安装 Twinbox CLI

- 在仓库根按项目惯例安装 editable / 包，使宿主机上 `twinbox`、`twinbox-orchestrate` 可执行。

### 2.3 邮箱与本地运行面

- 配置邮箱相关环境变量（或 state root 下的 `.env`），直到：

```bash
twinbox mailbox preflight --json
```

返回结构化成功结果。

- 可选：用 `twinbox onboarding` 完成画像与规则等 **应用内** 配置（与 OpenClaw 无关）。

- 至少手动跑通一次：

```bash
twinbox-orchestrate run --phase 4
```

若本地 CLI 与 phase 未跑通，**不要**先接 OpenClaw 托管。

### 2.4 初始化 code root / state root（强烈建议）

避免从 `~/.openclaw/workspace` 执行命令时把 workspace 误当作 state root、去读错误的 `.env`。

在 **仓库根**：

```bash
bash scripts/install_openclaw_twinbox_init.sh
```

作用概要：

- 写入 `~/.config/twinbox/code-root`、`state-root`（及兼容的 `canonical-root`）。
- 默认会从 workspace 视角尝试验证 `twinbox mailbox preflight --json` 链路（以脚本实现为准）。

语义：

- **`skills.entries.twinbox.env`**：OpenClaw agent run 侧的一等邮箱配置源（见 §5）。
- **`state root/.env`**：本地开发与自托管 fallback。
- 不推荐依赖「当前 shell cwd 碰巧是仓库根」。

### 2.5 安装托管 skill 文件

Manifest 的单一事实源是仓库根 [SKILL.md](../SKILL.md)。部署前核对其中 `metadata.openclaw`（如 `requires.env`、`login`、`schedules`）；**`schedules` 目前仍属设计契约**，是否被平台自动消费见 **§10**。

安装到 OpenClaw skills 目录，例如：

```bash
cp /path/to/twinbox/SKILL.md ~/.openclaw/skills/twinbox/SKILL.md
```

（路径按你的克隆位置替换。）

在 `~/.openclaw/openclaw.json` 中启用 twinbox，并写入 **完整** 邮箱相关 env（字段需与 [SKILL.md](../SKILL.md) 中 `metadata.openclaw.requires.env` 一致），示例结构：

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

然后 **重启 Gateway**，并用 **新会话** 起 agent turn，再检查该会话的 `systemPromptReport.skills.entries` 或 `skillsSnapshot`（见 §5）。

### 2.6 最小验证（宿主）

```bash
openclaw config validate
openclaw skills info twinbox
openclaw tui
```

本仓库曾实测：`openclaw skills info twinbox` 显示 `Ready` **不等于** 当前会话 prompt 已包含 `twinbox`；**env 未注入 run 时 skill 会在 run 级被过滤**。

### 2.7 推荐使用方式

- 为 Twinbox 使用 **专用 `twinbox` agent**；通用聊天用 `main`。
- 常见只读任务优先 **显式** `twinbox task ...`（或 §4 插件工具），减少对「模型自己选命令」的依赖。
- **skill / env 变更后**：开 **新 session** 验证，勿复用可能冻结旧 `skillsSnapshot` 的会话。

### 2.8 可选：调度与宿主桥接

若需 `OpenClaw cron → system-event → 宿主机 → twinbox-orchestrate`，见 **§6** 与目录内 `twinbox-openclaw-bridge.service` / `.timer`、`scripts/install_openclaw_bridge_user_units.sh`。

---

## 3. 维护与升级

与 [AGENTS.md](../AGENTS.md) 保持一致：

1. 修改了 CLI 行为、根 [SKILL.md](../SKILL.md) 或 OpenClaw Tool / `register-twinbox-tools.mjs` 时，同步更新 [SKILL.md](../SKILL.md)（及 `.agents/skills/twinbox/SKILL.md` 等副本，若仓库内维护）。
2. 将 skill 部署到本机 OpenClaw：  
   `cp SKILL.md ~/.openclaw/skills/twinbox/SKILL.md`
3. 使 Gateway 重新加载：  
   `openclaw gateway restart`（或你环境中的等价操作）。

变更后按 **§2.6–2.7** 用新会话做一次 smoke。

---

## 4. 可选：`plugin-twinbox-task`

当托管 agent 经常停在「Read `~/.openclaw/skills/twinbox/SKILL.md`」而不执行 CLI 时，可在 OpenClaw 侧注册 **确定性工具**，直接 `spawn` 宿主上的 `twinbox task … --json`。

| 项 | 说明 |
|----|------|
| 位置 | [plugin-twinbox-task/](./plugin-twinbox-task/) |
| 入口 | [index.mjs](./plugin-twinbox-task/index.mjs)、[register-twinbox-tools.mjs](./plugin-twinbox-task/register-twinbox-tools.mjs) |
| 清单 | [openclaw.plugin.json](./plugin-twinbox-task/openclaw.plugin.json) |
| 配置 | `twinboxBin`：可执行名或绝对路径；`cwd`：Twinbox **code root**，默认回落 `TWINBOX_CODE_ROOT` 或 `~/.config/twinbox/code-root` |
| 测试 | `node --test openclaw-skill/plugin-twinbox-task/register-twinbox-tools.test.mjs`（在仓库根或按包脚本执行） |

插件与 Markdown skill **可并存**：skill 负责契约与文档；插件负责高频、只读、需稳定 schema 的调用面。安装方式以 OpenClaw 当前插件文档为准（参见 **附录 A** 插件链接）。

---

## 5. 配置深层说明：env 与会话快照

### 5.1 两层 env 不可互换

- **`state root/.env`**：Twinbox CLI 自身解析配置。
- **`skills.entries.twinbox.env`**：OpenClaw 在 **agent run** 中注入给 skill 的环境；缺省时 skill 可能被过滤，即使磁盘上已安装 `SKILL.md`。

### 5.2 本机曾观测（2026-03-25）

- 写入 `skills.entries.twinbox.env` **之前**：`twinbox` 虽 `Ready`，`agent:main:main` 与新建 `agent:twinbox:main` 可能都 **未** 在 prompt 中出现 `twinbox`。
- 写入 env、重启 Gateway、清理旧 `agent:twinbox:main` 快照后：新会话的 `systemPromptReport.skills.entries` 可出现 `twinbox`。

操作建议：改 env 后 **重启 Gateway → 新会话 → 再查快照**。

### 5.3 `preflightCommand` 与对话层

`openclaw skills info twinbox` 与「agent 在自然语言里真的执行了 `twinbox mailbox preflight`」**不是**同一回事；不要将模型口头结论当作 preflight 结果。

---

## 6. 推荐 session / agent 与多渠道

### 6.1 Session 策略

- **`main`**：通用对话。
- **`twinbox`**：邮件、队列、产物、preflight、`twinbox task` 相关。
- **`system-event` / cron**：只驱动宿主 bridge，不把系统任务写进人工聊天 session。

原因：`session` 会冻结 `skillsSnapshot`；混合上下文下模型未必稳定命中 Twinbox。

### 6.2 多渠道时的边界

- **全局 truth**：单一 `state root`；`daytime-sync` / `nightly-full` / `friday-weekly` 只应有一套调度写产物。
- **订阅 / 投递**：哪些渠道收推送应收口到配置或状态文件，由 bridge / notify 读取，而非分散在各 session 记忆。
- **交互**：任意 session 可读同一 state；主动拉取优先 `twinbox task` / 插件工具。

### 6.3 为何有时只看到「Read SKILL.md」

用户问「最新邮件」时，模型可能只读 `SKILL.md` 而不执行 CLI。**更稳**的映射是显式 `twinbox task latest-mail --json` 等（或 §4 插件）。详见 [SKILL.md](../SKILL.md) 中的 task 入口说明。

### 6.4 宿主桥接与 systemd 样例

- `scripts/twinbox_openclaw_bridge.sh`：已有 `system-event` 文本时转发。
- `scripts/twinbox_openclaw_bridge_poll.sh`：轮询 Gateway `cron.list` / `cron.runs` 消费 Twinbox 相关 `systemEvent`。
- 样例单元：[twinbox-openclaw-bridge.service](./twinbox-openclaw-bridge.service)、[twinbox-openclaw-bridge.timer](./twinbox-openclaw-bridge.timer)、[twinbox-openclaw-bridge.env.example](./twinbox-openclaw-bridge.env.example)；安装脚本：`scripts/install_openclaw_bridge_user_units.sh`。

推荐组合（与历史实测一致）：`openclaw gateway install --force` 后安装用户态 timer/service。

---

## 7. Skill 交付形态（选型）

### 7.1 方案 A：直接使用仓库根

适合自托管与快速迭代；根 [SKILL.md](../SKILL.md) 即 manifest。注意仓库体积大，`.claude/`、测试与文档会一同存在。

### 7.2 方案 B：从 `openclaw-skill/` 导出独立包

适合版本化发布与清晰交付边界；需额外维护导出流程（仓库内尚未定型为单一 build）。

---

## 8. 排障：「缺少 env」类回复

### 8.1 成因 A：未真实执行 preflight

模型可能仅根据 `requires.env` **描述**「缺字段」，而非执行 `twinbox mailbox preflight --json`。以 CLI 在宿主上直接跑的结果为准。

### 8.2 成因 B：state root 漂移到 workspace

未配置 `~/.config/twinbox/state-root` 等时，在 workspace cwd 下可能回落到 `~/.openclaw/workspace/.env`。请执行 **§2.4** 并核对 **§5**。

---

## 9. 回滚与恢复

1. **配置**：保留备份的 `openclaw.json`、skills 目录与 Twinbox `state root`；回滚时恢复 **已知良好** 版本。
2. **会话状态**：避免把含陈旧 `skillsSnapshot` 的 `sessions/` 直接当作「恢复即上线」；必要时删特定 agent session 或新建会话验证。
3. **技能文件**：回滚 [SKILL.md](../SKILL.md) 后重复 **§3** 的复制与 Gateway 重启。

---

## 10. 成熟度与当前判断

### 10.1 已有基础

- 根 [SKILL.md](../SKILL.md) 含 `metadata.openclaw`。
- `twinbox mailbox preflight --json`、`twinbox-orchestrate`、调度契约文档（[docs/ref/scheduling.md](../docs/ref/scheduling.md)、[docs/ref/runtime.md](../docs/ref/runtime.md)）已形成。

### 10.2 仍未闭环或未验证（摘录）

- 平台是否自动消费 `metadata.openclaw.schedules`。
- OpenClaw cron / heartbeat 与 Twinbox phase 刷新的完整责任边界。
- listener / action / review 在托管环境中的运行方式。
- 部署后日志、通知、失败重试、stale fallback 的归属。

### 10.3 当前建议（摘要）

- 不把方案写成「完整托管已结束」；以 **manifest + CLI + bridge** 为实，托管调度与平台预检消费为待验项。
- 优先：**§2 / §3** 的稳定部署面；宿主 **poller + bridge** 闭环；再验证 `preflightCommand` 与 `metadata.openclaw.schedules` 的真实消费或明确其为声明层。

更细的排期与历史实测段落见 **附录 B** 检查清单中的勾选与备注。

---

## 附录 A：OpenClaw 官方文档与 twinbox 映射

本节汇总 [docs.openclaw.ai](https://docs.openclaw.ai) 入口与本仓库契约的对应关系。权威顺序：**官方当前文档 > 本目录 [README.md](./README.md) 与本文实测 > 社区镜像**。

### A.1 官方文档索引与精读清单

| 主题 | URL | 与 twinbox 的关系 |
|------|-----|-------------------|
| 全站索引（机器可读） | [llms.txt](https://docs.openclaw.ai/llms.txt) | 快速定位 skill / gateway / plugin / automation |
| 编写 Skill | [Creating Skills](https://docs.openclaw.ai/tools/creating-skills) | `name` / `description`、`openclaw agent` 冒烟 |
| 加载与优先级 | [Skills](https://docs.openclaw.ai/tools/skills) | `/skills` → `~/.openclaw/skills`；`metadata` 单行 JSON；session 快照 |
| 配置模式 | [Skills Config](https://docs.openclaw.ai/tools/skills-config) | `skills.entries.twinbox.env`；sandbox 不继承宿主 env |
| CLI | [skills](https://docs.openclaw.ai/cli/skills.md) / [cron](https://docs.openclaw.ai/cli/cron.md) / [gateway](https://docs.openclaw.ai/cli/gateway.md) | 安装、定时、Gateway 运维 |
| HTTP 调工具 | [Tools Invoke API](https://docs.openclaw.ai/gateway/tools-invoke-http-api) | Bearer `POST /tools/invoke`；默认拒绝列表含 `cron` |
| 定时 | [Cron Jobs](https://docs.openclaw.ai/automation/cron-jobs) | `~/.openclaw/cron/`；`system-event` 等 |
| Cron vs Heartbeat | [Cron vs Heartbeat](https://docs.openclaw.ai/automation/cron-vs-heartbeat) | 精确时刻 vs 批量巡检 |
| 频道 Poll | [Polls](https://docs.openclaw.ai/automation/poll) | IM 投票，非宿主机轮询 |
| Hooks | [Hooks](https://docs.openclaw.ai/automation/hooks.md) | 事件扩展；twinbox 当前以 cron + bridge 为主 |
| 沙箱与策略 | [Sandboxing](https://docs.openclaw.ai/gateway/sandboxing.md) 等 | 与 Phase 1–4 只读一致评估 |
| 插件 | [Building Plugins](https://docs.openclaw.ai/plugins/building-plugins.md) 等 | 见本文 §4 |

### A.2 OpenClaw 能力 ↔ twinbox 模块

| OpenClaw 能力 | twinbox 侧落点 |
|---------------|----------------|
| `skills.entries.<name>.env` | 邮箱与宿主 env；§5 |
| `metadata.openclaw.requires.env` / `login.preflightCommand` | [SKILL.md](../SKILL.md)、[docs/ref/cli.md](../docs/ref/cli.md) |
| `metadata.openclaw.schedules` | 声明层；[docs/ref/scheduling.md](../docs/ref/scheduling.md) |
| Gateway `cron` + `system-event` | [scripts/twinbox_openclaw_bridge.sh](../scripts/twinbox_openclaw_bridge.sh)、poller、[openclaw_bridge.py](../src/twinbox_core/openclaw_bridge.py) |
| `openclaw skills list` / `info` | 部署验证；≠ 当前 session 已注入 |
| 插件 `registerTool()` | §4；缓解「只读 SKILL」 |

### A.3 Markdown skill 与插件

| 方式 | 适用 | twinbox 现状 |
|------|------|----------------|
| Markdown `SKILL.md` + exec | 迭代快 | **默认** |
| 插件 `registerTool` | 稳定 schema、确定性任务 | **按需**，§4 |

### A.4 ClawHub / 社区样例（结构参考）

第三方 skill 视为不可信代码，仅借鉴文档结构：如 [Ai Provider Bridge](https://clawhub.com/skills/ai-provider-bridge)、[summarize](https://clawhub.ai/skills/summarize)、[agent-zero-bridge](https://playbooks.com/skills/openclaw/skills/agent-zero-bridge)。

---

## 附录 B：验证检查清单

以下勾选以仓库内 native + Twinbox smoke 为参考；未勾选表示待验证或待补证据。

### B.1 部署前（宿主 / Twinbox）

- [x] `twinbox mailbox preflight --json` 本地成功
- [x] `twinbox-orchestrate run --phase 4` 本地成功
- [x] 根 [SKILL.md](../SKILL.md) 元数据与实现一致
- [x] schedule 相关命令使用 `twinbox-orchestrate`
- [x] OpenClaw 侧能拿到 Twinbox 所需 env（含 `skills.entries.twinbox.env`）
- [x] `~/.config/twinbox/code-root` / `state-root` 已初始化
- [x] `~/.openclaw/openclaw.json` 模型与 secret 已就绪

### B.2 托管接入

- [x] OpenClaw 能读取 skill manifest
- [x] `openclaw skills info twinbox` 展示 `requires.env`
- [ ] 平台是否自动收集 / 透传 env
- [ ] OpenClaw 是否调用 `preflightCommand`；失败时是否呈现 `missing_env` / `actionable_hint`
- [x] preflight 成功后宿主可进入 phase 验证
- [x] `openclaw skills info twinbox` 显示 `Ready`
- [x] 根 SKILL 已提供 `twinbox task ...` 入口
- [x] 显式探针可触发 `twinbox task`（不等于自然话术已稳定）

**验证记录（摘录）**：2026-03-25 起，本机曾用 `openclaw agent --agent twinbox` 对 `latest-mail`、`todo`、`progress` 等做探针；曾暴露 `mailbox-status` 参数问题（已修复为 `account_override`）。自然话术与空 `assistant.content`、isolated cron session 行为等仍属平台与路由层待观察项，**不应**将单次探针等同于产品级 SLA。

### B.3 调度与桥接

- [x] Gateway 健康检查与 `system-event` smoke
- [x] `cron` 创建 / debug `systemEvent` job
- [x] 宿主机 poller：`scripts/twinbox_openclaw_bridge_poll.sh`
- [x] 用户态 timer 样例安装与 `daytime-sync` 触发（以你环境日志为准）
- [ ] `metadata.openclaw.schedules` 是否被平台解析
- [ ] 失败重试 / 告警 / stale 恢复责任
- [x] 已确认 `daytime-sync` 与 Phase 4 overlay 等行为边界（见调度文档）

### B.4 上线后

- [x] 至少一次日内 schedule smoke
- [ ] weekly refresh 至少成功一次
- [x] phase4 产物可被 queue / digest 消费
- [x] 至少一次 chat-visible 定时推送类 smoke（独立 cron session）
- [ ] preflight 错误对终端用户可见
- [ ] stale 队列识别与恢复
- [x] 无自动发送 / 破坏性邮箱操作

---

**文档版本说明**：本文由 `openclaw-skill/DEPLOY.md` 演进而来，主路径以 **§2** 为准。
