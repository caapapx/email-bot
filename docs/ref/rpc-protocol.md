# Twinbox daemon JSON-RPC 协议

真源：`src/twinbox_core/daemon/`、`TWINBOX_PROTOCOL_VERSION`。线协议为 **JSON-RPC 2.0**，每行一条消息（newline-delimited）。

## 顶层字段

| 字段 | 方向 | 说明 |
|------|------|------|
| `jsonrpc` | 请求/响应 | 固定 `"2.0"` |
| `method` | 请求 | 方法名 |
| `params` | 请求 | 对象；缺省按 `{}` |
| `id` | 请求/响应 | 客户端相关 ID；通知可省略 |
| `twinbox_version` | 请求/响应 | 协议/构建版本字符串（与 `twinbox_core.daemon.TWINBOX_PROTOCOL_VERSION` 对齐） |
| `result` / `error` | 响应 | 标准 JSON-RPC |

## 方法

### `ping`

- **params**：`{}`
- **result**：`{ "status": "ok", "uptime_seconds": <int>, "twinbox_version": <str>, "active_connections": <int>, "cache_stats"?: { "hits", "misses", "size_mb" } }`

### `imap_pool_stats`

- **params**：`{}`
- **result**：`{ "enabled": bool, "pooled": bool }` — 与 `TWINBOX_IMAP_POOL` 及进程内连接持有状态一致（详见 `imap_pool.py`）。

### `cli_invoke`

在子进程中执行 `python -m twinbox_core.task_cli`，将 stdout/stderr/exit_code 返回给调用方。

| params 字段 | 类型 | 说明 |
|-------------|------|------|
| `argv` | `string[]` | 传给 `task_cli` 的参数（不含 `twinbox` 程序名） |
| `cache_policy` | `string` | 可选。`prefer_cache` \| `force_refresh` \| `cache_only`；缺省或未知值等价于不缓存（总是执行子进程） |
| `timeout_ms` | `int` | 可选。子进程超时（毫秒）。缺省使用环境变量 `TWINBOX_DAEMON_CLI_TIMEOUT_SEC`（秒，默认 300） |

**缓存语义（`cache_policy`）**：

- 缓存键 = `argv` 的规范化序列化 + `state_root/runtime/context` 下相关文件的 **mtime 指纹**。
- `prefer_cache`：指纹未变且存在缓存则返回缓存结果；否则执行并写入缓存。
- `force_refresh`：总是执行子进程并更新缓存。
- `cache_only`：仅返回缓存；未命中时 `exit_code` 非 0，`stderr` 含说明。

**result**：`{ "exit_code": int, "stdout": str, "stderr": str, "cache"?: "hit"|"miss"|"bypass" }`

## 错误码（JSON-RPC error.code）

| code | 含义 |
|------|------|
| -32700 | Parse error（非法 JSON） |
| -32600 | Invalid Request |
| -32602 | Invalid params |
| -32603 | 服务端处理异常（含 `cli_invoke` 内 `ValueError` 等） |

## 环境变量（摘要）

- `TWINBOX_STATE_ROOT`：state root（socket、日志、context 路径）。
- `TWINBOX_DAEMON_CONN_IDLE_SEC`：连接读超时（秒）。
- `TWINBOX_DAEMON_CLI_TIMEOUT_SEC`：无 `timeout_ms` 时子进程超时（秒）。

## 相关文档

- [daemon-and-runtime-slice.md](./daemon-and-runtime-slice.md) 当前落地行为
- [cli.md](./cli.md) `twinbox daemon …`
