# OpenClaw Skill 设计模式：高星案例对比与 Twinbox 改进分析

> 2026-03-25 | 案例来源：ClawHub 高星 skill

---

## 案例概览

| Skill | 星数 | 安装量 | 核心模式 | 亮点 |
|---|---|---|---|---|
| **Gog** (steipete) | 781 | 132k | CLI wrapper | 极简 SKILL.md，1.7KB 全覆盖 |
| **Self-Improving Agent** (pskoett) | 2.6k | 294k | Hook + 文件伺服 | 15 文件完整体系，hook 自动激活 |
| **Proactive Agent** (halthelobster) | 621 | 117k | WAL + Cron 伺服 | 状态持久化架构，13 文件 |

---

## 1. Gog — CLI Wrapper 的极简标杆

### SKILL.md 全文仅 1.7KB

**结构**：
```
Setup (once) → Common commands → Notes
```

**设计特点**：
- 无 frontmatter 之外的元数据膨胀
- 每个命令都是可直接复制执行的完整 `gog` 命令
- `GOG_ACCOUNT` 环境变量避免重复 `--account`
- 对确认型操作（send mail / create event）有明确 "Confirm before" 提示
- `--json` + `--no-input` 组合推荐给脚本场景

**Registry metadata**：
- `bins: gog` 声明运行时二进制依赖
- `brew install steipete/tap/gogcli` 安装路径

### 与 twinbox 对比

| 维度 | Gog | Twinbox |
|---|---|---|
| SKILL.md 大小 | 1.7KB | ~5KB |
| 命令列表方式 | 纯命令示例 | intent → command 表格 |
| 安装说明 | 在 registry metadata 中 | 散布在多个文件 |
| 失败模式防护 | 无（极简） | 大量 "Turn contract" 防护 |
| env 声明 | metadata 中完整 | metadata 中完整 |

**启发**：
- Gog 证明 CLI wrapper skill **可以极简**——只要命令本身是自解释的
- Twinbox 需要大量 Turn contract 是因为 OpenClaw agent 容易"空转"——这说明根本问题不在 skill 而在 **session 设计**
- Gog 的 `bins: gog` 声明是 twinbox 缺少的：twinbox 应声明 `bins: twinbox, twinbox-orchestrate`

---

## 2. Self-Improving Agent — Hook 驱动的文件伺服

### 架构

```
~/.openclaw/workspace/
├── .learnings/           ← 核心伺服状态（磁盘文件）
│   ├── LEARNINGS.md
│   ├── ERRORS.md
│   └── FEATURE_REQUESTS.md
├── AGENTS.md             ← promotion 目标
├── SOUL.md               ← promotion 目标
└── TOOLS.md              ← promotion 目标
```

### 伺服模式

**状态生命周期**：
```
检测触发 → 记录到 .learnings/ → 关联已有条目 → 达标后 promote 到全局文件
```

**关键模式**：

1. **Hook 自动激活**：`UserPromptSubmit` hook 注入提醒，`PostToolUse` hook 自动检测错误
2. **结构化日志格式**：`[LRN-YYYYMMDD-XXX]` ID 系统，带 Priority/Status/Area 元数据
3. **Promotion 机制**：learning 证明可泛化后，从 `.learnings/` 提升到 `AGENTS.md` / `SOUL.md` / `TOOLS.md`
4. **Recurrence 检测**：`Pattern-Key` 去重，`Recurrence-Count >= 3` 触发自动 promotion
5. **Skill 抽取**：learning 足够成熟时，`extract-skill.sh` 一键创建新 skill

### 与 twinbox 对比

| 维度 | Self-Improving | Twinbox |
|---|---|---|
| 触发方式 | Hook 自动注入 | 用户显式调用 |
| 状态位置 | `.learnings/*.md` 文件 | `runtime/` 目录（CLI 产物） |
| 状态格式 | 结构化 markdown 条目 | JSON（`--json`） |
| 跨会话持久 | 是（workspace 文件） | 是（磁盘文件） |
| 自我进化 | 有（promotion + skill 抽取） | 无 |
| 多 agent 支持 | 有（Claude Code/Codex/Copilot/OpenClaw） | 有（Claude Code/OpenClaw） |

**启发**：
- Twinbox 可以学 Self-Improving 的 **hook 模式**：在 `UserPromptSubmit` 时自动注入最近邮件摘要或待办提醒，而不是等用户主动问
- `.learnings/` 的 promotion 模式可以用于 twinbox 的 **模式识别**：比如某个联系人总是延迟回复，自动记录并提升到 context
- `Pattern-Key` 去重 + `Recurrence-Count` 阈值是成熟的反膨胀机制

---

## 3. Proactive Agent — WAL + Cron 的伺服架构

### 架构

```
workspace/
├── SESSION-STATE.md      ← WAL 目标（活跃工作记忆）
├── memory/
│   ├── YYYY-MM-DD.md     ← 每日原始日志
│   └── working-buffer.md ← 危险区日志
├── HEARTBEAT.md          ← 周期性自检清单
├── SOUL.md               ← 身份/边界
├── USER.md               ← 用户 context
├── ONBOARDING.md         ← 首次运行引导
└── AGENTS.md             ← 操作规则
```

### 核心伺服模式

**1. WAL (Write-Ahead Log) 协议**

```
每条用户消息 → 扫描 6 类信号（纠正/专有名词/偏好/决策/草稿/具体值）
→ 命中则 STOP → 先写 SESSION-STATE.md → 再回复用户
```

**2. Working Buffer 协议**

