# Phase 4 Gastown 并行执行 — 问题清单与解决方案

## 问题清单

### P1: merge 脚本重复调 LLM（设计 bug）
- 现象：polecat 先单独跑 3 个 think 脚本，再跑 `phase4_thinking_parallel.sh`，后者内部又启动 3 个子任务
- 影响：LLM 调了 6 次而非 3 次，raw 文件被覆盖，浪费 API 配额和时间
- 方案：拆出 `phase4_merge.sh`，只做 raw JSON → YAML/MD 合并，不调 LLM

### P2: polecat worktree 基于旧 commit
- 现象：第一次 sling 时 worktree 基于 `0d580e3`，缺少并行脚本
- 原因：polecat worktree 从 remote master 创建，但 master 没 push 最新 commit
- 方案：sling 前确保 `git push origin master`；并在 formula 里加 `git fetch + ff-only/rebase` sync step

### P3: polecat 探索开销过大（~5min）
- 现象：每次 sling 都花 5 分钟探索代码库、读 formula、理解结构
- 原因：polecat 没有 session memory，每次从零开始
- 方案：在 formula description 里写更详细的执行指令，减少探索需求；或用 `gt remember` 存 context

### P4: 讯飞 API 不稳定
- 现象：websocket close 1006、JSON parse error、rate_limit_exceeded
- 影响：brief 子任务需要 3 次才成功，最终 API 限额耗尽
- 方案：
  1. `llm_common.sh` 已有 timeout + retry（已实现）
  2. `clean_json` 增加更宽松的 JSON 修复（截断修复、尾部补全）
  3. 配置备用 LLM backend（ANTHROPIC_API_KEY 作为 fallback）

### P5: formula molecule 只实例化 1 个 step
- 现象：`bd mol show` 显示 "Steps: 1"，polecat 看不到完整 5 步 DAG
- 原因：gastown molecule 系统可能不支持 workflow formula 的 step 展开
- 方案：polecat 直接读 formula TOML 文件（已 workaround）

### P6: reuse idle polecat 导致 session 启动失败
- 现象：第一次 sling reuse idle polecat，tmux session 没创建，polecat 标记 done 但没执行
- 原因：idle polecat 的 session 状态不干净
- 方案：sling 时用 `--create` 强制创建新 polecat（已 workaround）

### P7: gt 不在 Bash tool 的 PATH 里
- 现象：每次 Bash 调用都要 `export PATH=...`
- 原因：Bash tool 启动非交互式 shell，不 source .bashrc
- 方案：工具限制，无法修复；在脚本里用绝对路径

## 优先级排序

| 优先级 | 问题 | 修复成本 | 影响 |
|--------|------|----------|------|
| 高 | P1 merge 重复调 LLM | 低（拆脚本） | 省 50% API 调用 |
| 高 | P4 API 不稳定 | 中（备用 backend） | 提高成功率 |
| 中 | P3 探索开销 | 低（优化 formula） | 省 5min/次 |
| 中 | P2 worktree 旧 commit | 低（push 流程） | 避免脚本缺失 |
| 低 | P5 mol steps 不展开 | 取决于 gastown | 影响可观测性 |
| 低 | P6 idle reuse 失败 | 已 workaround | 偶发 |
| 低 | P7 PATH 问题 | 工具限制 | 仅影响调试 |
