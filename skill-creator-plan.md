# Twinbox Skill Package Plan

目标：把 Twinbox 的 skill 能力明确拆成两条产品线来建设和跟踪，而不是继续混在一份“泛 skill 说明”里。

- Track A：`Claude Code / Opencode` 本地代理 skill
- Track B：`OpenClaw` 全托管智能体 skill 包

这两条线共享同一套 Twinbox CLI / orchestration / runtime contract，但交付形态、接入方式、调度模型和验证方法不同，必须分开规划。

## 分类总览

### Track A：Claude Code / Opencode 本地代理 skill

- 当前承载位置：`.claude/skills/twinbox/`、`.claude/commands/`
- 当前状态：已经有基础骨架，可用，但还没完全收口
- 当前优势：
  - 已有 repo-local skill
  - 已有 mailbox / queue / digest / thread / action / review / context / status 命令模板
  - 本地代理可直接消费 `twinbox` 与 `twinbox-orchestrate`
- 主要缺口：
  - 缺统一的编排入口命令说明
  - references 仍偏薄
  - 根级 `SKILL.md` 与 `.claude/skills/twinbox/SKILL.md` 的职责边界还不够显眼

### Track B：OpenClaw 全托管 skill 包

- 当前承载位置：
  - 根级 `SKILL.md` 的 `metadata.openclaw`
  - 新增开发目录：`openclaw-skill/`
- 当前状态：以设计和契约为主，真正的托管接入工作基本还没开始
- 当前已具备的基础：
  - `twinbox mailbox preflight --json` 可作为 OpenClaw 登录预检接口
  - `twinbox-orchestrate` 是稳定编排入口
  - `SKILL.md` 已有 `requires.env`、`login`、`schedules` 元数据
  - `docs/ref/scheduling.md`、`docs/ref/runtime.md` 已描述未来调度 / listener / action 边界
- 当前未完成或未验证的重点：
  - OpenClaw 是否已经完整解析并执行 `metadata.openclaw.schedules`
  - OpenClaw 的心跳、cron、后台任务与 Twinbox phase 刷新如何对接
  - listener / action / review runtime 如何挂入 OpenClaw 托管环境
  - skill 包的最终交付形态是“直接挂 repo 根”还是“导出独立 package”
  - 部署、升级、回滚、观测、失败恢复还没有形成单独方案

## Track B 调研分析（2026-03-24）

### 从 `.claude` 已有 skill 得到的结论

- Track A 已经形成四层拆分：`.claude/skills/twinbox/SKILL.md` 负责触发和边界，`references/` 承载按需契约，`.claude/commands/` 承载高频入口，`evals/` 承载回归验证
- 这说明 repo 内已经验证过“薄 skill 入口 + 外置 reference + 单独验证面”这条组织方式，而不是把所有说明都塞进一个 `SKILL.md`
- Track B 不必复制 slash command 形态，但应继承这种分层思路：manifest、运行时契约、部署/验证、平台待验证项分别归位

### 基于根级 docs 的当前确定项

- 登录预检已经闭环：根级 `SKILL.md` 暴露 `metadata.openclaw.login.preflightCommand`，而 `docs/ref/cli.md` 已定义 `MailboxPreflightResult`、`login_stage`、退出码和只读边界
- 编排入口已经闭环：`docs/ref/orchestration.md` 与 `docs/ref/skill-authoring-playbook.md` 都把 `twinbox-orchestrate` 定义为稳定独立入口；Track B 不应再出现 `twinbox orchestrate ...`
- `docs/ref/scheduling.md` 已经给出 `metadata.openclaw.schedules` 的期望消费方式，但文档状态仍是 Draft，因此它目前是“设计契约”，不是“已跑通事实”
- `docs/ref/runtime.md` 明确 listener / action / review 示例只是 illustrative contract sketches；这意味着托管 runtime 目前仍是 contract-first，而不是已接通能力
- `docs/ref/skill-authoring-playbook.md` 表明目前真正具备 OpenClaw 友好状态外壳的只有 `twinbox mailbox preflight --json`；其他 queue / digest / action / review 仍主要返回对象投影

### 当前关键缺口

- 托管闭环目前只到 `manifest + preflight + orchestrate command`，还没有证据证明 OpenClaw 已真实消费 `schedules`
- `listener / action / review / heartbeat` 仍停留在规范层；如果现在把 Track B 写成“完整托管 runtime 已具备”，会越过当前实现状态
- 文档漂移仍会直接阻塞托管接入；`docs/ref/drift-inventory.md` 已把编排入口写法列为阻塞项，且 OpenClaw 相关指南仍需要持续校对旧示例
- Track B 目前没有对等于 `.claude/skills/twinbox/evals/` 的托管验证面，部署后的回归还主要靠人工 checklist

### 对 Track B 交付形态的判断