```
context 达 60% → 清空旧 buffer，开始记录每条交互
→ 压缩后 → 先读 buffer 恢复上下文 → 再继续工作
```

**3. Autonomous Cron 架构**

两种 cron 模式：

| 类型 | 机制 | 适用场景 |
|---|---|---|
| `systemEvent` | 向主会话发 prompt | 需要交互的任务 |
| `isolated agentTurn` | 派生子 agent 独立执行 | 后台维护/检查 |

**4. Verify Implementation, Not Intent**

核心教训：改文案 ≠ 改行为。必须验证 **机制** 变了，不只是 **文字** 变了。

### 与 twinbox 对比

| 维度 | Proactive Agent | Twinbox |
|---|---|---|
| 状态持久化 | WAL → SESSION-STATE.md | CLI 产物 → runtime/ |
| context 管理 | Working Buffer（60% 阈值） | 无 |
| Cron 架构 | systemEvent + isolated agentTurn | openclaw cron → bridge → orchestrate |
| 自检 | HEARTBEAT.md 周期清单 | 无 |
| 首次运行 | ONBOARDING.md 引导流 | mailbox preflight |
| 安全模型 | 详细的 scope 规则 | read-only 默认 |

**启发**：
- Twinbox 的 bridge poller 本质就是 Proactive Agent 的 `isolated agentTurn` 模式——但 twinbox 没有显式区分 systemEvent vs isolated
- WAL 协议对 twinbox 的价值：用户纠正联系人姓名/项目关键词时，应先写入 context profile 再回复
- Working Buffer 概念可以应用于 twinbox：长会话中邮件 context 丢失时的恢复机制
- HEARTBEAT 清单可以用于 twinbox：定期检查队列新鲜度 + 连接状态

---

## 4. 综合改进建议

### A. SKILL.md 瘦身（学 Gog）

当前 twinbox SKILL.md 130 行，大量篇幅用于防"空转"。建议：

- Turn contract 的反复强调可以精简为一条：`## Rule: Run command, then answer. Never end with only file reads.`
- "Wrong pattern" 举例可以移到 `references/failure-modes.md`
- 目标：SKILL.md < 80 行

### B. Hook 自动激活（学 Self-Improving）

当前 twinbox 完全依赖用户主动问。建议：

- `UserPromptSubmit` hook：检查队列新鲜度，过期则注入 "队列数据已过期 X 小时" 提醒
- `PostToolUse` hook：twinbox 命令返回 exit code 2-5 时注入诊断建议
- 这解决了 skill 最大的落地问题——用户不记得/不知道可以问什么

### C. Registry Metadata 完善（学 Gog）

当前缺失：

```json
{
  "bins": ["twinbox", "twinbox-orchestrate"],
  "install": {
    "command": "bash scripts/install_openclaw_twinbox_init.sh",
    "description": "Initialize twinbox roots and verify preflight"
  }
}
```

### D. Per-Exit-Code Recovery Table（学 Self-Improving 的结构化错误处理）

当前 exit code 0-5 只在 `cli-quick-ref.md` 文档中。建议在 SKILL.md 中内联：

```markdown
| Exit | 含义 | 自动恢复 |
|------|------|----------|
| 0 | 成功 | — |
| 2 | 缺 env | 列出缺失变量，提示设置 |
| 3 | IMAP 网络失败 | 检查 IMAP_HOST/PORT，提示网络 |
| 4 | IMAP 认证失败 | 提示检查 IMAP_LOGIN/PASS |
| 5 | 内部错误 | 检查 himalaya/Python 依赖 |
```

### E. Cron 架构显式化（学 Proactive Agent）

当前 bridge poller 是 isolated agentTurn 模式但没有显式声明。建议：

- 在 SKILL.md metadata 中区分 `systemEvent` 型调度（需要用户交互的通知）和 `isolated` 型调度（后台 refresh）
- 现有三个 schedule 都是 isolated 型，文档应明确标注

### F. 多 track 合并

当前三份 SKILL.md（`.claude/skills/`, `.agents/skills/`, 根 `SKILL.md`）同步维护成本高。建议：

- 根 `SKILL.md` 作为唯一 source of truth
- `.claude/skills/twinbox/SKILL.md` 和 `.agents/skills/twinbox/SKILL.md` 改为 symlink 或单行 include

---

## 5. 三个案例的通用模式总结

| 模式 | Gog | Self-Improving | Proactive |
|---|---|---|---|
| SKILL.md 极简 | ✅ 1.7KB | ❌ 19KB | ❌ 20KB |
| 独立 reference 文件 | ❌ | ✅ 3 个 | ✅ 2 个 |
| Hook 集成 | ❌ | ✅ 2 种 | ❌（用 cron） |
| 磁盘状态机 | ❌ | ✅ .learnings/ | ✅ SESSION-STATE |
| Cron/调度 | ❌ | ❌ | ✅ 2 种模式 |
| Registry bins 声明 | ✅ | ❌ | ❌ |
| 安装脚本 | ✅ brew | ✅ clawdhub install | ✅ cp assets |
| 安全审计 | ❌ | ❌ | ✅ scripts/ |
| 多 agent 支持 | ❌ | ✅ 4 种 | ❌ |

**核心结论**：
- CLI wrapper skill 应该学 Gog 的极简（命令自解释，SKILL.md 只做路由）
- 伺服型 skill 应该学 Self-Improving 的 hook 触发 + 结构化日志
- 架构型 skill 应该学 Proactive Agent 的 WAL + cron 分层
- Twinbox 是 CLI wrapper + 伺服的混合体，需要两种模式的优点
