# Phase 3 Lifecycle 建模改造记录

## TL;DR

将 Phase 3 生命周期建模从硬编码模板改为 LLM 推断（astron-code-latest）。
LLM 从 20 条高频线程中识别出 5 条生命周期流，每条 4-5 个阶段，20 个线程全部归类并附证据链。

---

## 变更概要

| 项目 | 内容 |
|------|------|
| 日期 | 2026-03-19 |
| 变更类型 | new implementation |
| 新增脚本 | `scripts/phase3_loading.sh`, `scripts/phase3_thinking.sh` |
| LLM 后端 | astron-code-latest (OpenAI-compatible) |
| 人工上下文 | 支持 manual-facts / manual-habits / calibration notes |

---

## LLM 输出摘要

### 5 条生命周期流

| Flow | Name | Stages | Evidence Threads |
|------|------|--------|-----------------|
| LF1 | 资源申请审批流 | 5 | 11 |
| LF2 | 辽宁区域项目运营日报流 | 4 | 6 |
| LF3 | RDG货架授权管理流 | 4 | 1 |
| LF4 | 项目部署实施规划流 | 4 | 1 |
| LF5 | 工时填报提醒流 | 4 | 1 |

### Phase 4 推荐

LLM 建议 Phase 4 优先覆盖：
1. LF1（资源申请审批流）— 证据最充分，SLA 风险点明确
2. LF2（辽宁区域日报流）— 高度标准化，适合信息压缩

### 与旧版对比

旧版 lifecycle-model.yaml 也定义了 LF1-LF5，但：
- 旧版的 flow 定义和 stage 信号全部硬编码，无法适应新线程
- 旧版的 thread-stage-samples 只有 15 条，置信度是手写常量
- 新版从实际邮件内容推断，每条 evidence 引用具体发件人、主题格式、部署结果

---

## 已知局限

1. 只分析了 20 条高频线程的 body excerpt（500 字截断），低频线程未覆盖
2. LF3-LF5 各只有 1 条 evidence thread，置信度较低
3. 人工上下文当前为空模板，注入后需重跑验证效果