- `openclaw-skill/` 现阶段更适合作为开发工作区，而不是最终交付包本身
- 最终导出的 OpenClaw skill 应尽量薄，只保留宿主真正需要的 manifest、最小 reference、以及托管 smoke/验证资产
- 是否保留 repo 根挂载，还是从 `openclaw-skill/` 导出独立包，现在还不该拍板；应先用验证能力、回滚能力、最小暴露面来做判断，而不是只看目录整洁度

### Track B 验证阶梯

按当前仓库材料，OpenClaw 接入更像一个五级验证阶梯，而不是一步到位：

1. `Manifest parsing`
   - 平台能读取根级 `SKILL.md`
   - 能展示 `requires.env`、`primaryEnv`、`login`、`schedules`
2. `Login preflight`
   - 平台能收集 `runtimeRequiredEnv`
   - 能调用 `twinbox mailbox preflight --json`
   - 能把 `missing_env` / `actionable_hint` / `next_action` 透传给用户
3. `Manual command execution`
   - 平台宿主能执行 `twinbox-orchestrate run --phase 4`
   - 执行后 `queue` / `digest` 可消费最新 artifacts
4. `Schedule execution`
   - 平台能消费 `metadata.openclaw.schedules`
   - cron 能真实触发 `twinbox-orchestrate`
   - 失败后有最小可见性
5. `Hosted runtime extensions`
   - stale fallback、retry、audit、heartbeat 有明确责任边界
   - listener / action / review runtime 再决定由 Twinbox 还是 OpenClaw 承担

这个阶梯的意义是：前三级更接近“当前可证实能力”，后两级仍属于重点研究区。

### 当前文档漂移与研究风险

- `docs/guide/openclaw-compose.md`：Twinbox 快速路径命令已写为 `twinbox-orchestrate run --phase 1`（与 `orchestration.py` 一致）
- `docs/ref/cadence.md`：编排示例已改为 `twinbox-orchestrate run --phase 4` / 全量 `run`；`--background` 等仍属意图稿，不作执行事实
- `docs/ref/scheduling.md` 虽然已经改用 `twinbox-orchestrate`，但其状态仍是 Draft，且其中 retry / stale / 平台行为仍是期望模型，不是已验证行为
- 结论：Track B 研究应优先依赖 `SKILL.md`、`docs/ref/cli.md`、`docs/ref/orchestration.md`、`docs/ref/skill-authoring-playbook.md` 这些更接近实现面的文档；`cadence.md` 和部分 guide 文档应只作为补充线索

### Track B 最小 Smoke 矩阵

| 阶段 | 目标 | 触发命令 / 动作 | 预期证据 | 当前风险 |
|------|------|----------------|---------|---------|
| S1 | 读取 manifest | OpenClaw 载入 repo-root `SKILL.md` | 平台 UI 能看到 env/login/schedules 字段 | 平台是否真的消费全部 metadata 未验证 |
| S2 | 预检透传 | 调用 `twinbox mailbox preflight --json` | 能显示 `login_stage`、`missing_env`、`actionable_hint`、`next_action` | 目前只有 preflight 明确有统一状态外壳 |
| S3 | 手动 phase 刷新 | 运行 `twinbox-orchestrate run --phase 4` | `queue list --json` / `digest daily --json` 产物刷新 | 宿主 PATH、state root、env 注入方式待验证 |
| S4 | schedule 消费 | 等待/触发 `metadata.openclaw.schedules` | 至少一次定时执行记录 | OpenClaw 是否解析 schedules 未知 |
| S5 | stale 恢复 | 读取 stale 队列后观察恢复路径 | stale 被识别，且有明确刷新责任方 | retry / background refresh 仍只有规范，没有宿主证据 |
| S6 | 审计回流 | 查看任务执行日志或 audit 记录 | 至少能定位预检/调度执行结果 | 平台日志与 `runtime/audit/` 的边界未定 |

这个矩阵可以直接作为后续 Track B 验证清单的骨架。

### 建议的 Track B 研究推进顺序

1. 先验证 OpenClaw 是否真实消费 `preflightCommand`
2. 再验证 `metadata.openclaw.schedules` 是否会真实触发 `twinbox-orchestrate`
3. 然后决定 stale fallback、retry、audit、heartbeat 的平台责任边界
4. 最后再确定 skill 包是 repo-root 直挂，还是独立导出

### Track B 实测结果（2026-03-24，本机 OpenClaw 2026.3.23）

#### 1. 平台识别层：已能识别本地 managed skill

- 已把根级 `SKILL.md` 复制部署到本机 OpenClaw managed skills 目录：`~/.openclaw/skills/twinbox/SKILL.md`
- `openclaw skills list` 已将其识别为 `openclaw-managed` 来源，而不是仓库外部文档假设
- `openclaw skills info twinbox` 已读取出：
  - `Primary env: IMAP_LOGIN`
  - 缺失项：`IMAP_HOST`、`IMAP_PORT`、`IMAP_LOGIN`、`IMAP_PASS`、`SMTP_HOST`、`SMTP_PORT`、`SMTP_LOGIN`、`SMTP_PASS`

