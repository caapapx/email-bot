# Plan: Docs Directory Restructure

> Source: 2026-03-24 conversation, "docs 目录重构优化计划" review and refinement

## Architectural decisions

适用于所有阶段的稳定决策：

- **Single entry**: `docs/README.md` 是唯一文档入口；根目录 `README.md`、`README.zh.md`、`AGENTS.md`、`CLAUDE.md` 只保留高层导读，不再维护并行索引清单。
- **Taxonomy first**: 先定义目录职责，再迁移文件。目录职责如下：
  - `docs/architecture/`: 架构总览、系统分层、设计分章节
  - `docs/specs/`: 稳定协议、契约、对象模型、运行时边界
  - `docs/guides/`: 操作手册、接入说明、运维路径
  - `docs/roadmap/`: 进行中的方案、路线图、分阶段实施计划
  - `docs/archive/`: 历史方案、废弃设计、已失效迁移记录
  - `docs/reports/`: 评估、迁移记录、阶段分析报告
  - `docs/validation/`: 实例级验证工件；路径保持不变
- **Status labels**: 每份文档在页头显式标记 `active`、`reference` 或 `archive`，避免目录语义和文档语义脱钩。
- **Naming rules**:
  - phase 文档统一采用 `phase-<n>-<topic>.md`
  - 报告文档统一采用 `<subject>-report.md` 或 `<subject>-evaluation.md`
  - 计划文档统一采用 `<topic>-plan.md`
- **Direct migration**: 本次不保留旧路径占位文件；迁移依赖通过批量修正引用解决。
- **Split after target shape is fixed**: 大文档拆分依赖目标目录和命名规则，必须在 taxonomy 和 target path 确定后执行。
- **Relative links**: 文档间交叉引用统一使用相对路径；根入口可以使用相对仓库路径。
- **Validation safety**: `docs/validation/`、`runtime/validation/` 及脚本写入路径不变，不为文档整理由此引入运行时改动。

---

## Phase 0: Inventory And Taxonomy Baseline

**User stories**: 作为维护者，我需要在迁移前知道每份文档属于什么类型、哪些路径已经失真、哪些引用会受影响，这样后续迁移才不会返工。

### What to build

建立一份 old-to-new 映射与分类清单，而不是直接移动文件。该清单至少要覆盖：

- 当前 `docs/` 下所有 Markdown 的现存路径、目标路径、目标状态标签
- 已失效但仍被引用的路径
- 根入口和 docs 内部文档的受影响链接
- 需要拆分的长文档及预期子文档列表

### Acceptance criteria

- [ ] 形成完整的文档清单，覆盖 `docs/` 下全部 Markdown 文件
- [ ] 每份文档都有目标目录归属，而不是仅按当前目录继承
- [ ] 明确列出所有已失效引用，至少覆盖根入口文件和 `docs/specs/*.md`
- [ ] 输出 old-to-new 映射表，供后续迁移和回归扫描复用

---

## Phase 1: Single Entry And Governance Rules

**User stories**: 作为新维护者，我需要一个唯一入口和明确目录约定，这样不会再从多个相互漂移的入口理解仓库。

### What to build

新建或重写 `docs/README.md`，作为唯一文档入口，包含中英文导航、目录职责、状态标签定义、命名规则、阅读顺序和维护约束。同步收敛根入口文件的治理规则，使其不再将 `docs/plans/` 写成唯一计划目录，也不再维护平行的详细索引。

### Acceptance criteria

- [ ] `docs/README.md` 可独立充当唯一文档入口
- [ ] `AGENTS.md` 和 `CLAUDE.md` 的目录规则与新 taxonomy 一致
- [ ] `README.md` 和 `README.zh.md` 不再维护会漂移的详细 docs 清单
- [ ] 根入口统一指向 `docs/README.md`，而不是各自维护一套“核心文档列表”

---

## Phase 2: Directory Reshape And File Migration

**User stories**: 作为维护者，我需要把现行方案、历史归档和架构说明放回正确目录，这样路径语义和文档语义才一致。

### What to build

按映射清单执行目录重排：

