# 开发进度快照

本文件汇总 **周期性工作快照**（可按周报节奏追加），分类与 GitHub 常见标签对齐：**Fix**、**Feat**、**Refactor**、**Docs**、**Chore**、**Security**。更细的技术结论见各 Phase 报告与 `docs/reports/`。

---

## 2026-03-23

### Feat / 新增（功能与能力）

- **Task-facing CLI 完整实现**：完成所有核心命令（queue, context, thread, digest）
  - `queue list/show/explain`：从 Phase 4 artifacts 投影队列视图
  - `context import-material/upsert-fact/profile-set/refresh`：用户上下文管理
  - `thread inspect/explain`：线程状态检视与解释
  - `digest daily/weekly`：每日/每周摘要视图
  - 统一入口脚本 `scripts/twinbox`，支持 `--json` 输出

### Docs（文档）

- 更新 `task-facing-cli.md` 规范文档，标记所有已完成命令的实现状态
- 新增 `test_task_cli.py` 测试文件，覆盖核心数据模型和辅助函数（8个测试全部通过）

### 阶段小结

完成了 task-facing CLI 的核心实现，为 skill、listener、review runtime 提供了稳定的命令面。所有命令都支持从 Phase 3/4 artifacts 投影出用户友好的视图，避免直接依赖 phase 文件细节。下一步可以推进 cadence 运行策略和对象 contract 收口。

---

## 2026-03-16 ~ 2026-03-22

### Fix（缺陷与稳定性）

- LLM 输出：加强 JSON 清理逻辑，降低解析失败。
- Phase 4 并行：将 `phase4_merge` 从并行脚本中拆出，避免重复调用 LLM。
- Gastown / Polecat：并行前同步 polecat worktrees；减少 formula 中的 polecat 探索范围。
- 仓库与合并：处理 `.gitignore` stash 合并冲突；gitignore `.beads/`、`.claude/`、`.runtime/` 等本地目录；移除误跟踪的 `.beads/metadata.json`。

### Feat / 新增（功能与能力）

- Phase 1–4 LLM 管线：各阶段 **loading / thinking** 分层；Phase 4 日报式价值输出。
- 人机上下文：runtime 上下文初始化脚本与空模板；Phase 2 读取人工事实/习惯/校准笔记；Phase 3 支持 human context。
- LLM 基础设施：双后端 + OpenAI 兼容接口；Phase 1–4 thinking 脚本统一接入。
- Gastown 融合：formula + sling 全链路、操作与编排相关能力；Phase 4 在 gastown 下的 **rerun** 与 **shared root** 稳定化。
- Python 路径：搭建 **python path core**，并把 Phase 1–4 thinking、Phase 2–3 loading、phase 渲染逐步收敛到 **Python 核心 + 共享渲染器**；**共享编排契约 CLI**；canonical state root 扩展到 Phase 1–3。
- 工程化：**bd（beads）** 问题跟踪初始化；明确 beads 路由模式。
- 渐进式验证：preflight 邮箱冒烟脚本；架构上的「渐进式注意力漏斗」写入计划与架构文档。

### Refactor（重构与结构调整）

- **full-pipeline formula**：由 convoy 改为 workflow 结构。
- **命名与骨架**：项目从 email-skill 迁到 **email-bot** / **twinbox**；公开 v1 runtime 骨架准备。
- LLM 后端切换与 `max_tokens` 从环境读取。
- 校准类笔记迁入 runtime 上下文；重构执行树可视化辅助理解。

### Docs（文档）

- 验证工件契约、语言层优化计划、实现重构计划更名。
- Gastown 集成与 formula 回退说明整理；gastown shell bootstrap；workflow DAG 验证记录。
- Phase 4 bash 并行 vs gastown polecat 性能对比；Phase 4 shared-root 清单。
- README 中英拆分、阶段与 gastown 管线说明；运行与测试路径文档。
- Phase 1–4 各阶段 LLM 迁移报告、架构审视、多 agent 集成计划等持续更新。

### Chore / 其他

- README 例行更新；Claude value skill 与 email-bot 的评估笔记；openclaw 路径与验证流程文档调整。

### Security（安全）

- 从 Git 跟踪内容中移除 PII，改为从环境变量读取。

### 阶段小结

本周从邮箱 Copilot 骨架与文档推进到 **四阶段 LLM 分层管线 + Gastown 编排 + Python 核心收敛**，同步完成 **PII 与 gitignore 治理**、**beads 跟踪** 以及 **验证契约与运行路径** 文档，整体在向「可重复运行、可对接 Gastown、可扩展 Python 路径」的形态靠拢。

---

## 后续追加方式

在上方新节之前插入新的 `## YYYY-MM-DD ~ YYYY-MM-DD` 区块，保持同类小标题一致即可。