这说明当前 OpenClaw 至少真实消费了根级 manifest 中的：

- `name` / `description`
- `metadata.openclaw.requires.env`
- `metadata.openclaw.primaryEnv`

但这一步只证明“skill 被发现并被判定 eligibility”，还没有证明 `login.preflightCommand` 或 `schedules` 被平台自动执行。

#### 2. Twinbox 宿主基线：preflight 与 orchestrate 现已真实跑通

- 宿主机上执行：
  - `twinbox mailbox preflight --json`
  - `twinbox-orchestrate roots`
  - `twinbox-orchestrate contract --phase 4`
  - `twinbox-orchestrate run --phase 4`
- 当前结果已经闭环：
  - `mailbox preflight` 返回 `login_stage=mailbox-connected`、`status=warn`、`error_code=smtp_skipped_read_only`
  - `roots` / `contract` 均指向仓库根 `/home/caapap/fun/twinbox`
  - `run --phase 4` 已完整产出 `daily-urgent.yaml`、`pending-replies.yaml`、`sla-risks.yaml`、`weekly-brief.md`

这说明此前的 `twinbox-orchestrate` root 解析问题已经被修复，Track B 的本机稳定编排入口不再是 blocker。

#### 3. Gateway 宿主接入：已真实跑通 preflightCommand 对应命令

- 为了让 OpenClaw Gateway 真正消费 Twinbox runtime，本机实测补了三层宿主接入：
  - 通过 compose override 挂载 Twinbox 仓库到 Gateway `/opt/twinbox`
  - 把 Twinbox `.env` 注入到 Gateway / CLI 容器，并把 `/opt/twinbox/scripts` 加入 `PATH`
  - 在 Gateway 容器内补充 `python3-yaml`，使 `twinbox` 入口可运行
- 此外还修正了 `scripts/twinbox` 包装，使其在 repo-mounted runtime 中自动锚定 `PROJECT_ROOT`
- 在 Gateway 容器内真实执行：
  - `twinbox mailbox preflight --json`
  - `twinbox-orchestrate roots`
  - `twinbox-orchestrate contract --phase 4`
- 当前结果：
  - `preflight` 返回 `login_stage=mailbox-connected`
  - `state_root=/opt/twinbox`
  - `config_file=/opt/twinbox/runtime/himalaya/config.toml`
  - `twinbox-orchestrate` 在容器内也指向 `/opt/twinbox`

这说明 Track B 至少已经拿到了“OpenClaw Gateway 宿主环境中，Twinbox login preflight 命令可以真实执行”的证据，不再只是宿主机外部 smoke。

#### 4. 用户视角 prompt 实测：Ready 不等于进入 `main` agent prompt

- 补齐 Gateway env / runtime 后，`openclaw skills check` 已把 `twinbox` 从 `Missing requirements` 提升为 `Ready`
- `openclaw skills info twinbox` 现在会展示：
  - `Source: openclaw-managed`
  - `Primary env: IMAP_LOGIN`
  - 所有 `requires.env` 均已满足
- 但继续用真实 Gateway 路径执行：
  - `openclaw agent --agent main --json --message '请检查 twinbox 现在是否已经完成邮箱登录预检，并说明你依据的是平台当前真实状态。'`
- 返回的 `systemPromptReport.skills.entries` 仍只包含：
  - `healthcheck`
  - `node-connect`
  - `skill-creator`
  - `weather`
- 即使把根级 `SKILL.md` 从 metadata stub 提升为更完整的 skill 正文后重新部署，`main` agent 的 prompt 注入结果依然没有变化
- 额外实测 `--session-id` 与 `--to` 也仍然被路由回 `sessionKey=agent:main:main`

结论：从真实用户视角看，当前本机 OpenClaw 上 `Ready` 只证明平台识别并接受了 Twinbox skill；它并不自动等价于“`main` agent prompt 会注入这个 managed skill”。Track B 需要单独研究 OpenClaw 的 agent-skill 选择 / 注入策略。

- 后续继续追源码与实测后，已确认更具体的触发条件：
  - `openclaw agent --agent main ...` 这条 CLI 路径会把显式 agent 请求解析到固定 session key `agent:main:main`，不会因为 `--to` 自动新建独立 agent session
  - `main` agent 的 skills 是按 `sessionKey` 快照复用的；旧 snapshot 存在时，普通 turn 不会重建
  - `/new` 或 `/reset` 在当前 OpenClaw 2026.3.23 上只会为同一个 `sessionKey` 生成新的 `sessionId`，但 `performGatewaySessionReset()` 会保留原有 `skillsSnapshot`
  - 这意味着对 `agent:main:main` 而言，`/new` 并不足以让新增 managed skill 进入 prompt；文档层“start a new session”在这条 direct-agent 路径上并不等价于“刷新 skills snapshot”
