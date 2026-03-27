# Twinbox 产物契约（Phase 1–4 与运行时）

本文档描述 **state root** 下常见 JSON/YAML 产物的角色与路径约定；**schema 以仓库内生成代码与测试 fixture 为准**，变更时需同步单测与 OpenClaw 话术。

## 根布局（约定）

| 路径 | 说明 |
|------|------|
| `runtime/context/` | Phase 1 上下文包、原始拉取等 |
| `runtime/context/phase1-context.json` | Phase 1 汇总上下文 |
| `runtime/context/intent-classification.json` | Phase 1 意图分类 |
| `runtime/validation/phase-4/` | Phase 4 验证与队列投影 |
| `runtime/validation/phase-4/activity-pulse.json` | 日间活动脉冲（task/digest 等读取） |
| `runtime/himalaya/config.toml` | Himalaya 渲染配置（mailbox） |

## YAML 配置（仓库 `config/` 为模板）

| 文件 | 用途 |
|------|------|
| `config/policy.default.yaml` | 默认策略 |
| `config/routing-rules.yaml` | 语义路由规则 |
| `config/schedules.yaml` | 调度元数据 |
| `config/profiles/*.yaml` | 用户画像模板（与 CLI `--profile` 多邮箱 **state** 目录不同名空间） |

具体键名以各模块的 load/save 实现为准（如 `routing_rules.py`、`schedule_override.py`）。

## Phase 4 与队列

队列、thread card、review 等 **视图**由 Phase 4 产物与 [cli.md](./cli.md) 所述命令投影；字段级 schema 见 `tests/` 与 `src/twinbox_core` 内 dataclass / 解析逻辑。

## 与 daemon 缓存

`cli_invoke` 的 `cache_policy` 使用 `runtime/context/` 下文件 mtime 作为 **失效指纹** 的一部分（见 [rpc-protocol.md](./rpc-protocol.md)）。

## 相关文档

- [validation.md](./validation.md) 验证工件角色
- [orchestration.md](./orchestration.md) 编排与调度
