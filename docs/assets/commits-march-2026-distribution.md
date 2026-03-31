# 2026 年 3 月提交分布图：复现方法与结果记录

本文说明如何在**任意克隆**的仓库根目录，用 Git + Python 复现「全分支、全部作者」的 2026 年 3 月提交**按 UTC 日历日柱状图**与**按 UTC 时刻散点图**，并记录本仓库一次跑出来的**统计结果**（与 [`commits_march_2026_all_branches.png`](./commits_march_2026_all_branches.png) 一致）。

## 范围与时间

| 项目 | 取值 |
|------|------|
| 分支 | `git log --all`（所有可达 ref，不限当前检出分支） |
| 作者 | 不过滤（`--author` 不传） |
| 时间窗 | `2026-03-01 00:00:00` ≤ 提交时间 **早于** `2026-04-01 00:00:00`（与下面 `--until` 写法一致） |
| 日历 / 时刻 | 使用提交时间戳的 **UTC**（`%ai` 中的 `+0000` 等会由 Git 输出；解析时取 `YYYY-MM-DD HH:MM:SS` 部分按 UTC 理解） |

## 环境依赖

- Git（需能执行 `git log`）
- Python 3
- Matplotlib：`pip install matplotlib`（或等价方式安装到当前 Python）

## 一键复现（仓库根目录执行）

将下面整段保存为 `plot_march_commits.py` 后在仓库根运行：`python3 plot_march_commits.py`。

输出默认写入 **`docs/assets/commits_march_2026_all_branches.png`**（若目录不存在请先 `mkdir -p docs/assets`）。

```python
#!/usr/bin/env python3
"""March 2026 commit distribution: all branches, all authors, UTC."""

import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parent
OUT = REPO / "docs/assets/commits_march_2026_all_branches.png"


def main() -> None:
    out = subprocess.check_output(
        [
            "git",
            "log",
            "--all",
            "--since=2026-03-01 00:00:00",
            "--until=2026-04-01 00:00:00",
            "--pretty=format:%ai",
        ],
        cwd=REPO,
        text=True,
    )
    lines = [ln for ln in out.splitlines() if ln.strip()]
    rows: list[datetime] = []
    for line in lines:
        main, _tz = line.rsplit(" ", 1)
        rows.append(datetime.strptime(main, "%Y-%m-%d %H:%M:%S"))

    by_day = Counter(d.day for d in rows)
    days = list(range(1, 32))
    counts = [by_day.get(d, 0) for d in days]

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 9), gridspec_kw={"height_ratios": [1, 1.15]}
    )

    ax1.bar(days, counts, color="steelblue", edgecolor="white", linewidth=0.5)
    ax1.set_xlabel("March 2026 (day of month, UTC date)")
    ax1.set_ylabel("Commit count")
    ax1.set_title(
        f"Daily commits — all branches, all authors — March 2026 (n={len(rows)})"
    )
    ax1.set_xticks(list(range(1, 32, 2)))
    ax1.set_xlim(0.5, 31.5)
    ymax = max(counts) if counts else 1
    ax1.set_ylim(0, ymax * 1.08 if ymax else 1)

    xs = mdates.date2num(rows)
    ys = [d.hour + d.minute / 60.0 + d.second / 3600.0 for d in rows]
    ax2.scatter(xs, ys, alpha=0.35, s=25, c="coral", edgecolors="none", rasterized=True)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax2.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    ax2.set_ylabel("Time of day (UTC, decimal hours)")
    ax2.set_xlabel("Date")
    ax2.set_title(
        "Commit time scatter (each point = one commit; overlap stacks visually)"
    )
    ax2.set_ylim(-0.5, 24.5)
    ax2.grid(True, alpha=0.3, linestyle="--")
    fig.autofmt_xdate()
    plt.tight_layout()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150)
    print("saved:", OUT)
    print("total commits:", len(rows))


if __name__ == "__main__":
    main()
```

### 命令行核对统计（可选）

仅打印每日条数与总数（与上图同源数据）：

```bash
git log --all --since="2026-03-01 00:00:00" --until="2026-04-01 00:00:00" \
  --pretty=format:"%ai" | python3 -c "
from collections import Counter
from datetime import datetime
import sys
lines = [l.strip() for l in sys.stdin if l.strip()]
by_day = Counter()
for line in lines:
    main = line.rsplit(' ', 1)[0]
    d = datetime.strptime(main[:10], '%Y-%m-%d').day
    by_day[d] += 1
for d in sorted(by_day):
    print(f'2026-03-{d:02d}: {by_day[d]}')
print('total:', len(lines))
"
```

## 结果记录（本仓库快照）

以下数字来自**当时**对 twinbox 仓库执行 `git log --all` 的输出；历史改写或新增分支后重跑会变。

| 指标 | 值 |
|------|-----|
| 总提交数 | **301** |
| 峰值日（UTC） | **2026-03-28**，**69** 次 |

### 按 UTC 日历日（仅列有提交的日子）

| 日期 (UTC) | 提交数 |
|------------|--------|
| 2026-03-16 | 4 |
| 2026-03-17 | 13 |
| 2026-03-18 | 10 |
| 2026-03-19 | 31 |
| 2026-03-20 | 15 |
| 2026-03-23 | 19 |
| 2026-03-24 | 4 |
| 2026-03-25 | 19 |
| 2026-03-26 | 37 |
| 2026-03-27 | 32 |
| 2026-03-28 | 69 |
| 2026-03-29 | 21 |
| 2026-03-30 | 27 |

配图文件：[`commits_march_2026_all_branches.png`](./commits_march_2026_all_branches.png)。

## 变体说明

- **只要当前分支**：去掉 `git log` 的 `--all`。
- **只要某个作者**：增加 `--author=<email>` 或符合 `git log` 规则的 pattern。
- **换月份 / 时区**：改 `--since` / `--until`；若要用**本地时区**切日界，需先把 `%ai` 转成 `datetime` 并 `astimezone` 到目标 zone 再取 date，脚本需相应改动。