- 实测 workaround：
  - 备份并手动删除 `config/agents/main/sessions/sessions.json` 中 `agent:main:main.skillsSnapshot`
  - 之后再次运行 `openclaw agent --agent main --json ...`
  - `systemPromptReport.skills.entries` 立即从 4 个 bundled skill 变成 5 个，其中新增 `twinbox`

因此当前更准确的结论不是“OpenClaw main agent 永远不会注入 managed skill”，而是“已存在的 `agent:main:main` session snapshot 会把 managed skill 注入冻结住；在本机版本上，`/new` 也不会清空这个 snapshot”。后续若要做平台级修复，应优先关注 session reset / skills watcher 对 `skillsSnapshot` 的失效策略。

#### 5. 平台调度层：当前 OpenClaw cron 是 agent/system-event 模型，不是 manifest command 模型

- 本机 OpenClaw `openclaw cron add --help` 当前暴露的是：
  - `--message`
  - `--system-event`
  - `--session`
  - `--agent`
  - `--announce`
- 没有直接对应 `metadata.openclaw.schedules[].command` 的 CLI 入口
- 即使 skill 已变成 `Ready`，`openclaw cron list --json` 仍然为空，没有任何 Twinbox schedule 被自动导入

这使得当前更稳妥的判断是：

- `metadata.openclaw.schedules` 仍然只被 Twinbox 文档当作设计契约使用
- 在本机 OpenClaw 2026.3.23 上，还没有拿到“manifest 里的 command schedule 被平台自动消费”的实测证据
- Track B 的 schedule 验证不该继续写成“已接通”，而应改成“需做平台导入映射验证”

## 共享基础层

以下内容是两条线共用的，不应重复建设：

- [SKILL.md](./SKILL.md)
- [docs/ref/cli.md](./docs/ref/cli.md)
- [docs/ref/orchestration.md](./docs/ref/orchestration.md)
- [docs/ref/runtime.md](./docs/ref/runtime.md)
- [docs/ref/scheduling.md](./docs/ref/scheduling.md)
- [docs/ref/skill-authoring-playbook.md](./docs/ref/skill-authoring-playbook.md)

## 推荐目录形态

```text
twinbox/
├── SKILL.md                         # OpenClaw manifest / shared metadata root
├── .claude/
│   ├── commands/                    # Claude Code / Opencode slash commands
│   └── skills/
│       └── twinbox/                 # Claude Code / Opencode local skill
├── openclaw-skill/                  # OpenClaw skill package development area
│   ├── README.md
│   └── DEPLOY.md
└── docs/
    ├── ref/
    └── guide/
```

## Todo List

### Shared Foundation

- [ ] 明确根级 `SKILL.md` 的定位
  - [ ] 继续作为 OpenClaw manifest / shared metadata root
  - [ ] 不再承担 Claude Code 的工作流正文
- [ ] 明确本地代理和 OpenClaw 共享的 source of truth
  - [ ] `twinbox` task-facing CLI
  - [ ] `twinbox-orchestrate`
  - [ ] runtime / scheduling / review safety contract

## Track B 决策清单（2026-03-24 Draft）

这部分只收口当前已经确认的实现边界与仍待拍板的分叉，避免把 Draft 契约误写成既成事实。

### 已确认的实现事实

- `twinbox-orchestrate run [--phase N]` 是当前唯一稳定编排入口；仓库内没有常驻 listener / worker / daemon 自动按天刷新
- 当前 phase 产物默认写入 `runtime/validation/phase-*` 并覆盖上次结果；没有内建 per-run 快照归档
- `twinbox queue list/show --json`、`twinbox digest daily --json`、`twinbox digest weekly --json` 已可作为 OpenClaw 读侧投影
- `twinbox context import-material / upsert-fact / profile-set` 会写本地 state，但当前不会自动触发局部重算
- `metadata.openclaw.schedules` 在本机 OpenClaw 2026.3.23 上仍缺少“自动导入并执行 command”的实测证据
- 当前实现没有内建 `flock` / 运行锁、append-only run log、`runtime/archive/` 快照归档、`notify-pack` 聚合命令

### 待拍板决策

#### D1. 定时触发宿主

- 备选 A：宿主 `systemd timer` / `cron` 直接执行 `twinbox-orchestrate`
- 备选 B：OpenClaw cron 只发 `message` / `system-event`，再由宿主适配层执行 twinbox
- 备选 C：双轨冗余，systemd 负责权威刷新，OpenClaw cron 只做提醒或健康探针

当前选择：

- 选择 B：由 OpenClaw cron 发事件，再由宿主适配层执行 twinbox

仍待细化：

- 事件类型是 `message` 还是 `system-event`
- 宿主适配层落在 Gateway 容器、宿主机，还是独立 sidecar
- 事件如何映射到唯一权威执行入口，避免 agent session 差异导致漂移

当前补充选择：

- OpenClaw cron 使用 `system-event`
- 宿主适配层落在宿主机 service，而不是 Gateway agent session

