# Pipeline Orchestration Contract

日期：2026-03-20
项目：twinbox

## 目的

这份 contract 收口的是"谁负责描述 pipeline 编排语义"。

从现在开始，编排语义的权威来源应是共享 CLI / Python contract，而不是：

- 某个 shell wrapper 里的隐式顺序
- 文档里对 phase 依赖的口头描述

目标边界：

```text
skill / local operator
  -> scripts/twinbox_orchestrate.sh
      -> twinbox_core.orchestration
          -> phase shell entrypoints
              -> twinbox_core implementation modules
```

## 稳定入口

本仓库当前的稳定编排入口是：

- `scripts/twinbox_orchestrate.sh`
- `python -m twinbox_core.orchestration`
- 安装后可选入口：`twinbox-orchestrate`

兼容入口：

- `scripts/run_pipeline.sh`

说明：

- `run_pipeline.sh` 仍可继续调用，但它只是对共享 orchestration CLI 的兼容包装
- 后续如果改造成 skill，经由 CLI 驱动整条流水线时，应直接消费 `scripts/twinbox_orchestrate.sh`

## Contract 形状

每个 phase 必须显式声明以下信息：

- `depends_on`：依赖哪些上游 phase
- `required_artifacts`：运行前必须存在的结构化输入
- `produced_artifacts`：该 phase 负责产出的结构化输出
- `loading step`：确定性 I/O 和 context-pack 构建入口
- `thinking step`：默认推断入口
- `alternative steps`：例如 Phase 4 的 parallel thinking

这些信息由 `twinbox_core.orchestration` 对外导出，可用：

```bash
bash scripts/twinbox_orchestrate.sh contract
bash scripts/twinbox_orchestrate.sh contract --format json
```

宿主调度桥接使用同一个入口：

```bash
bash scripts/twinbox_orchestrate.sh schedule --job daytime-sync --format json
```

如果宿主侧拿到的是 OpenClaw `system-event` 文本，而不是已经解析好的作业 id，则先走 bridge dispatcher：

```bash
bash scripts/twinbox_orchestrate.sh bridge \
  --event-text '{"kind":"twinbox.schedule","job":"daytime-sync","event_source":"openclaw.system-event"}' \
  --format json
```

宿主机 service 更推荐直接挂这个 wrapper，而不是自己拼环境变量：

```bash
scripts/twinbox_openclaw_bridge.sh \
  --event-text '{"kind":"twinbox.schedule","job":"daytime-sync"}' \
  --format json
```

如果宿主机 service 需要自己去 Gateway 拉取 OpenClaw cron history，而不是被动接收事件文本，则走 poller：

```bash
scripts/twinbox_openclaw_bridge_poll.sh --format json
```

## Phase Surface

| Phase | 依赖 | Loading | Thinking | 关键产物 |
|------|------|---------|----------|----------|
| 1 | 无 | `scripts/phase1_loading.sh` | `scripts/phase1_thinking.sh` | `phase1-context.json`, `intent-classification.json` |
| 2 | 1 | `scripts/phase2_loading.sh` | `scripts/phase2_thinking.sh` | `context-pack.json`, `persona-hypotheses.yaml`, `business-hypotheses.yaml` |
| 3 | 1 + 2 | `scripts/phase3_loading.sh` | `scripts/phase3_thinking.sh` | `context-pack.json`, `lifecycle-model.yaml`, `thread-stage-samples.json` |
| 4 | 1 + 2 + 3 | `scripts/phase4_loading.sh` | `scripts/phase4_thinking.sh` 或 `scripts/phase4_thinking_parallel.sh` | `context-pack.json`, `daily-urgent.yaml`, `pending-replies.yaml`, `sla-risks.yaml`, `weekly-brief.md` |

## 面向 Skill 化的解耦判断

如果后续把 twinbox 改造成通过 CLI 执行的 skill，这层 contract 已经提供了最关键的稳定边界：

- skill 只需要调用 `scripts/twinbox_orchestrate.sh run ...`
- skill 可以先读 `contract --format json` 再决定跑整条 pipeline、单 phase，或只跑 Phase 4 的 serial fallback

当前路径：

