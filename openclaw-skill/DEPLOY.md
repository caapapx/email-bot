# Twinbox × OpenClaw 部署操作主路径

> **本文面向运维**：前置条件 → 宿主接线 → 验证 → 对话引导 → 维护与卸载。
> 设计模型（三层分工、数据流）见 [docs/ref/openclaw-deploy-model.md](../docs/ref/openclaw-deploy-model.md)。
> 排障与回滚见 [TROUBLESHOOT.md](./TROUBLESHOOT.md)；附录见 [DEPLOY-APPENDIX.md](./DEPLOY-APPENDIX.md)。
> Agent 行为与命令契约见仓库根 [SKILL.md](../SKILL.md)。

---

## 1. 适用范围与路径约定

**覆盖**：Twinbox 作为 OpenClaw 托管 Markdown skill（及可选插件工具）的安装路径、`openclaw.json` 配置、roots 初始化、验证与常见误判。
**不覆盖**：OpenClaw 本体安装与升级（以 [docs.openclaw.ai](https://docs.openclaw.ai) 为准）；Claude Code / Opencode 本地 `.claude/` skill。

**路径约定**：文中 `bash scripts/...` 默认在 **Twinbox 仓库根目录** 执行。若在 `openclaw-skill/` 下，请用 `bash ../scripts/...`。

---

## 2. 推荐整体顺序

```
§3.1–§3.5（宿主接线）
  → §3.6–§3.7（验证与专用 agent）
    → §3.8（在 OpenClaw 里跑 onboarding）
      → §3.9（可选：bridge/timer 定时刷新）
```

任一步失败先查 [TROUBLESHOOT.md](./TROUBLESHOOT.md)；未完成宿主接线时，**不要**假设 skill 已注入或 onboarding 能代替 env。

---

## 3. 从零部署

### 3.1 前置：OpenClaw 可用

- 已安装并可执行 `openclaw`（示例：`npm install -g openclaw@latest`）。
- 至少能完成：`openclaw config validate`、按需启动 Gateway。

### 3.2 安装 Twinbox CLI

在仓库根按项目惯例安装 editable / 包，使宿主机上 `twinbox`、`twinbox-orchestrate` 可执行。

### 3.3 邮箱连通与首次 phase（门槛）

接 OpenClaw 托管之前，必须让宿主上的 `twinbox` 能读齐邮箱配置并跑通预检，二选一：

- **A.** 先配 `state root/.env`，执行 `twinbox mailbox preflight --json` 直到成功。
- **B.** 把完整 IMAP/SMTP 写入 `skills.entries.twinbox.env`（§3.5），重启 Gateway 后在 `twinbox` agent 里验证。

至少手动跑通一次完整产物链：

```bash
twinbox-orchestrate run --phase 4
```

若本地 CLI 与 phase 未跑通，不要宣称托管侧已可用。

### 3.4 初始化 code root / state root

避免 workspace 误当 state root、读错 `.env`。在 **仓库根**：

```bash
bash scripts/install_openclaw_twinbox_init.sh
```

作用：写入 `~/.config/twinbox/code-root`、`state-root`（及 `canonical-root`）；默认尝试验证 `twinbox mailbox preflight --json`。

**路径注意**：若 `~/.openclaw/workspace` 不存在，可加 `--no-verify` 跳过，再手工执行 preflight。

### 3.5 安装托管 skill 文件（含插件）

#### Markdown skill

```bash
cp /path/to/twinbox/SKILL.md ~/.openclaw/skills/twinbox/SKILL.md
```

在 `~/.openclaw/openclaw.json` 中启用并写入 **完整** 邮箱 env：

```json
{
  "skills": {
    "entries": {
      "twinbox": {
        "enabled": true,
        "env": {
          "IMAP_HOST": "...", "IMAP_PORT": "...",
          "IMAP_LOGIN": "...", "IMAP_PASS": "...",
          "SMTP_HOST": "...", "SMTP_PORT": "...",
          "SMTP_LOGIN": "...", "SMTP_PASS": "...",
          "MAIL_ADDRESS": "..."
        }
      }
    }
  }
}
```

**安全**：`skills.entries.*.env`、Gateway `token` 等为敏感信息，**勿提交到 git**；泄露后应轮换凭据。

#### 插件工具（推荐同步安装）

当模型频繁停在「Read SKILL.md」而不执行 CLI 时，插件提供**确定性工具**直接调用 `twinbox task … --json`：

| 项 | 说明 |
|----|------|
| 位置 | [plugin-twinbox-task/](./plugin-twinbox-task/) |
| 入口 | [index.mjs](./plugin-twinbox-task/index.mjs)、[register-twinbox-tools.mjs](./plugin-twinbox-task/register-twinbox-tools.mjs) |
| 配置 | `twinboxBin`：可执行名或绝对路径；`cwd`：Twinbox code root |
| 测试 | `node --test openclaw-skill/plugin-twinbox-task/register-twinbox-tools.test.mjs` |

安装方式以 OpenClaw 当前插件文档为准（见 [DEPLOY-APPENDIX.md §A.1](./DEPLOY-APPENDIX.md)）。插件与 Markdown skill 可并存。

然后 **重启 Gateway**，用 **新会话** 起 agent turn 检查 `systemPromptReport.skills.entries`。

### 3.6 最小验证（宿主）

```bash
openclaw config validate
openclaw skills info twinbox
```

`skills info` 显示 `Ready` **不等于** 当前会话 prompt 已注入 twinbox（见 [TROUBLESHOOT.md §1](./TROUBLESHOOT.md)）。

#### 3.6.1 Gateway 与会话级 smoke

Gateway 运行中（`openclaw gateway status` RPC probe 为 ok）时，用单次 agent turn 验证：

```bash
openclaw agent --agent twinbox --message "Acknowledge if twinbox skill is available." --json --timeout 120
```

在输出 JSON 的 `result.meta.systemPromptReport` 中核对：

- `skills.entries` 中应出现 **`twinbox`**。
- `workspaceDir` 对应 agent 配置的专用 workspace。

**注意**：部分版本 `result.payloads` 可能为空；要机器可读验收时，以宿主 shell 的 `twinbox … --json` 为准。

### 3.7 推荐使用方式

- 为 Twinbox 使用**专用 `twinbox` agent**；通用聊天用 `main`。
- 常见只读任务优先**显式** `twinbox task ...`（或插件工具），减少依赖「模型自己选命令」。
- **skill / env 变更后**：开**新 session** 验证，勿复用旧快照会话。

### 3.8 在 OpenClaw 里完成对话引导（推荐）

在 **`twinbox` agent** 且已确认 skill 进入当前会话后：

**可观测性（推荐）**：需要可靠 JSON 验收时，在宿主终端执行：

```bash
cd "$(tr -d '\n' < ~/.config/twinbox/code-root)"
twinbox onboarding status --json
```

**引导流程**：

1. 让 agent 执行 `twinbox onboarding start --json`，按返回 `prompt` 多轮对话收集信息；
   需探测服务器时配合 `twinbox mailbox detect EMAIL --json`。
2. 阶段完成后执行 `twinbox onboarding next --json`，重复直到 `current_stage` 为 `completed`；
   中途可用 `twinbox onboarding status --json` 查看进度。
3. 阶段顺序：`mailbox_login` → `profile_setup` → `material_import` → `routing_rules` → `push_subscription`。

**调度开关（对话中可设置）**：
onboarding 完成后，可在对话里启用或禁用定时任务：

```bash
twinbox schedule enable --job daytime-sync --json
twinbox schedule disable --job daytime-sync --json
```

或通过插件工具 `twinbox_schedule_enable` / `twinbox_schedule_disable` 调用（模型可直接触发）。
详见 [docs/ref/scheduling.md](../docs/ref/scheduling.md) 与 [SKILL.md](../SKILL.md) schedule 工具说明。

### 3.9 可选：调度与宿主桥接

若需 `OpenClaw cron → system-event → 宿主机 → twinbox-orchestrate`：

- `scripts/twinbox_openclaw_bridge.sh`：已有 `system-event` 文本时转发。
- `scripts/twinbox_openclaw_bridge_poll.sh`：轮询 Gateway `cron.list` / `cron.runs` 消费 Twinbox 相关 `systemEvent`。
- 样例单元：[twinbox-openclaw-bridge.service](./twinbox-openclaw-bridge.service)、[twinbox-openclaw-bridge.timer](./twinbox-openclaw-bridge.timer)；安装脚本：`scripts/install_openclaw_bridge_user_units.sh`。

---

## 4. 维护与升级

1. 修改了 CLI 行为、根 [SKILL.md](../SKILL.md) 或插件时，同步更新 [SKILL.md](../SKILL.md)。
2. 部署 skill：`cp SKILL.md ~/.openclaw/skills/twinbox/SKILL.md`
3. 重载 Gateway：`openclaw gateway restart`

变更后用新会话做一次 smoke：`skills info`、一条 `twinbox task --json`，以及按需一次 `openclaw agent … --json` 查 `systemPromptReport`。

---

## 5. 卸载

### 5.1 完整卸载

移除 systemd 单元、OpenClaw cron、sessions、skill 文件、`openclaw.json` 中 twinbox 条目、`~/.config/twinbox/` 与 runtime：

```bash
bash scripts/uninstall_openclaw_twinbox.sh
```

加 `--dry-run` 预览；加 `--with-pip` 同时卸载 Python 包。

### 5.2 仅重置运行时状态

保留 CLI、roots、openclaw.json、systemd 单元，只清空 `runtime/` 与 sessions：

```bash
bash scripts/reset_twinbox_state.sh
```

加 `--dry-run` 预览。

---

**文档版本**：本文为操作主路径；设计模型见 [docs/ref/openclaw-deploy-model.md](../docs/ref/openclaw-deploy-model.md)，排障见 [TROUBLESHOOT.md](./TROUBLESHOOT.md)，附录见 [DEPLOY-APPENDIX.md](./DEPLOY-APPENDIX.md)。
