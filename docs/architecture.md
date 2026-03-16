# 配置驱动的邮件代理架构

## 目标

构建一个稳定的 OpenClaw + Himalaya 邮件代理核心，在不分叉实现的前提下支持多公司、多角色和多个人。

这套架构强调三件事：

- 邮件传输层必须稳定、可替换
- 策略和个性化必须配置化
- 任何发送动作都必须经过可审计的人机闭环

## 六层模型

### 1. 传输层

职责：

- 通过 `himalaya` 访问 IMAP/SMTP
- 输出结构化邮件列表（`--output json`）
- 使用 `template send` 承接已确认的本地草稿发送

实现原则：

- 配置文件由 `.env` 渲染到 `runtime/himalaya/config.toml`
- 凭证优先使用 `keyring`
- 传输层不做业务判断

### 2. 标准数据层

职责：

- 把 Himalaya 输出转成统一内部结构，避免上层直接依赖 CLI 文本格式

建议字段：

- `message_id`
- `thread_id`
- `from`
- `to`
- `subject`
- `received_at`
- `body_text`
- `attachments`
- `labels`
- `mailbox`

### 3. 策略层

职责：

- 依据全局策略决定优先级、意图、建议目录、是否需要草稿、是否需要复核

输入：

- 发件人
- 关键词
- profile
- 风险条件
- 历史学习规则

输出：

- `intent`
- `priority`
- `suggested_folder`
- `summary_3bullet`
- `reply_recommended`
- `review_required`

### 4. Profile 层

职责：

- 注入角色差异，而不是修改核心流程

当前项目中的 profile：

- `executive`
- `recruiter`

每个 profile 由两部分组成：

- `config/profiles/*.yaml`：结构化风格、规则、摘要分区
- `config/profiles/rules/*.md`：人工确认后的经验规则

### 5. 草稿与审批层

职责：

- 把 AI 输出转成可复核的本地草稿
- 在显式确认后触发发送

标准流程：

1. 生成 `runtime/drafts/{{thread_id}}.eml`
2. 人工在本地查看或编辑
3. 只有当用户提供 `CONFIRM_SEND` 时，才允许发送

为什么采用本地草稿队列：

- 比“直接发出”更安全
- 比“只给一段文本草稿”更接近真实邮件流程
- 便于桌面客户端继续编辑，尤其适合高风险外发

### 6. 学习与可观测层

职责：

- 把人工修订转成下一轮更好的行为
- 让用户直观看到价值

学习流程：

1. 用户触发 `!learn` / `!rule` / `!edit`
2. 系统对比 AI 草稿与人工修改版
3. 推断一条新规则
4. 人工确认后，写入 `config/profiles/rules/{{profile}}.md`

可见指标：

- `triaged_count`
- `drafted_count`
- `awaiting_human_review`
- `sla_at_risk_count`
- `estimated_minutes_saved`

## 决策流

```text
himalaya envelope list --output json
-> 标准化邮件数据
-> 加载全局 policy
-> 加载 profile YAML
-> 加载 profile learned rules
-> 输出 intent / priority / summary
-> 如需回复则生成本地 .eml 草稿
-> 人工复核
-> 收到 CONFIRM_SEND 后才允许 template send
-> 记录指标与学习样本
```

## 通用核心与可定制边界

通用核心：

- Himalaya 接入
- JSON 解析
- 草稿文件生成
- 发送守护规则
- 审计日志与指标
- 学习闭环的“提议-确认-落盘”流程

可定制表层：

- `policy.default.yaml`
- `profiles/*.yaml`
- `profiles/rules/*.md`
- 摘要模板
- 发件人优先级清单

## 高可用与安全要求

- 同步必须基于 `message_id` 幂等
- 原始邮件与动作结果分开存储
- 草稿生成必须可重跑
- 默认禁止自动发送
- 法务/财务/外部回复/附件发送必须进入人工复核
- 任何学习规则都不能静默写入，必须先确认

## 实施规则

如果需求只影响某个人，写进对应 profile 规则文件。  
如果需求影响某个角色，写进对应 profile YAML。  
如果需求影响所有人的稳定性或安全性，写进通用核心与默认 policy。
