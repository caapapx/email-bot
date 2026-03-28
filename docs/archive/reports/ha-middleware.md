# 高可用 / 持久化 / 中间件优化机会清单（批判性版）

## 背景与目标

本文件聚焦一个现实问题：在不强行重构的前提下，挖掘 twinbox 当前架构中可以降低人工负担、提升高可用与响应速度、并增强架构统一性和开源传播性的改进点。

评估范围基于当前主干实现与文档契约：

- `docs/ref/architecture.md`
- 仓库根 `ROADMAP.md`（历史计划已合并）
- `docs/ref/runtime.md`
- `docs/ref/validation.md`
- `docs/ref/orchestration.md`
- `README.md` / `README.zh.md`
- `src/twinbox_core/task_cli.py`
- `scripts/twinbox_orchestrate.sh` / `scripts/run_pipeline.sh` / `scripts/twinbox` / `scripts/phase4_gastown.sh`

## 评估方法（避免“强行分析”）

排序标准采用四个维度：

1. 是否直接减少人工操作与人工排障成本
2. 是否显著改善可用性（失败退化、重试、并发安全）与响应速度（预计算、缓存命中）
3. 是否提升跨层统一性（single source of truth、contract 一致）
4. 改造半径与风险（优先低风险、小步可落地）

优先级定义：

- `P0`：小步可做，1-2 周可见收益
- `P1`：中等改造，引入中间件或运行部件后收益明显
- `P2`：偏架构演进，需在 P0/P1 稳定后推进

---

## 优化机会（11 项）

### 1) P0：将 `task_cli` 的写操作与只读操作做硬门禁

- **当前证据**
  - `src/twinbox_core/task_cli.py` 中 `context import-material` / `upsert-fact` / `profile-set` 直接写本地状态。
  - 架构文档强调 phase-gated automation 与 early phase read-only-first。
- **问题本质**
  - “文档只读、命令可写”会制造审计歧义和误操作风险。
- **建议方案（优先）**
  - 增加统一写门禁：`--allow-write` + `TWINBOX_PHASE_GATE` 校验（默认拒绝写）。
  - 在 CLI 层实现 guard decorator，统一拦截所有 state mutation。
- **替代方案**
  - 拆分为 `twinbox-ro` 与 `twinbox-admin` 两个入口。
- **收益**
  - 可用性与安全边界可解释；减少人工复核负担；对开源用户上手更清晰。
- **风险与反例**
  - 本地开发体验会变“更啰嗦”。
  - 如果当前仅单人本地实验且无自动触发，不做也合理。

### 2) P0：建立稳定对象快照层（QueueView / ThreadCard / DigestView）

- **当前证据**
  - `task_cli.py` 直接读多个 phase 产物文件。
  - `core-refactor-plan.md` 已提出 task-facing object contract 的收敛方向。
- **问题本质**
  - 外部消费绑定底层 artifact 文件名，contract 漂移会被放大。
- **建议方案（优先）**
  - 增加 `runtime/state/views/*.json` 投影层，统一 schema（`pydantic` / `jsonschema`）。
  - CLI 与未来 API 仅消费 views，不直接拼接 phase 文件。
- **替代方案**
  - 先只在 CLI 内做 adapter，不落盘。
- **收益**
  - 响应更快（读快照）；接口更稳；复用性更高（skill、listener、外部 SDK）。
- **风险与反例**
  - 多一层可能形成“第二真相源”。
  - 若 phase schema 已稳定且外部消费者极少，不做也合理。

### 3) P0：把“stale fallback + background refresh”从文档落地成调度

- **当前证据**
  - 架构和 runtime 规范提到 stale 可读与后台刷新。
  - 实际运行仍以手工触发脚本为主。
- **问题本质**
  - 依赖人工重跑导致响应时间抖动，SLA 难保证。
- **建议方案（优先）**
  - 第一阶段：`cron`/`systemd timer` 定时跑 phase 关键路径。
  - 第二阶段：进程内 `APScheduler`，支持补偿执行与失败重排。
- **替代方案**
  - 只在 CI 定时评测，不做生产预计算。
- **收益**
  - 可用性提升（自动补算）；响应速度提升（预计算命中）；人工催跑减少。