#### D2. 调度粒度

- 最小方案：工作日 `Phase 4` 快刷 + 夜间全量 `run`
- 扩展方案：额外保留 weekly refresh 与 `context_updated` 触发局部重算

当前选择：

- 先做“白天 `Phase 4` + 夜间全量”；weekly refresh 不单列为独立调度

仍待细化：

- 白天 `Phase 4` 的具体时间点与频率
- 周报是直接复用最近一次 nightly / weekday `Phase 4`，还是周五额外触发一次专门刷新

补充结论：

- 日内交互目标并不等价于当前 `weekly-brief` / `daily-urgent` 产物
- 仅靠现有 `Phase 4` 不足以支撑“今天发生了什么 / 待我回复 / 某事进展如何 / 每小时一次且不重复推送”
- 需要新增一个独立的日内投影视图，暂称 `daytime-slice` 或 `activity-pulse`

#### D3. 并发语义

- 备选 A：严格串行，所有 orchestrate 入口前加锁
- 备选 B：接受 `last-write-wins`，但每次运行写 `run_id` / `run_source`
- 备选 C：分 phase 细粒度锁

当前选择：

- 选择 A：所有 orchestrate 入口前统一加锁，先不接受并发覆盖

#### D4. 存档与审计深度

- 备选 A：仅保留最新工件 + append-only 运行日志
- 备选 B：每次 `Phase 4` 都复制到 `runtime/archive/phase-4/<timestamp>/`
- 备选 C：只对 nightly / weekly / 失败运行保留快照

当前选择：

- 选择 C：只对 nightly / weekly / 失败运行保留快照

仍待细化：

- 快照保留天数 / 数量上限
- 失败运行是否保留 loading 中间产物，还是只保留 run log + 失败 phase 输出目录

当前补充选择：

- 默认保留 7 天

#### D5. OpenClaw 推送契约

- 最小载荷：`generated_at`、`stale`、`urgent_top_k`、`pending_count`、一句 `summary`
- 扩展载荷：附 `sla_risks`、`recent_activity_window`、`why` / `evidence_refs`

当前选择：

- 先做最小载荷，不在 OpenClaw 侧重新分类，只读 twinbox 投影

仍待细化：

- `urgent_top_k` 的默认 K 值
- `summary` 是纯文本一句话，还是固定 schema 字段组合后由 OpenClaw 渲染

当前选择补充：

- `urgent_top_k = 3`
- 首版推送对象优先覆盖：
  - 今日新增或有推进的线程
  - 当前待我回复 / 待我拍板的线程
  - 指定线程的最新进展
- 推送频率：每小时一次
- 去重要求：同一线程 / 同一变动不应重复推送

#### D6. 失败恢复责任边界

- 备选 A：宿主调度层负责重试与告警，Twinbox 只返回退出码并保留旧产物
- 备选 B：OpenClaw 负责看到 stale 后提醒用户手动刷新
- 备选 C：双层都有，但需避免重复重试

推荐默认值：

- 先把责任放在宿主调度层；OpenClaw 先只做状态展示与提醒

当前补充选择：

- 自动重试 1 次；再次失败后告警，不自动补偿

#### D7. `context_updated` 产品语义

- 备选 A：写入事实/材料后立即同步重算受影响 phase
- 备选 B：先写事件标记，下一次调度或手动 refresh 再消费
- 备选 C：只提供显式 `twinbox context refresh`

当前选择：

- 选择 B：先写事件标记，下一次调度或手动 refresh 再消费

附加约束：

- `refresh` 不能只打印提示语，必须变成真实执行入口
- 方案目标应写成“刷新失败可见、可重试、可回退到最近成功结果”，而不是绝对成功承诺

## 新一轮优化计划（Draft）

### P0. 决策收口

- [x] 确认 D1 定时触发宿主：OpenClaw cron -> 宿主适配层执行
- [x] 确认 D2 调度粒度：白天 `Phase 4` + 夜间全量
- [x] 确认 D3 并发语义：统一串行加锁
- [x] 确认 D4 存档与审计深度：nightly / weekly / 失败运行保留快照
- [x] 确认 D5 OpenClaw 推送最小载荷
- [x] 确认 D7 `context_updated` 的即时性预期：事件标记 + 手动/定时消费
- [ ] 收口 D1/D2/D4/D5 的次级参数
- [ ] 明确“刷新失败可见、可重试、可回退”的 SLA 语义

### P1. 宿主调度最小闭环

