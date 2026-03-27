# Code root（开发者模式）

Twinbox 将 **安装/源码树**（code root）与 **用户数据**（state root，默认 `~/.twinbox`）分开。`code_root` 由 `TWINBOX_CODE_ROOT` 或 `~/.config/twinbox/code-root` 等解析（见 [`paths.py`](../../src/twinbox_core/paths.py)）。

## 谁需要 code root

- **仓库内开发**：当前目录或配置的 code root 指向本仓库；`resolve_code_root` 解析到含 `src/twinbox_core` 的树。
- **仅宿主 / OpenClaw**：可在只配置 state root + `twinbox vendor install` 或 Go `twinbox-go install` 解压 vendor 后，用 `PYTHONPATH=$TWINBOX_HOME/vendor` 运行；**不必**在网关上保留 git 仓库。

## 与 profile 的关系

使用 `twinbox --profile NAME` 时：

- `TWINBOX_STATE_ROOT` → `~/.twinbox/profiles/NAME/state`
- `TWINBOX_HOME` → `~/.twinbox`（共享 `vendor/`）

## 迁移提示

若历史文档仍强调「必须配置 code-root 文件」，以本文与 [`daemon-and-runtime-slice.md`](./daemon-and-runtime-slice.md) 为准：无 clone 路径以 **vendor + 绝对路径** 为主，code root 为开发者可选。