- **风险与反例**
  - 并发触发可能与手工运行冲突。
  - 用户量极低且人工触发足够时，不做也合理。

### 4) P0：引入幂等锁与运行租约，防并发踩踏

- **当前证据**
  - Phase 4 存在 fan-out/merge 并行路径（`scripts/phase4_gastown.sh` 等）。
  - state root 是共享目录，多 worker 存在写冲突风险。
- **问题本质**
  - 并发写同一目录易造成部分覆盖与产物不一致，增加排障成本。
- **建议方案（优先）**
  - 单机先用 `flock`/`filelock` + `run_id` 租约文件。
  - 将“同一 phase 同一 state_root 不可并写”写入 contract。
- **替代方案**
  - 用 SQLite 锁表。
- **收益**
  - 提升运行稳定性；降低偶发错误与不可复现问题。
- **风险与反例**
  - 锁管理不当会造成“假死”。
  - 完全串行、无并发 worker 的部署下不做也合理。

### 5) P0：把 artifact 分类规则变成自动 contract test

- **当前证据**
  - `validation-artifact-contract.md` 已区分 authoritative/derived/debug。
  - 现阶段主要靠文档约束与人工遵守。
- **问题本质**
  - 没有自动检查，后续脚本变更容易“悄悄破坏”统一性。
- **建议方案（优先）**
  - 增加 contract test：校验路径、最小字段、类型与 ownership。
  - 在 CI 作为硬门禁。
- **替代方案**
  - pre-commit 轻校验（先软门禁）。
- **收益**
  - 降低回归；强化统一性；开源用户更信任契约稳定性。
- **风险与反例**
  - 快速探索期会感觉“测试噪音”高。
  - 若 schema 尚未收敛，不做也合理。

### 6) P1：为 LLM 调用加入缓存与熔断中间件

- **当前证据**
  - 已有 retry/repair，但缺少跨 run 的缓存和 provider 退化策略。
- **问题本质**
  - 重复请求耗时、成本高；上游波动时可用性弱。
- **建议方案（优先）**
  - `diskcache`（单机）或 `Redis`（多实例）做语义缓存。
  - `tenacity` + 熔断策略做失败降级。
- **替代方案**
  - 只加本地文件缓存。
- **收益**
  - 响应速度提升；成本下降；高峰期稳定性提升。
- **风险与反例**
  - 缓存污染会放大旧结论。
  - 数据变化快、命中率低场景不做也合理。

### 7) P1：把 context ingestion 升级为 reader 插件管线

- **当前证据**
  - 架构中建议 pluggable readers；CLI 侧仍偏文件导入。
- **问题本质**
  - 用户材料解析能力不足，依然需要大量手工摘要和搬运。
- **建议方案（优先）**
  - 插件接口（`pluggy` 或 Python entry points）支持 `pdf/docx/xlsx/ocr/mcp` readers。
  - 失败降级到 manifest + user summary，不阻塞主流程。
- **替代方案**
  - 先支持最常见两类（例如 markdown/csv）。
- **收益**
  - 直接降低人工输入负担；增强扩展能力与社区贡献入口。
- **风险与反例**
  - 插件质量参差，依赖复杂度上升。
  - 用户材料类型高度单一时不做也合理。

### 8) P1：审计事件从 JSONL 升级为可查询存储

- **当前证据**
  - runtime 规范已定义审计事件；当前主要是文件级落地。
- **问题本质**
  - 仅靠文本文件难做追溯、统计和故障复盘。
- **建议方案（优先）**
  - 保留 JSONL 作为日志源，同时 ingest 到 SQLite（后续可接 litestream）。
- **替代方案**
  - 直接接 OpenSearch（更重）。
- **收益**
  - 提升可观测性与复盘效率，支持更好的开源演示与排障。
- **风险与反例**
  - 双写路径会增加复杂度。
  - 小规模单机且极少复盘场景，不做也合理。

### 9) P1：提供只读 HTTP/SDK 表面，替代“直接读文件树”

- **当前证据**
  - 对外消费主要依赖 CLI + artifact 文件。
- **问题本质**
  - 外部集成门槛高，不利于开源传播与生态复用。