- [x] 验证 OpenClaw authenticated `cron -> system-event` 最小链路可用
- [x] 产出调度 smoke checklist，并补进 `openclaw-skill/DEPLOY.md`
- [x] 设计 OpenClaw cron 事件 -> 宿主适配层 -> `twinbox-orchestrate` 的桥接路径
- [x] 明确 `TWINBOX_CODE_ROOT` / `TWINBOX_STATE_ROOT`、env 注入方式与工作目录
- [x] 增加宿主轮询器：通过 Gateway `cron.list` / `cron.runs` 消费新的 Twinbox `systemEvent` 运行记录
- [x] 落地宿主 wrapper 与用户态 systemd 样例：`scripts/twinbox_openclaw_bridge_poll.sh` + `openclaw-skill/twinbox-openclaw-bridge.*`
- [x] 安装并验证官方 `openclaw-gateway.service` + Twinbox 用户态 bridge timer 最小闭环
- [x] 验证非 dry-run `daytime-sync` 能由 bridge poller 实际触发并落审计
- [ ] 固定白天小时级刷新、周五额外 refresh 与夜间全量的执行窗口
- [ ] 统一权威执行入口为 `twinbox-orchestrate run --phase 4` / `run`
- [x] 明确 bridge 的事件协议，至少覆盖 `daytime-sync` / `nightly-full` / `friday-weekly`

当前补充结论：

- 2026-03-25 已实测通过：`openclaw health --url ... --token ...`、`openclaw system event --mode now`、`openclaw cron add/run`
- 当前 OpenClaw `cron add` 只支持 agent message 或 `system-event` payload，不支持直接执行宿主机命令
- 因此 `system-event -> 宿主机 service -> twinbox-orchestrate bridge --event-text ... -> schedule --job ...` 不是优化项，而是当前方案的必要桥接层
- Twinbox 已新增 `twinbox-orchestrate bridge` dispatcher，并固定了两种事件协议：JSON `{"kind":"twinbox.schedule","job":"daytime-sync"}` 与紧凑文本 `twinbox.schedule:daytime-sync`
- Twinbox 已新增宿主 wrapper `scripts/twinbox_openclaw_bridge.sh`，统一 `TWINBOX_CODE_ROOT`、`TWINBOX_STATE_ROOT` 与工作目录，方便 systemd/service 直接挂载
- Twinbox 已新增 `twinbox-orchestrate bridge-poll` 与宿主 wrapper `scripts/twinbox_openclaw_bridge_poll.sh`，通过 Gateway `cron.list` / `cron.runs` 轮询新完成的 `systemEvent` run，再转发到 `bridge`
- 2026-03-25 已 dry-run 验证：`bridge-poll` 能识别历史 Twinbox `systemEvent` run，并产出 `dispatched_count`
- 2026-03-25 已转为“官方 `openclaw gateway install --force` + Twinbox 用户态 bridge timer”的默认安装模型，不再以 `/etc/default/...` 为主路径
- 2026-03-25 已真实验证：临时 OpenClaw `systemEvent` cron job 可经由用户态 bridge poller 触发 `daytime-sync`，并写入 `openclaw-bridge-state.json`、`openclaw-bridge-polls.jsonl`、`schedule-runs.jsonl`
- 这次 smoke 也确认了当前去重语义：同一 `cron run` 不会重复消费；同一线程若 `fingerprint` 未变会被抑制，但 `urgent_top_k` 仍可能被其他尚未通知过的线程补位
- `preflightCommand` 仍未获得平台真实消费证据，不能因为 skill `Ready` 或 agent 能对话就视为已闭环

### P2. 完整性与审计最小闭环

- [x] 为每次 orchestrate 运行写 append-only 运行日志
- [x] 加入外层串行锁，并定义锁冲突时的返回码与日志
- [x] 对 nightly / weekly / 失败运行保留 `runtime/archive/phase-4/`
- [ ] 明确 stale 恢复责任边界与人工介入方式
- [ ] 定义 refresh 失败后的重试、降级和最近成功结果回退语义

当前补充结论：

- Twinbox 已显式区分 `TWINBOX_CODE_ROOT` 与 `TWINBOX_STATE_ROOT`
- `TWINBOX_CANONICAL_ROOT` 已降级为 legacy state-root alias，不再作为唯一标准入口
- `scripts/install_openclaw_twinbox_init.sh` 现已写入 `~/.config/twinbox/code-root`、`state-root` 与 legacy `canonical-root`
- mailbox preflight 现已显式输出 `code_root`、`state_root`、`env_file` 与 `env_sources`，便于区分 OpenClaw process env 与本地 `.env` fallback

### P3. OpenClaw 薄通知层

- [ ] 为“日内新增/进展/待回复”定义新的 `daytime-slice` 最小 payload
- [ ] 明确 OpenClaw 只负责路由与渲染，不重复做 phase 推理
- [ ] 定义失败/过期时的展示话术：`stale`、`last_success_at`、`next_action`
- [ ] 设计每小时一次且不重复推送的去重状态
- [ ] 把 Track B smoke 矩阵 S4-S6 改成可执行 checklist

### P3.1 日内投影层

- [ ] 明确 `daytime-slice` 与 `daily-urgent` / `pending-replies` / `weekly-brief` 的边界
- [ ] 定义日内视图的三个核心对象：
  - `new_or_changed_threads`
  - `waiting_on_me_now`
  - `thread_progress`
