# Drift Inventory: Documentation / SKILL.md / Implementation

日期：2026-03-26
状态：Active — 每次修复后更新

## 致命级（Skill 首次运行必失败）

| # | 位置 | 文档/SKILL.md 写法 | 实际实现 | 修复方案 |
|---|------|-------------------|---------|---------|
| F1 | SKILL.md schedules | `twinbox orchestrate run phase4` | `twinbox-orchestrate run --phase 4`（`twinbox_core.orchestration:main`） | 已统一独立入口 + `--phase` |
| F2 | SKILL.md schedules | 全量误写为 positional phases | `twinbox-orchestrate run`（不传 `--phase` 即 1→4） | 同左 |
| F3 | cli.md 命令树 | `twinbox orchestrate roots/contract/run` 列为 twinbox 子命令 | `orchestrate` 不在 `task_cli.py` 的 subparser 中，属于独立二进制 `twinbox-orchestrate` | cli.md 标注为独立入口 |

## 高级（参数不匹配，调用必报错）

| # | 命令 | 文档参数 | 实际参数 (task_cli.py) | 修复方案 |
|---|------|---------|----------------------|---------|
| H1 | `context import-material` | `--file PATH` / `--text TEXT` + `--label LABEL` | 位置参数 `source`（无 `--file`/`--text`/`--label`） | 对齐文档到实现，或扩展实现 |
| H2 | `context upsert-fact` | `--key KEY --value VALUE` | `--id ID --type TYPE --content CONTENT [--source SRC]` | 对齐文档到实现 |
| H3 | `context profile-set` | `--key KEY --value VALUE` | 位置参数 `profile` + `--key KEY --value VALUE` | 文档补充位置参数 `profile` |
| H4 | `queue list` | `--type TYPE`（可选 urgent/pending/sla_risk/stale/all） | 无 `--type` 参数，固定返回全部三个队列 | 对齐文档（删除 `--type`），或扩展实现 |
| H5 | `queue explain` | `TYPE THREAD_ID` 两个位置参数 | 无参数，只打印静态说明文本 | 对齐文档（降级为无参数说明），或扩展实现 |

## 中级（功能未实现，引用会 404）

| # | 命令 | cli.md 状态 | task_cli.py 状态 | 说明 |
|---|------|------------|-----------------|------|
| M1 | `thread summarize` | 命令树中列出 | 未实现 | 需标记 🚧 或实现 |
| M2 | `action apply` | 命令树中列出 | 未实现 | 需标记 🚧 |
| M3 | `review approve` | 命令树中列出 | 未实现 | 需标记 🚧 |
| M4 | `review reject` | 命令树中列出 | 未实现 | 需标记 🚧 |

## 低级（风格/一致性）

| # | 问题 | 位置 | 说明 |
|---|------|------|------|
| L1 | 错误信息混用中英文 | task_cli.py 全局 | 部分用"错误:"，部分用英文。建议统一 |
| L2 | `context refresh` 只打印提示文本 | task_cli.py:477-481 | 未实际执行刷新，只提示用户手动运行 orchestrate |
| L3 | scheduling.md 调试命令示例用 `twinbox orchestrate status` | scheduling.md:292 | `twinbox-orchestrate` 无 `status` 子命令 |
| L4 | DigestView weekly 的 `generated_at` 始终为空字符串 | task_cli.py:739 | weekly-brief-raw.json 中无 generated_at 字段 |
| L5 | `digest weekly` 命令 JSON 输出缺少 `stale` 计算 | task_cli.py:740 | 硬编码 `False`，未调用 `_is_stale` |

## 修复顺序

1. **F1-F3**：修正 SKILL.md / 调度文档 / `run` 的 `--phase` 用法与 cli.md 入口说明（OpenClaw 与本地 cron 依赖正确 argv）
2. **H1-H5**：对齐文档参数到实现（阻塞 Skill 调用）
3. **M1-M4**：标记未实现命令为 🚧（防止误调用）
4. **L1-L5**：低优先级清理
