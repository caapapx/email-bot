# Phase 4 性能对比：Bash Fallback vs Gastown Polecat

## 测试环境
- 日期：2026-03-19
- LLM API：讯飞 astron-code-latest（OpenAI-compatible）
- Context：55KB context-pack（30 threads, 210 envelopes, 20 bodies）
- 网络：讯飞 API 不稳定，有 websocket 断连

## 对比结果

| 维度 | Bash Fallback (并行) | Gastown Polecat (串行) |
|------|---------------------|----------------------|
| 总耗时 | ~3 min | ~9.5 min |
| Loading | ~30s | ~30s |
| LLM 调用 | 3 并行 × ~3min = ~3min wall | 1 串行 × ~4.5min (含重试) |
| 编排开销 | 0 | ~5min (探索代码 + 理解 formula) |
| LLM 失败处理 | 脚本内 clean_json fallback → {} | polecat 自主检查 env + 重试 |
| 产出质量 | 8 urgent, 1 pending, 8 risks | 6 urgent, 7 pending, 4 risks |
| 可观测性 | stdout 日志 | gt peek / bead tracking / wisp |
| 可复现性 | bash scripts/run_pipeline.sh --phase 4 | gt sling twinbox-phase4 twinbox --create |

## 分析

### 时间分布
```
Bash Fallback:
  loading(30s) → [urgent(3m) | sla(1m) | brief(3m)] → merge(1s)
  Wall time: ~3.5 min

Gastown Polecat:
  sling(5s) → explore(5m) → loading(30s) → thinking-fail(2m) → thinking-retry(4.5m) → done(1m)
  Wall time: ~9.5 min
```

### 关键差异

1. **编排开销**：polecat 花了 ~5min 探索代码库理解 formula，这是一次性成本。
   如果 polecat 有 session memory 或 checkpoint，后续执行会快很多。

2. **并行 vs 串行**：bash fallback 用 `&` 并行 3 个 LLM 调用，wall time 等于最慢的那个。
   polecat 用的是旧版串行脚本（worktree 基于旧 commit），单次大 LLM 调用。

3. **容错能力**：polecat 自主发现 API 错误、检查配置、决定重试 — 比脚本的 clean_json fallback 更智能。

4. **可观测性**：gastown 提供 bead tracking、wisp 状态、gt peek 实时监控，bash 只有 stdout。

### 结论

- **纯执行速度**：bash fallback 并行模式快 3x（3min vs 9.5min）
- **智能容错**：gastown polecat 更强（自主诊断 + 重试）
- **运维价值**：gastown 提供完整的工作追踪和可观测性
- **优化方向**：让 polecat worktree 包含最新并行脚本，可以同时获得并行速度 + gastown 编排能力
