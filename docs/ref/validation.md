# Validation Artifact Contract

日期：2026-03-20  
状态：current-state contract + convergence target

## 目的

本文档定义 twinbox 当前实现里真正可依赖的 phase artifact contract，并明确：

- 哪些文件是跨 phase 的 authoritative state
- 哪些文件只是 phase 内部 handoff
- 哪些文件只是 report / diagram / debug trace
- `attention-budget.yaml` 在当前仓库中的真实地位

这份文档优先描述当前仓库已经实现并可测试的事实，不把“目标设计”伪装成“现状”。

## 结论

当前仓库的 authoritative contract 不是 `attention-budget.yaml`。

当前真实的阶段依赖由以下两类工件构成：

1. phase-specific structured state
2. loading -> thinking 的 phase-local `context-pack.json`

`attention-budget.yaml` 仍然保留为目标收敛方向，但在当前实现中它还不是 authoritative runtime contract，也不是任何脚本的真实输入依赖。

## 工件分类

### 1. Cross-Phase Authoritative State

定义：

- 后续 phase 可以直接依赖
- 缺失会阻断后续 phase，或需要 fallback 重建
- 必须位于 `runtime/`
- 应优先被未来的 contract test 覆盖

### 2. Phase-Local Handoff State

定义：

- 只用于同一 phase 的 `loading -> thinking`
- 不是长期稳定的跨 phase 契约
- 可以在后续 Python core 迁移时调整内部结构

### 3. Derived View / Report Artifact

定义：

- 面向人阅读
- 不应作为运行前提
- 文档格式可以迭代

### 4. Debug / Trace Artifact

定义：

- 用于追查 LLM 返回或并行子任务结果
- 不是后续 phase 的 schema 承诺

## 当前 authoritative artifact matrix

| Phase | Cross-phase authoritative state | Phase-local handoff | Derived view / report | Debug / trace |
|------|----------------------------------|---------------------|-----------------------|---------------|
| Phase 1 | `runtime/context/phase1-context.json`, `runtime/validation/phase-1/intent-classification.json` | 无额外 handoff；`phase1-context.json` 同时承担 loading 输出与后续输入 | `runtime/validation/phase-1/mailbox-census.json`, `runtime/validation/phase-1/intent-distribution.yaml`, `runtime/validation/phase-1/contact-distribution.json`, `docs/validation/phase-1-report.md`, diagrams | `runtime/context/raw/*`, `runtime/validation/phase-1/intent-report.md` |
| Phase 2 | `runtime/validation/phase-2/persona-hypotheses.yaml`, `runtime/validation/phase-2/business-hypotheses.yaml` | `runtime/validation/phase-2/context-pack.json` | `docs/validation/phase-2-report.md`, `docs/validation/diagrams/phase-2-relationship-map.mmd` | `runtime/validation/phase-2/llm-response.json` |
| Phase 3 | `runtime/validation/phase-3/lifecycle-model.yaml`, `runtime/validation/phase-3/thread-stage-samples.json` | `runtime/validation/phase-3/context-pack.json` | `docs/validation/phase-3-report.md`, `docs/validation/diagrams/phase-3-lifecycle-overview.mmd`, `docs/validation/diagrams/phase-3-thread-state-machine.mmd` | `runtime/validation/phase-3/llm-response.json` |
| Phase 4 | `runtime/validation/phase-4/daily-urgent.yaml`, `runtime/validation/phase-4/pending-replies.yaml`, `runtime/validation/phase-4/sla-risks.yaml`, `runtime/validation/phase-4/weekly-brief.md` | `runtime/validation/phase-4/context-pack.json` | `docs/validation/phase-4-report.md` | `runtime/validation/phase-4/llm-response.json`, `runtime/validation/phase-4/*-raw.json` |

## 为什么 Phase 1 的 contract 这样定义

`Phase 2/3` 当前真正硬依赖的是：

- `runtime/context/phase1-context.json`
- `runtime/validation/phase-1/intent-classification.json`

