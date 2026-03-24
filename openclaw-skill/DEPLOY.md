# OpenClaw Skill Deployment

目的：说明如何把 Twinbox 作为 `OpenClaw` 托管 skill 来准备、接入、验证，并明确当前哪些环节已经有基础、哪些仍处于待验证状态。

## 适用范围

这份文档关注的是“Twinbox skill 如何进入 OpenClaw 托管环境”。

不覆盖：

- OpenClaw 本体 Docker/Compose 安装细节
- Claude Code / Opencode 本地代理 skill

如果你还没把 OpenClaw 服务本身搭起来，先看：

- [../docs/guide/openclaw-compose.md](../docs/guide/openclaw-compose.md)

## 当前成熟度判断

### 已经有基础的部分

- 根级 [../SKILL.md](../SKILL.md) 已提供 `metadata.openclaw`
- `twinbox mailbox preflight --json` 已可作为登录预检接口
- `twinbox-orchestrate` 已是稳定的 phase 编排入口
- [../docs/ref/scheduling.md](../docs/ref/scheduling.md) 已定义 `schedules` 元数据和未来调度方向
- [../docs/ref/runtime.md](../docs/ref/runtime.md) 已定义 listener / action 的未来边界

### 仍未闭环或未验证的部分

- OpenClaw 是否已实际消费 `metadata.openclaw.schedules`
- OpenClaw 的 cron / heartbeat / background task 与 Twinbox phase 刷新如何对接
- listener / action / review runtime 如何在托管环境里运行
- 部署后的日志、通知、失败重试、stale fallback 责任边界
- 最终 skill 包是直接指向 repo 根，还是导出独立 package

## 推荐部署路径

### 1. 先把 Twinbox 本地运行面跑通

最低要求：

- Twinbox 代码可安装 / 可执行
- 邮箱 env 已配置
- `twinbox mailbox preflight --json` 能返回结构化结果
- 至少能手动运行一次：

```bash
twinbox-orchestrate run --phase 4
```

如果连本地 CLI 和 phase 刷新都没跑通，不要先上 OpenClaw 托管。

### 2. 校准 OpenClaw skill manifest

当前 manifest source of truth 是：

- [../SKILL.md](../SKILL.md)

重点检查：

- `metadata.openclaw.requires.env`
- `metadata.openclaw.login`
- `metadata.openclaw.schedules`

至少确认这些字段与当前实现一致：

- `preflightCommand` 使用 `twinbox mailbox preflight --json`
- schedule command 使用 `twinbox-orchestrate run ...`
- 不再引用 `twinbox orchestrate ...`

### 3. 决定 skill 包挂载方式

当前建议先按两种方式评估，不要过早锁死：

#### 方案 A：直接使用仓库根

适合：

- 本地自托管
- 开发期快速联调
- manifest / docs / CLI 都还在快速变化

优点：

- 不需要额外导出包
- root `SKILL.md` 就是 manifest source of truth

风险：

- 仓库内容较多，不够像最终交付物
- `.claude/`、测试、文档会一起暴露到包视角

#### 方案 B：从 `openclaw-skill/` 导出独立 skill package

适合：

- 后续发布
- 版本化部署
- 限定 OpenClaw 只看到最小 skill 交付物

优点：

- 交付边界清楚
- 更适合升级 / 回滚 / 发布管理

风险：

- 需要额外维护导出流程
- 当前仓库还没把 package build 这件事真正做起来

## 部署前检查清单

- [ ] `twinbox mailbox preflight --json` 本地成功
- [ ] `twinbox-orchestrate run --phase 4` 本地成功
- [ ] root `SKILL.md` 元数据与实现一致
- [ ] schedule command 全部使用 `twinbox-orchestrate`
- [ ] 未实现命令未出现在托管入口里
- [ ] OpenClaw 宿主环境能拿到 Twinbox 需要的 env

## 托管接入检查清单

- [ ] OpenClaw 能读取 skill manifest
- [ ] OpenClaw 能展示 / 收集 `requires.env`
- [ ] OpenClaw 能调用 `preflightCommand`
- [ ] preflight 失败时，平台能把 `missing_env` / `actionable_hint` 呈现出来
- [ ] preflight 成功后，能进入 phase 运行验证

## 调度与心跳专项检查清单

这部分当前是重点待梳理区，不应默认视为已完成。

- [ ] `metadata.openclaw.schedules` 是否已被平台解析
- [ ] 定时任务是否真的触发了 `twinbox-orchestrate run --phase 4`
- [ ] 失败后平台是否有重试 / 告警
- [ ] stale surface 出现时，谁负责补刷
- [ ] 平台是否有 heartbeat / worker / daemon 模型
- [ ] Twinbox 是否需要实现自己的 listener manager

## 上线后验证清单

- [ ] 每日 schedule 至少成功跑通一次
- [ ] weekly refresh 至少成功跑通一次
- [ ] phase4 产物生成后，queue / digest 可被消费
- [ ] preflight 错误能回显给平台用户
- [ ] stale 队列能被识别并恢复
- [ ] 没有自动发送 / destructive mailbox 操作

## 当前建议

现阶段不要把 OpenClaw 方案写成“已具备完整托管能力”。

更准确的状态是：

- Twinbox 已经准备好了 `manifest + preflight + orchestration CLI + scheduling contract`
- 但 OpenClaw 托管接入，尤其是 `schedule / heartbeat / listener / action runtime`，仍然需要单独推进和验证

下一步建议优先级：

1. 跑通 OpenClaw 对 `preflightCommand` 的真实消费
2. 验证 `metadata.openclaw.schedules` 是否会被真实执行
3. 再决定是直接用 repo 根，还是从 `openclaw-skill/` 导出独立包