- [ ] 决定这层是复用现有 Phase 1 truth + 新 projection，还是引入增量 truth refresh
- [ ] 定义“不重复推送”的去重键与已推送游标

当前补充选择：

- “有推进”定义为：线程出现新邮件即视为推进，不要求先发生状态跃迁
- “不重复推送”定义为：同一线程在没有新邮件、也没有状态变化时不重复推送
- “看某个事情进展如何”同时支持：
  - 按 thread key / 邮件主题检索
  - 按项目名 / 资源名等业务关键词检索

实现含义：

- `daytime-slice` 需要显式维护至少一份去重状态，例如 `last_notified_message_id` / `last_notified_state`
- 关键词检索不能只靠 OpenClaw prompt，需要 twinbox 侧提供稳定映射或检索投影
- 首版按“轻量规则映射 + thread 索引”落地，不引入更重的语义检索层

当前阶段性结论：

- 已完成的最小闭环可以先接受“`Phase 1` truth + `activity-pulse` overlay 最近一次 `Phase 4` 队列”的实现
- 这能先覆盖“日内新增/进展/关键词查进展/不重复推送”的第一版，不要求同步重跑完整 `Phase 4`
- 该实现不应被误写为终态；`waiting_on_me_now` / `needs_attention` 的语义新鲜度仍部分依赖最近一次重型刷新

后续最值钱的下一刀（Deferred）：

- [ ] 把 `daytime-sync` 从“复用最近一次 `Phase 4` 结果做 overlay”推进到“增量 truth + 轻量 `needs-attention` 重算”
- [ ] 为这条演进单独补成功标准：
  - [ ] 白天小时级刷新不依赖前一晚 `Phase 4` 才能判断 `waiting_on_me_now`
  - [ ] 新邮件进入后，轻量重算能直接更新日内 attention 投影
  - [ ] 不引入完整周报链路或全量 LLM 成本

### P4. `context_updated` 增量闭环

- [ ] `context` 写命令产出事件标记或 run request
- [ ] `twinbox context refresh` 从提示语升级为真实执行入口
- [ ] 明确受影响对象范围：queue / digest / thread 投影
- [ ] 验证写入事实后不必手工跑整条 pipeline
- [ ] 把“已实现能力”和“未来能力”分开
  - [ ] 已实现：preflight / queue / thread inspect-explain / digest / action suggest-materialize / review list-show / context writes
  - [ ] 未实现：thread summarize / action apply / review approve-reject / long-running listener runtime

### Track A: Claude Code / Opencode

- [ ] 全链路评测（中文用户提问）：`.claude/skills/twinbox/evals/full-chain-2026-03-24.json` + `evals/run-full-chain-live.sh`（脚本与 JSON 内 `user_prompt_zh` 同步）
- [ ] 收口 `.claude/skills/twinbox/SKILL.md`
  - [ ] 写清楚它是本地代理 skill
  - [ ] 写清楚根级 `SKILL.md` 不是 Claude 主 skill
- [ ] 补齐 `.claude/commands/`
  - [ ] 新增 `twinbox-orchestrate.md`
  - [ ] 统一各命令之间的跳转提示
  - [ ] 把 stale / missing artifact 的恢复路径统一指向编排入口
- [ ] 补齐 `.claude/skills/twinbox/references/`
  - [ ] `orchestration.md`
  - [ ] `workflows.md`
  - [ ] 明确读路径 / 写路径 / 禁止自动发送
- [ ] 验证 Claude 命令层覆盖主路径
  - [ ] mailbox preflight
  - [ ] queue inspect
  - [ ] thread explain
  - [ ] digest daily / weekly
  - [ ] action materialize
  - [ ] review show
  - [ ] context write + refresh

### Track B: OpenClaw Managed Skill Package

- [x] 建立 `openclaw-skill/` 开发目录
- [x] 输出 OpenClaw skill 部署文档
- [ ] 单独梳理 OpenClaw 方案，而不是继续混在 Claude 方案里
  - [ ] skill 包边界
  - [ ] 登录字段收集
  - [ ] preflight 对接
  - [ ] schedule / cron 对接
  - [ ] heartbeat / background task 对接
  - [ ] listener / action / review runtime 对接
  - [ ] deployment / upgrade / rollback / observe
- [ ] 梳理 OpenClaw 当前确定项
  - [x] `metadata.openclaw.requires.env`
  - [x] `metadata.openclaw.login`
  - [x] `metadata.openclaw.schedules`
  - [x] `twinbox mailbox preflight --json`
  - [x] `twinbox-orchestrate run ...`
- [ ] 梳理 OpenClaw 当前待验证项
  - [ ] `schedules` 是否已被实际消费
  - [ ] cron 任务的触发模型
  - [ ] 失败重试 / stale fallback 的平台责任边界
  - [ ] 是否有平台级 heartbeat / worker / daemon 机制
  - [ ] 是否需要单独的 listener manager / action runner
  - [ ] skill 更新后的热加载或重部署流程