而不是：

- `runtime/validation/phase-1/attention-budget.yaml`

`mailbox-census.json`、`intent-distribution.yaml`、`contact-distribution.json` 当前更接近 derived state view：

- 如果它们存在，`phase2_loading.sh` / `phase3_loading.sh` 会直接读取
- 如果它们不存在，脚本仍可从 `phase1-context.json` + `intent-classification.json` 派生回兼容视图

因此在当前实现里，Phase 1 的最小 authoritative state 应定义为：

1. 原始 mailbox snapshot: `runtime/context/phase1-context.json`
2. intent inference result: `runtime/validation/phase-1/intent-classification.json`

## 关于 `attention-budget.yaml`

### 当前状态

当前仓库中：

- 规范文档多次把 `attention-budget.yaml` 描述成阶段主线契约
- 但脚本实现里还没有任何 phase 真正读写它
- `rg` 到的引用全部在文档层，而非可执行路径

因此，`attention-budget.yaml` 当前只能被定义为：

- target contract
- not-yet-authoritative
- 不能作为“当前仓库已具备该依赖”的表述依据

### 目标状态

`attention-budget.yaml` 仍然值得保留为未来收敛方向，因为它回答的是一个真实问题：

- 每个 phase 如何把“应该继续深读的线程集合”交给下一 phase

但它只有在以下条件满足后，才能升级为 authoritative contract：

1. Phase 1-4 都真实产出该文件
2. Phase 2-5 的 loading 真实读取上一阶段的 budget，而不是只靠其他文件存在
3. budget schema 被单独定义并稳定
4. 至少有一组 contract tests 覆盖 `focus / deprioritize / skip`

在此之前，所有文档都应把它写成：

- convergence target
- planned cross-phase contract

而不是 current implementation fact。

## State vs Report Ownership Rules

### 规则 1：`runtime/` 才能承载运行时真相

只有 `runtime/` 下的结构化工件可以成为 authoritative state。

### 规则 2：`docs/validation/` 默认只承载视图

`docs/validation/` 下的 markdown 和 mermaid：

- 用于解释、审阅、对外展示
- 不得作为后续 phase 的必需输入

当前唯一保留的实例级人工补充说明是：

- `runtime/context/instance-calibration-notes.md`
- 它属于 instance-local human context input，而不是 `docs/validation/` report artifact
- `docs/validation/` 现在应完全收敛为视图层，不再承担运行时输入

### 规则 3：`llm-response.json` 不是长期契约

它是 debug trace，不是对下游暴露的稳定 schema。

下游如需读取，应读取 phase 的 normalized output，而不是原始 LLM 回包。

### 规则 4：phase-local `context-pack.json` 不是跨 phase API

`context-pack.json` 的拥有者是当前 phase 的 loading/thinking 边界。

它可以被重构，但不能默认被其他 phase 直接依赖。

### 规则 5：raw capture 是可重放素材，不是业务 contract

如：

- `runtime/context/raw/envelopes-merged.json`
- `runtime/context/raw/sample-bodies.json`
- `runtime/validation/phase-4/*-raw.json`

这些文件可用于 debug、cache、重放，但不是业务语义层的最终 contract。

## 对文档的落地要求

从现在开始，文档描述 phase outputs 时应区分三层：

1. 当前 authoritative state
2. 当前派生视图
3. 未来目标 contract

避免再把“未来的 `attention-budget` 主线”写成“当前已经实现的阶段依赖”。

## 后续迁移顺序

基于当前 contract，推荐后续顺序为：

1. 先围绕这里定义的 authoritative state 建 contract tests
2. 再把这些 state 的 load/save 迁到 Python core
3. 最后再把 `attention-budget.yaml` 从 target contract 提升为真实 runtime contract

## 相关文档

- [Implementation Core Refactor Plan](../core-refactor.md)
- [Progressive Validation Framework](../archive/validation-framework.md)
- [Thread State Runtime](./runtime.md)
