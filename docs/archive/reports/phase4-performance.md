# Phase 4 性能对比：Bash Fallback vs Gastown Polecat

## 测试环境
- 日期：2026-03-19
- LLM API：讯飞 `astron-code-latest`（OpenAI-compatible）
- 最新 rerun 时间窗：2026-03-12 到 2026-03-19（`PIPELINE_LOOKBACK_DAYS=7`）
- 最新 rerun context：30 threads，132 recent envelopes，主仓库旧 validation 输出已先清理
- 说明：最新一轮改成“近一周”窗口，和前两轮的更宽窗口数据不是完全同量级；下面更关注编排形态差异

## 对比结果

| 维度 | Bash Fallback (并行) | Gastown Polecat（首次） | Gastown Polecat（2026-03-19 16:44 串行 rerun） | Gastown Polecat（2026-03-19 17:37 shared-repo 并行 rerun） |
|------|---------------------|-------------------------|------------------------------------------------|-------------------------------------------------------------|
| 总耗时 | ~3.5 min | ~9.5 min | 6m32s | 6m37s |
| Loading 完成 | ~30s | ~30s | 1m39s | 2m38s |
| Think wall time | ~3m | ~4.5m（单次大调用 + 重试） | 4m32s（单 session 串行） | 3m21s（3 session 并行） |
| Merge | ~1s | ~1m | 21s | 32s |
| 编排/恢复开销 | 0 | ~5m（探索代码 + 理解 formula） | ~1m09s（会话恢复 + 手动纠偏） | ~2m（session 启动 + 首次 nudge 未直接执行 + 手动二次触发） |
| 产出质量 | 8 urgent, 1 pending, 8 risks | 6 urgent, 7 pending, 4 risks | 7 urgent, 3 pending, 10 risks | 8 urgent, 3 pending, 5 risks |
| 可观测性 | stdout 日志 | `gt peek` / bead tracking / wisp | `gt peek` + 文件时间戳 | `gt peek` + 文件时间戳 + 多 session 进程 |
| 可复现性 | `bash scripts/run_pipeline.sh --phase 4` | `gt sling twinbox-phase4 twinbox --create`（当时 worktree 还是旧脚本） | 需要人工恢复 | 需要人工 `nudge` 到共享仓库，不能算稳定一键路径 |

## 时间线

### Bash Fallback
```text
loading(30s) -> [urgent(3m) | sla(1m) | brief(3m)] -> merge(1s)
wall time: ~3.5 min
```

### Gastown Polecat（首次）
```text
sling(5s) -> explore(5m) -> loading(30s) -> thinking-fail(2m) -> thinking-retry(4.5m) -> done(1m)
wall time: ~9.5 min
```

### Gastown Polecat（2026-03-19 16:44 串行 rerun）
```text
16:44:40 start
16:46:19 context-pack.json updated
16:49:02 urgent-pending-raw.json updated
16:50:03 sla-risks-raw.json updated
16:50:51 weekly-brief-raw.json updated
16:51:12 docs/validation/phase-4-report.md updated
wall time: 6m32s
```

### Gastown Polecat（2026-03-19 17:37 shared-repo 并行 rerun）
```text
17:37:55 dispatch loading to nitro
17:39:53 dispatch think fan-out to rust / chrome / guzzle
17:40:32 context-pack.json updated
17:41:37 weekly-brief-raw.json updated
17:41:42 sla-risks-raw.json updated
17:43:14 urgent-pending-raw.json updated
17:44:00 dispatch merge to nitro
17:44:31 docs/validation/phase-4-report.md updated
wall time: 6m37s
```

## 分析

### 已验证的改善

1. `P3` 的 formula 扩写确实压掉了“重新理解仓库”的大头。
   相比首次约 5 分钟的探索，这两次 rerun 都已经把主要时间花在真正执行，而不是读 README 和摸结构。

2. Gastown 的“真并行 think”这次已经验证成功。
   `rust`、`chrome`、`guzzle` 三个 session 分别执行：
   - `phase4_think_urgent.sh`
   - `phase4_think_sla.sh`
   - `phase4_think_brief.sh`

   且都通过共享仓库绝对路径脚本把 raw 输出写回了主仓库。

3. 单看 think 阶段，shared-repo fan-out 已经比 16:44 的单 session 串行 rerun 更快。
   从三路 fan-out 发出到最后一份 `urgent-pending-raw.json` 落盘，wall time 是 `3m21s`；
   上一轮单 session 串行 think 是 `4m32s`。
   这部分改善约 `26%`。

### 仍然没解决的瓶颈

1. 端到端总耗时并没有继续下降。
   虽然 think 变快了，但总 wall time 这次是 `6m37s`，比 16:44 的 `6m32s` 还略慢。
   原因不在 prompt，而在执行链：
   - session 启动
   - 首次 `nudge` 没有直接进入执行
   - 需要二次触发
   - merge 仍然要额外调度一次

2. `workflow formula -> wisp -> polecat work` 仍然不适合直接承载这次验证型并行。
   根本原因不是 formula 文本本身，而是 polecat worktree 默认彼此隔离。
   如果每个 polecat都在自己的 worktree 里跑 `phase4_loading/think/merge`，`context-pack.json` 和 `*-raw.json` 不会天然共享。
   这次能跑通，是因为命令显式执行了主仓库 `/home/caapap/fun/twinbox` 里的绝对路径脚本。

3. 所以现在的并行方案已经证明“能力可达”，但还没有证明“链路稳定”。
   当前验证路径依赖：
   - `gt session restart`
   - `gt nudge --mode=immediate`
   - shared-repo absolute-path command

   这仍然是人工恢复链，不是一条稳定的一键公式执行链。

## 当前结论

- **性能改善已部分验证**：Gastown 的 think 阶段从 `4m32s` 压到 `3m21s`，说明多 session 并行确实有效。
- **端到端性能尚未改善**：总耗时仍在 `6m30s` 量级，执行链调度开销抵消了并行收益。
- **现在最该修的是执行链稳定性，不是继续压缩 prompt**：真正的瓶颈已经从“仓库探索”转成“如何稳定把共享仓库任务送进多个 Gastown session”。
- **最新阶段性判断**：
  - `formula description` 扩写是值得保留的，已经解决了探索开销问题。
  - `shared-repo session fan-out` 是可行 workaround，已经验证 3 路 think 并行。
  - `workflow formula / wisp / mol-polecat-work` 还没有稳定到能直接承担这套共享产物并行。

## 下一阶段优化方向

1. 先把共享产物路径显式建模。
   要么让 Phase 4 子 formula 明确操作 canonical repo root，要么引入统一的 wrapper，避免继续靠人工 absolute-path `nudge`。

2. 再把 Phase 4 的 fan-out / merge 做成正式可复现编排。
   目标不是“一个 session 内并行 3 个 Bash”，而是：
   - 1 个 session 负责 loading / merge
   - 3 个 session 各跑一个 think 子任务
   - 全部都落到同一份共享产物目录

3. 最后再回头看 prompt 和模型层面的压缩。
   在执行链稳定之前，继续压 prompt 只会优化次要矛盾。