- CLI -> shell -> Python core
- Host service / OpenClaw system-event -> `scripts/twinbox_openclaw_bridge.sh` -> `twinbox-orchestrate bridge --event-text ...` -> `twinbox-orchestrate schedule --job ...`
- User-level host poller -> `scripts/twinbox_openclaw_bridge_poll.sh` -> `twinbox-orchestrate bridge-poll` -> `gateway call cron.list` / `cron.runs` -> `bridge` -> `schedule`

根路径约束：

- `twinbox-orchestrate` 现在显式区分 `TWINBOX_CODE_ROOT` 与 `TWINBOX_STATE_ROOT`
- 兼容层仍接受 `TWINBOX_CANONICAL_ROOT`，但仅作为 legacy state-root alias
- 当前自托管默认仍允许两者相同；更通用的部署应把“代码 checkout”和“实例状态目录”分开

## Scheduled Jobs

为宿主机 service 和 OpenClaw `system-event` 增加的稳定作业面：

| Job | 目的 | 默认步骤 | 关键产物 |
|-----|------|----------|----------|
| `daytime-sync` | 小时级日内刷新与去重推送 | `phase1_loading` + `phase3_loading` + `phase4_loading` + `phase4_thinking` (serial) | `runtime/validation/phase-4/activity-pulse.json`、`daily-urgent.yaml`、`recipient_role` 信号 |
| `nightly-full` | 夜间全量校正 | Phase 1→4 全量 | Phase 1-4 全套产物 + 归档快照 |
| `friday-weekly` | 周五正式周报刷新 | Phase 1→4 全量 | Phase 1-4 全套产物 + 周报归档快照 |

调度侧约束：

- 所有 `schedule` 作业通过单一锁文件串行化：`runtime/tmp/schedule.lock`
- 每次非 dry-run 追加运行日志：`runtime/audit/schedule-runs.jsonl`
- 归档策略：默认归档 `nightly-full`、`friday-weekly`、以及所有失败运行到 `runtime/archive/phase-4/`
- `daytime-sync` 现在覆盖了数据拉取、recipient-role 解析、线程聚合与 Phase 4 打分（serial 模式），保证日内 `twinbox task todo` 可见最新的 [CC]/[GRP] 状态
- `daytime-sync` 成功后会刷新 `activity-pulse`，并更新去重状态，保证“同线程无新邮件且无状态变化则不重复推送”
- `daytime-sync` 成功且存在启用订阅时，会自动触发一次 push dispatcher（`openclaw sessions send`），并把分发结果写入 `schedule` 返回载荷与 `runtime/audit/schedule-runs.jsonl` 的 `push_dispatch` 字段
- `bridge` 当前支持两种事件文本：JSON `{"kind":"twinbox.schedule","job":"daytime-sync"}`，或紧凑文本 `twinbox.schedule:daytime-sync`
- `bridge-poll` 通过 OpenClaw Gateway 的 `cron.list` / `cron.runs` 公开 RPC 轮询新完成的 `systemEvent` 运行记录，并用 `jobId|runAtMs|ts` 做用户态宿主侧去重
- OpenClaw 平台当前没有“直接执行宿主命令”的现成入口；因此宿主适配层要么显式拿到事件文本走 `bridge`，要么定时轮询 `cron.runs` 走 `bridge-poll`
- 推荐安装方式是用户态 systemd：
  - `openclaw gateway install --force`
  - `bash scripts/install_openclaw_bridge_user_units.sh`
- 线程去重语义属于 `daytime-sync` / `activity-pulse`，不是 `bridge-poll` 本身：
  - `bridge-poll` 负责避免同一 `cron run` 被重复消费
  - `activity-pulse` 负责避免同一线程在 `fingerprint` 未变化时重复进入通知载荷

## 最小验证要求

每次修改 orchestration contract 时，至少验证：

```bash
bash scripts/twinbox_orchestrate.sh contract --format json
bash scripts/twinbox_orchestrate.sh run --dry-run
bash scripts/twinbox_orchestrate.sh bridge-poll --dry-run --format json
bash scripts/run_pipeline.sh --dry-run
pytest tests/
```
