# Daemon、Go 薄壳与模组化测试（当前事实）

日期：2026-03-27  
状态：**以本仓库当前代码为准**；与旧计划/归档文档冲突时，优先本文 + `src/` + `tests/`。

## 目的

记录 **大范围重构分支** 上已经落地、可被单测与 CLI 验证的行为，避免读者被仅描述「目标形态」或「暂缓 Go」的旧段落误导。

## 已落地（本分支树内可核对）

| 能力 | 说明 |
|------|------|
| **Python 常驻 Daemon** | Unix socket + JSON-RPC 2.0（`ping`、`cli_invoke`、`imap_pool_stats`），`twinbox_version`；`logs/daemon.log` 使用 **轮转**（约 10MB×3）；路径在 `$TWINBOX_STATE_ROOT/run/` |
| **CLI** | `twinbox daemon start\|stop\|status\|restart`；`cli_invoke` 支持 `cache_policy` / `timeout_ms`（见 [rpc-protocol.md](./rpc-protocol.md)） |
| **Go 薄客户端** | `cmd/twinbox-go/`：RPC 或 `exec` Python；**`twinbox-go install --archive …`** 可从本地 tarball 或 HTTP URL 解压到 `$TWINBOX_STATE_ROOT/vendor/twinbox_core/` |
| **Profile** | `twinbox --profile NAME`：`TWINBOX_STATE_ROOT=~/.twinbox/profiles/NAME/state`，`TWINBOX_HOME=~/.twinbox`（共享 **vendor**） |
| **Loading 入口** | `twinbox loading phase1|…|phase4` 全部走 Python 入口；`phase1/4` 已迁为 Python 编排，`scripts/phase1_loading.sh` / `scripts/phase4_loading.sh` 仅保留兼容 shim，mail transport 仍走 himalaya CLI |
| **IMAP 池（可选）** | `TWINBOX_IMAP_POOL=1` 时 preflight 可走 `imaplib` 复用连接；统计经 RPC `imap_pool_stats` |
| **单测** | `tests/test_daemon_rpc.py`、`tests/test_modular_mail_sim.py`、`tests/test_vendor_install.py`、`tests/test_imap_pool.py` |
| **模组化模拟邮箱** | `twinbox_core.modular_mail_sim`；`scripts/seed_modular_mail_sim.sh` |
| **Vendor 副本** | `twinbox vendor install` 同步 `src/twinbox_core` → **`$TWINBOX_HOME/vendor`**（未设 `TWINBOX_HOME` 时与 **state root** 同根，即 `state/vendor`）；`MANIFEST.json` 含 `file_count`、`twinbox_version`；`vendor status` 含 **integrity** |
| **OpenClaw** | SKILL 真源 + 软链/复制；若已存在 **vendor/twinbox_core**，`deploy` 合并 `openclaw.json` 时会把 **插件 `config.cwd`** 指向该 **vendor** 目录 |
| **CI tarball** | `scripts/package_vendor_tarball.sh`（本地/流水线自行调用；仓库内未附带 GitHub workflow） |

## 显式未包含（仍为 North Star / 后续 PR）

- **Onboard / LSP**、daemon **自动监控重启**、Phase 4 **Go hot path** 重写等。
- **Loading**：phase1/4 编排已迁 Python，但 mailbox transport 仍依赖 himalaya CLI；未改为纯 Python mail transport。

## 常用命令

```bash
twinbox daemon start
twinbox daemon status --json
twinbox --profile work daemon start

./twinbox-go task todo --json
./twinbox-go install --archive dist/twinbox_core-0.1.0.tar.gz
./twinbox-go install --archive https://example.com/twinbox_core-0.1.0.tar.gz

twinbox vendor install
twinbox vendor status --json
twinbox loading phase1 -- --lookback-days 3

bash scripts/seed_modular_mail_sim.sh
```

## 环境变量（摘要）

- `TWINBOX_STATE_ROOT`、`TWINBOX_HOME`（共享 vendor）、`TWINBOX_DAEMON_SOCKET`、`TWINBOX_PYTHON`、`TWINBOX_IMAP_POOL`、`TWINBOX_DAEMON_CLI_TIMEOUT_SEC`、`TWINBOX_DAEMON_CONN_IDLE_SEC`。

## 相关参考

- [rpc-protocol.md](./rpc-protocol.md)、[artifact-contract.md](./artifact-contract.md)、[code-root-developer.md](./code-root-developer.md)

## 与历史文档的关系

- `docs/core-refactor.md` 中 **「Go 暂缓」** 指不全量 Go 重写 Phase 管线；**不排斥** Go 薄壳与安装辅助。
- 归档计划若未提及上述能力，视为文档未更新，不以之否定当前实现。
