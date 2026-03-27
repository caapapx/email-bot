# Daemon、Go 薄壳与模组化测试（当前事实）

日期：2026-03-27  
状态：**以本仓库当前代码为准**；与旧计划/归档文档冲突时，优先本文 + `src/` + `tests/`。

## 目的

记录 **大范围重构分支** 上已经落地、可被单测与 CLI 验证的行为，避免读者被仅描述「目标形态」或「暂缓 Go」的旧段落误导。

## 已落地（本分支树内可核对）

| 能力 | 说明 |
|------|------|
| **Python 常驻 Daemon** | Unix socket + JSON-RPC 2.0（`ping`、`cli_invoke`），`twinbox_version` 字段；路径在 `$TWINBOX_STATE_ROOT/run/`、`logs/daemon.log` |
| **CLI** | `twinbox daemon start\|stop\|status\|restart`（`task_cli_daemon.py`） |
| **Go 薄客户端** | `cmd/twinbox-go/`：优先连 daemon，失败则 `exec` `python3 -m twinbox_core.task_cli`；见该目录 `README.md` |
| **单测** | `tests/test_daemon_rpc.py`、`tests/test_modular_mail_sim.py` |
| **模组化模拟邮箱** | `twinbox_core.modular_mail_sim`：无 IMAP/LLM 写入 `phase1-context.json`、`intent-classification.json`、Phase 4 YAML、`activity-pulse.json`；包装脚本 `scripts/seed_modular_mail_sim.sh` |
| **OpenClaw 话术** | `openclaw-skill/prompt-test.md` § P8（种子 + 对话验收） |

## 显式未包含（仍为 North Star / 后续 PR）

- `~/.twinbox` 唯一根与 vendor 释放、多 profile、OpenClaw deploy 软链真源、LSP、IMAP 连接池等（见历史 grill 计划类文档，**不作当前交付承诺**）。

## 常用命令

```bash
# Daemon
twinbox daemon start
twinbox daemon status --json

# Go（在 cmd/twinbox-go 构建后）
./twinbox-go task todo --json

# 模组化 30 封邮件种子（默认 ~/.twinbox）
bash scripts/seed_modular_mail_sim.sh
```

## 环境变量（摘要）

- `TWINBOX_STATE_ROOT`：state root（socket/PID/日志/模拟数据均在此下）。
- Daemon 客户端侧：`TWINBOX_DAEMON_SOCKET`、`TWINBOX_PYTHON`（Go 与文档同）。
- 连接空闲超时（测试可调）：`TWINBOX_DAEMON_CONN_IDLE_SEC`。

## 与历史文档的关系

- `docs/core-refactor.md` 中 **「Go 暂缓」** 的原始含义是：**不全量用 Go 重写 Phase 1–4 / LLM 管线**；**不排斥** Go 作为可选 **CLI 分发 / RPC 转发** 薄壳。
- 归档计划、旧 near-term 列表若未提及 daemon，视为 **文档未更新**，不以之否定已实现模块。