- [ ] 建立 Track B 能力分层表
  - [ ] 已实现：manifest / preflight / `twinbox-orchestrate`
  - [ ] 设计已定：login stages / schedule metadata / phase contract
  - [ ] 待验证：OpenClaw schedule consumption / retry / stale fallback / audit 回流
  - [ ] 未开始：listener runtime / action runner / hosted review flow
- [ ] 设计托管验证面
  - [x] Gateway 宿主内真实跑通 `twinbox mailbox preflight --json`
  - [ ] 平台自动消费 `preflightCommand` smoke
  - [ ] `schedules` 触发 smoke
  - [ ] stale / retry / audit 行为 smoke
  - [ ] 明确每个 smoke 的“成功证据”与“失败证据”
- [ ] 清理 OpenClaw 接入相关文档漂移
  - [ ] 清理仍引用 `twinbox orchestrate ...` 的旧示例
  - [ ] 明确 `docs/ref/cadence.md` 只作策略草案，不作托管事实来源
  - [ ] 对齐 `SKILL.md`、`openclaw-skill/`、`docs/guide/openclaw-compose.md` 的说法
- [ ] 建立 Track B source-of-truth 优先级
  - [ ] 第一优先级：`SKILL.md`、`docs/ref/cli.md`、`docs/ref/orchestration.md`
  - [ ] 第二优先级：`docs/ref/skill-authoring-playbook.md`、`openclaw-skill/DEPLOY.md`
  - [ ] 仅作草案参考：`docs/ref/scheduling.md`、`docs/ref/cadence.md`
- [ ] 评估是否需要统一 OpenClaw 消费协议
  - [ ] 当前只有 `mailbox preflight` 具备 `status / actionable_hint / next_action` 外壳
  - [ ] 队列 / digest / review 是否需要补统一 envelope
- [ ] 决定 OpenClaw skill 包交付形式
  - [ ] 直接使用 repo 根目录
  - [ ] 从 `openclaw-skill/` 导出独立包
  - [ ] 哪种方式更适合后续发布和升级
- [x] 修复 `twinbox-orchestrate` root 解析
  - [x] `roots` / `contract` 在仓库内执行时应指向 `/home/caapap/fun/twinbox`
  - [x] `run --phase 4` 不再错误引用上级目录 `scripts/`
- [ ] 为 OpenClaw skill 增补真实宿主接入前提
  - [x] 明确 Twinbox runtime 如何进入 Gateway 宿主环境
  - [ ] 评估是否需要 `metadata.openclaw.install`
  - [x] 评估是否需要把 repo-root manifest 导出为真正可注入的 OpenClaw skill 正文
  - [ ] 确认为何 `Ready` skill 仍不进入 `agent:main:main` prompt

## OpenClaw 专项问题清单

这些问题目前不应假装“已经定了”，应单独跟踪：

- [ ] OpenClaw 对 `SKILL.md` 中 login / env / schedule 元数据的展示与执行边界到底在哪一层
- [ ] OpenClaw 对 `metadata.openclaw.schedules` 的消费是否已跑通过
- [ ] schedule 是平台主动 cron 触发，还是由 Twinbox 自带心跳 / worker 接收后再执行
- [ ] 如果 Queue / Digest stale，后台补刷是 OpenClaw 负责任务调度，还是 Twinbox 自带 runtime 负责
- [ ] listener/event-driven 模式是否属于本仓库后续实现，还是由 OpenClaw 提供宿主能力
- [ ] action/review 的人工审批面是平台托管，还是 Twinbox 只提供 CLI / JSON contract
- [ ] 托管环境里的审计日志、失败通知、任务重试怎么回流
- [x] 当前 manifest-only `SKILL.md` 是否足以支撑用户视角 prompt 测试，还是需要单独的 OpenClaw skill 正文
  - 结论：仅 manifest stub 不足；已补成更完整 skill 正文，但 `main` agent prompt 仍未自动注入，说明问题还在平台选择策略层

## 完成标准

### Track A 完成标准

- [ ] 新人能一眼分清：
  - [ ] 根级 `SKILL.md` = OpenClaw manifest
  - [ ] `.claude/skills/twinbox/` = 本地代理 skill
  - [ ] `.claude/commands/` = 高频场景命令层
- [ ] Claude Code / Opencode 主路径可被完整覆盖

### Track B 完成标准

- [ ] `openclaw-skill/` 成为独立开发入口
- [ ] OpenClaw 部署文档单独存在，不再散落在 README / 零散 ref 里
- [ ] OpenClaw 的“已实现 / 已验证 / 待验证 / 未开始”边界清楚
- [ ] schedule / heartbeat / listener / action runtime 的平台职责被单独追踪
- [ ] OpenClaw 至少真实跑通一次 `preflightCommand` 与一次 schedule 触发
