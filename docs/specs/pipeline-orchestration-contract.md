# Pipeline Orchestration Contract

日期：2026-03-20  
项目：twinbox

## 目的

这份 contract 收口的是“谁负责描述 pipeline 编排语义”。

从现在开始，编排语义的权威来源应是共享 CLI / Python contract，而不是：

- 某个 shell wrapper 里的隐式顺序
- 某份 Gastown formula 里的说明性文字
- 文档里对 phase 依赖的口头描述

目标边界：

```text
skill / local operator / gastown
  -> scripts/twinbox_orchestrate.sh
      -> twinbox_core.orchestration
          -> phase shell entrypoints
              -> twinbox_core implementation modules
```

这意味着 `gastown` 是 adapter，不是 pipeline 语义真相源。

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
- `gastown adapter`：对应 formula 和子任务映射

这些信息由 `twinbox_core.orchestration` 对外导出，可用：

```bash
bash scripts/twinbox_orchestrate.sh contract
bash scripts/twinbox_orchestrate.sh contract --format json
```

## Phase Surface

| Phase | 依赖 | Loading | Thinking | 关键产物 |
|------|------|---------|----------|----------|
| 1 | 无 | `scripts/phase1_loading.sh` | `scripts/phase1_thinking.sh` | `phase1-context.json`, `intent-classification.json` |
| 2 | 1 | `scripts/phase2_loading.sh` | `scripts/phase2_thinking.sh` | `context-pack.json`, `persona-hypotheses.yaml`, `business-hypotheses.yaml` |
| 3 | 1 + 2 | `scripts/phase3_loading.sh` | `scripts/phase3_thinking.sh` | `context-pack.json`, `lifecycle-model.yaml`, `thread-stage-samples.json` |
| 4 | 1 + 2 + 3 | `scripts/phase4_loading.sh` | `scripts/phase4_thinking.sh` 或 `scripts/phase4_thinking_parallel.sh` | `context-pack.json`, `daily-urgent.yaml`, `pending-replies.yaml`, `sla-risks.yaml`, `weekly-brief.md` |

## Gastown Adapter 约束

Gastown 侧保留的职责：

- worker 分发
- convoy / workflow 编排
- health monitoring
- merge queue

Gastown 不应重新定义：

- phase 依赖顺序
- 本地 fallback 的语义
- phase 默认输入输出
- Phase 4 是否存在 serial / parallel 两种 thinking surface

因此 formula 文档应被理解为“如何在 Gastown 内执行这份 contract”，而不是“重新声明一套新的 pipeline”。

## 面向 Skill 化的解耦判断

如果后续把 twinbox 改造成通过 CLI 执行的 skill，这层 contract 已经提供了最关键的稳定边界：

- skill 不需要理解 `.beads/formulas/*.toml`
- skill 只需要调用 `scripts/twinbox_orchestrate.sh run ...`
- skill 可以先读 `contract --format json` 再决定跑整条 pipeline、单 phase，或只跑 Phase 4 的 serial fallback

这让后续替换编排后端成为可能：

- 现在：CLI -> shell -> Python core，同时可由 Gastown 调度
- 以后：CLI -> skill runtime -> Python core，Gastown 可选保留或移除

## 最小验证要求

每次修改 orchestration contract 时，至少验证：

```bash
bash scripts/twinbox_orchestrate.sh contract --format json
bash scripts/twinbox_orchestrate.sh run --dry-run
bash scripts/run_pipeline.sh --dry-run
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