- 在用方案迁入 `docs/roadmap/`
- `docs/plans/old/` 全量迁入 `docs/archive/plans/`
- `docs/architecture.md` 迁为 `docs/ref/architecture.md`
- 为 `architecture`、`specs`、`guides`、`roadmap`、`archive`、`reports`、`validation` 补齐简短 `README.md`

这一阶段只做路径归位和目录说明，不做深度拆文，避免与后续内容级重组交叉。

### Acceptance criteria

- [ ] 目标目录全部创建完成，并具备简短 `README.md`
- [ ] 所有计划/路线图/历史方案不再混放在 `docs/plans/`
- [ ] `docs/plans/old/` 被清空并由新归档目录替代
- [ ] `docs/architecture.md` 不再作为最终入口文件存在

---

## Phase 3: Long-Form Document Split

**User stories**: 作为读者，我需要长文档按主题拆分且保持阅读连续性，这样能快速定位信息，不必在单个超长文件中反复滚动搜索。

### What to build

在目标目录已稳定的前提下拆分超长文档：

- `core-refactor-plan.md` 拆为主索引 + phase / topic 子文档
- `task-facing-cli.md` 拆为命令语义、参数契约、示例与实现状态
- `architecture/overview.md` 保留核心结论，补充分章节设计文档

每个拆分后的主文档必须保留：

- 阅读顺序
- 子文档导航
- 反向链接
- 原有关键锚点语义的映射说明

### Acceptance criteria

- [ ] 每个长文档的主索引长度明显收敛，只承担导航与摘要职责
- [ ] 拆分后的子文档按主题分层，避免再次形成“超长附录”
- [ ] 主索引中明确给出阅读顺序与反向链接
- [ ] 旧锚点涉及的关键语义在新文档集合中仍可稳定定位

---

## Phase 4: Reference Rewrite And Searchability Cleanup

**User stories**: 作为维护者，我需要所有引用都指向新路径，并且命名和搜索关键词一致，这样搜索结果不会同时返回旧事实和新事实。

### What to build

基于映射表做全仓引用修正，覆盖：

- `README.md`
- `README.zh.md`
- `AGENTS.md`
- `CLAUDE.md`
- `docs/specs/*.md`
- `docs/guides/*.md`
- `docs/reports/*.md`
- 其他 docs 内 Markdown 的相对链接

同时统一命名风格，尤其是 phase 文档和 reports 文档的文件名规范。

### Acceptance criteria

- [ ] 不再存在对 `docs/plans/validation-framework.md`、`docs/plans/gastown-integration.md`、`docs/plans/oss-v1-plan.md` 这类失效路径的引用
- [ ] 根入口中的 repository map 与真实目录一致
- [ ] 同一类文档的命名规则一致，不再混用多套 phase/report 命名
- [ ] 文档内交叉引用全部采用相对路径

---

## Phase 5: Validation And Changelog Closure

**User stories**: 作为维护者，我需要确认迁移没有漏改，也没有影响运行时工件路径，这样本次重构才能安全收口。

### What to build

执行回归验证并记录结果：

- Markdown link check 或等效扫描
- `rg` 扫描旧路径残留
- 检查脚本与 Python 代码仍只依赖 `docs/validation/`
- 在 `docs/CHANGELOG.md` 记录重构规则、迁移范围和结果

### Acceptance criteria

- [ ] 全仓不存在残留旧路径引用，或残留项已被明确记录为有意保留
- [ ] `docs/validation/` 路径未发生变化，相关脚本和代码无需修改
- [ ] `docs/CHANGELOG.md` 记录本次重构的规则与结果
- [ ] 本次迁移后的新入口、目录职责和命名规则可由后续维护者直接复用

---

## Rollout order

推荐执行顺序如下：

1. Phase 0: 先做 inventory、taxonomy 和映射表
2. Phase 1: 建立唯一入口并改治理规则
3. Phase 2: 迁目录、建 README、落目标形态
4. Phase 3: 在目标形态内拆超长文档
5. Phase 4: 批量改引用并统一命名
6. Phase 5: 回归验证并更新 changelog

这个顺序的原则是：先固定分类与目标形态，再移动，再拆分，再修链接；避免“同一链接改两次”和“文档刚迁完又因拆分再次迁移”。