- **建议方案（优先）**
  - `FastAPI` 只读 endpoints：`/queue`、`/thread/{id}`、`/digest/*`。
  - 与 task-facing object contract 复用，避免重复定义。
- **替代方案**
  - 先发 Python SDK，不先发 HTTP。
- **收益**
  - 传播性提升；二次开发更快；架构接口更统一。
- **风险与反例**
  - API 版本承诺增加维护负担。
  - 若定位仍是纯本地 CLI 工具，不做也合理。

### 10) P2：把 Phase 4 fan-out 抽象到任务队列执行器

- **当前证据**
  - 已有 Gastown 适配与并行子任务语义。
  - orchestration contract 强调“adapter 可替换”。
- **问题本质**
  - 过度依赖脚本并发不利于统一重试/超时/可观测。
- **建议方案（优先）**
  - 引入 `RQ`/`Arq`/`Celery` 之一承载 phase4 子任务，保留 Gastown adapter。
- **替代方案**
  - 持续 shell 并发 + watchdog。
- **收益**
  - 高可用（自动重试、超时治理）和响应稳定性提升。
- **风险与反例**
  - 引入 broker/worker 运维成本。
  - 并发规模低时不做也合理。

### 11) P2：建立“开源发行最小包 + 实例数据隔离”流水线

- **当前证据**
  - README 已提示 `docs/validation/` 可能带实例特征数据。
- **问题本质**
  - 发布边界不自动化，存在泄露与传播阻力。
- **建议方案（优先）**
  - 发布前 sanitizer 流水线：路径扫描、敏感模式检查、样例替换。
  - 提供 public profile + public fixtures。
- **替代方案**
  - 手工清理 checklist。
- **收益**
  - 开源传播与合规可信度显著提升。
- **风险与反例**
  - 需要维护发布链路。
  - 若短期不公开发布，不做也合理。

---

## 分层路线图

### 现在就能做（小步快跑）

- 1) CLI 写门禁
- 2) 稳定对象快照层（先 QueueView）
- 3) 定时预计算与 stale fallback
- 4) 并发锁与租约
- 5) artifact contract tests

### 需要中等改造（建议近期排期）

- 6) LLM 缓存 + 熔断
- 7) ingestion reader 插件化
- 8) 审计可查询存储
- 9) 只读 API/SDK

### 需要架构演进（在前两层稳定后）

- 10) 队列化执行器（可替换 Gastown）
- 11) 开源发行自动化隔离链路

---

## 建议的首个执行批次（4 周）

目标：先拿到“可感知收益”，避免先上重中间件。

- **Week 1**
  - 完成 CLI 写门禁（机会 1）
  - 增加并发锁/租约（机会 4）
- **Week 2**
  - 实现 QueueView 快照层 v1（机会 2）
  - 打通最小 contract tests（机会 5）
- **Week 3**
  - 上线定时预计算与 stale fallback（机会 3）
  - 观察命中率与失败恢复时延
- **Week 4**
  - 验证是否进入 P1（优先机会 6：LLM cache）
  - 根据数据决定是否继续扩展到 7/8/9

验收建议：

- 手工触发次数下降（每周）
- phase 失败后的恢复时间下降（P95）
- queue/read 命令平均响应时间下降（P50/P95）
- contract 回归导致的问题数下降

---

## 明确不建议“现在就做”的事项

以下事项收益存在，但不建议当前立即推进：

- 先做“全栈微服务化”再治理可靠性（改造成本过高，收益滞后）
- 在没有稳定 task-facing schema 前承诺公开 HTTP API v1（后续反复破坏兼容）
- 未建立 artifact contract tests 就引入大量插件（会扩大不一致）

---

## 结论

twinbox 当前最值得做的不是“再加一个大系统”，而是先把现有 contract 和运行边界落地成可执行机制。优先完成 P0 五项后，再引入缓存、插件、审计存储和 API 层，能在风险可控前提下同时提升：

- 高可用（失败退化、自动恢复、并发安全）
- 响应速度（预计算、缓存、轻量对象层）
- 架构统一性（contract-first、single source of truth）
- 开源传播性（更稳接口、更低接入门槛）
