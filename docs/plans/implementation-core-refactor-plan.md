# 实现层重构与全局架构收敛计划

日期：2026-03-20  
项目：twinbox

## 目标

在不重写产品语义的前提下，收敛当前仓库的“中编程层”：

- 保留 `bash` 作为薄编排层
- 引入 `Python` 作为可测试的核心实现层
- 暂缓 `Go`，直到仓库真正进入常驻 runtime / listener manager / worker service 阶段
- 同时把当前已经暴露出的全局架构摩擦点落成明确迁移约束

这里讨论的不是“换一门语言会不会更快”，而是：

- 哪些复杂度不该继续留在 shell
- 哪些契约应该先被拉直
- 语言层迁移如何服务于整体架构收敛

## 结论

当前最合适的目标形态不是 “all in Go” 或 “全部重写”，而是：

```text
bash entrypoints / gastown formulas
  -> python core modules
      -> transport adapters / artifact store / llm adapters
```

具体判断：

- `bash` 继续保留在入口、环境装配、薄编排、向后兼容脚本层
- `Python` 接管 context-pack builder、artifact contract、LLM boundary、renderer 等核心逻辑
- `Go` 留给未来的长生命周期能力：
  - listener manager
  - scheduled execution
  - worker orchestration service
  - review/send runtime

## 为什么不是现在就上 Go

Go 当然有价值，但它当前不是最优先的解。

Go 擅长：

- 强类型的长期维护
- 并发与常驻进程
- 单文件二进制分发
- service/runtime 产品化

而 twinbox 当前更痛的地方是：

- phase 间 artifact contract 漂移
- shell / inline Node 里堆了过多数据处理
- LLM 调用边界不统一
- 文档产物与运行时产物 ownership 混在一起
- docs 里的语义与实际脚本产物已经出现偏差

这些问题的第一阶段更像“把浅模块收成深模块”，不是“把脚本改写成高性能服务”。

`Python` 在这一阶段的收益更直接：

- 更容易表达数据模型和 schema 校验
- 更容易做 fixture test / contract test / golden test
- JSON / YAML / markdown / mermaid 处理都比 shell 自然
- 可以保留现有 `bash scripts/*.sh` 和 formula 入口，不破坏 Gastown 现状

## 全局架构摩擦点

语言层优化不应只盯着“脚本可读性”。当前至少有六个全局摩擦点需要一起考虑。

### 1. context-pack builder 重复

当前 `Phase 2` 和 `Phase 3` 的 loading 都在自己实现一份派生上下文逻辑：

- `normalizeEnvelope`
- sender/domain 统计
- thread key 归一化
- legacy fallback
- human context 合入

代表文件：

- `scripts/phase2_loading.sh`
- `scripts/phase3_loading.sh`

问题本质：

- 同一个“由 Phase 1 artifacts 派生 phase-ready context”概念，被拆成多个浅脚本
- 同样的逻辑以 inline Node 形式复制粘贴

影响：

- 修改输入契约时需要多处同步
- 测试只能围绕文件树和脚本执行搭建，成本高

### 2. LLM boundary 分裂

当前 LLM 调用边界不一致：

- `scripts/llm_common.sh` 提供公共 backend + retry + JSON repair
- `scripts/phase1_thinking.sh` 仍自带一套 transport / parse 流程
- prompt 组装、返回修复、provider 差异处理没有一个统一 contract

问题本质：

- 仓库没有一个 authoritative 的 “LLM request/response boundary”

影响：

- phase 间行为不一致
- 无法集中做 malformed JSON、timeout、retry、schema drift 测试

### 3. artifact ownership 混合

当前单个脚本经常同时负责：

- LLM 调用
- 结构化状态产物
- YAML 序列化
- markdown 报告
- mermaid 图表

代表文件：

- `scripts/phase2_thinking.sh`
- `scripts/phase3_thinking.sh`
- `scripts/phase4_merge.sh`

问题本质：

- “运行时状态”与“给人看的报告”没有边界

影响：

- 很难只测状态正确，不顺带把文档格式一并锁死
- 重构数据层时容易被 markdown 快照拖住

### 4. attention-budget 契约漂移

文档已经把 `attention-budget.yaml` 定义成阶段间核心契约，但脚本侧大多还没真正围绕它收敛。

问题本质：

- spec 里以 attention budget 为主线
- runtime 里更多还是靠“某几个文件存在”推进阶段依赖

影响：

- 跨 phase 测试无法围绕一个稳定工件断言
- 架构故事与实现路径在逐步背离

### 5. docs/runtime 耦合

当前 loader 会直接读取 `docs/validation/` 下的 markdown 作为输入的一部分。

问题本质：

- 文档目录既是报告面，也是运行输入面

影响：

- 文档格式调整可能破坏运行
- 测试 fixture 必须同时准备 runtime 数据和 markdown 文本

### 6. state root 模型只在 Phase 4 收敛

`Phase 4` 已经引入 `code root / state root` 分离，但 `Phase 1-3` 仍主要把 repo root 当一切的根。

问题本质：

- 多 worktree 语义在不同 phase 中不一致

影响：

- 本地串行和 Gastown worker 模式不是同一个状态模型
- 上游 phase 后续很可能重复踩一遍 Phase 4 刚处理过的问题

## 目标分层

目标不是“把所有 shell 脚本删掉”，而是把职责重分配。

### 1. Shell Layer

职责：

- 参数入口
- 环境装配
- 调用 Python 命令
- 保持与现有 formula / `gt sling` / 本地手工命令兼容

应该保留在 shell 的典型内容：

- `check_env`
- `render_himalaya_config`
- `phase4_gastown.sh`
- `run_pipeline.sh`

约束：

- 不承载复杂数据处理
- 不承载 artifact 序列化
- 不承载 LLM 协议细节

### 2. Python Core Layer

职责：

- phase 输入模型
- phase artifact contract
- context-pack builder
- thread normalization
- attention-budget 读写
- LLM request/response abstraction
- output renderer

这是最应该“加深模块”的层。

目标特征：

- 暴露小接口
- 把 JSON/YAML/markdown 细节封装在内部
- 支持 fixture-driven tests

### 3. Adapter Layer

职责：

- Himalaya / mailbox CLI 调用
- 文件系统 artifact store
- LLM provider adapter

这层要尽量薄，给 core 提供稳定依赖。

### 4. Future Runtime Layer

暂不实现，但为未来留接口：

- listener runner
- action instance materializer
- review / audit pipeline
- scheduler / daemon / worker service

这个阶段才值得认真评估是否引入 `Go`。

## 推荐目录形态

建议从当前仓库平滑演进到这种结构：

```text
scripts/
  run_pipeline.sh
  phase1_loading.sh
  phase1_thinking.sh
  phase4_gastown.sh

python/
  pyproject.toml
  src/twinbox_core/
    paths.py
    artifacts/
      phase1.py
      phase2.py
      phase3.py
      phase4.py
      attention_budget.py
    context/
      mailbox_snapshot.py
      context_builder.py
      human_context.py
      thread_model.py
    llm/
      client.py
      schema.py
      repair.py
      prompts/
        phase1.py
        phase2.py
        phase3.py
        phase4.py
    render/
      reports.py
      mermaid.py
      yaml_outputs.py
    orchestration/
      phase_runner.py
      dependencies.py
      state_root.py
tests/
  fixtures/
  contract/
  integration/
```

说明：

- `scripts/` 不消失，只变薄
- `python/` 是中编程层
- `tests/` 围绕 Python core 建立，而不是围绕 shell 文本

## 迁移顺序

### Phase A: 先收紧契约，不先重写全部

目标：

- 明确每个 phase 的 authoritative artifact
- 决定 `attention-budget.yaml` 是否真的是主线契约
- 区分 state artifact 与 report artifact

输出：

- phase artifact contract 文档
- 状态产物与文档产物的 ownership 规则

这是最优先的一步。否则只是把混乱从 bash 搬到 Python。

### Phase B: 落 Python core 的共享底座

目标：

- 建 `pyproject.toml`
- 建 `twinbox_core.paths`
- 建 `twinbox_core.llm`
- 建 `twinbox_core.artifacts`

优先迁移：

- state root 解析
- artifact load/save
- LLM backend 调用与 JSON repair

完成标准：

- shell 不再直接拼复杂 JSON
- 各 phase thinking 不再各自处理 provider 差异

### Phase C: 迁 context builder

优先对象：

- `phase2_loading`
- `phase3_loading`

目标：

- 合并重复的 envelope normalization
- 合并 human context merge
- 合并 legacy fallback
- 建一个共享的 `context_builder`

完成标准：

- Phase 2/3 loading 只负责“调用 Python module 并落盘”

### Phase D: 迁 render / merge

优先对象：

- `phase4_merge`
- `phase4_thinking_parallel` 中重复的 merge/render
- `phase2/3` 的 report + diagram 写入

目标：

- 拆出统一 renderer
- 让并行 fallback 与 merge-only 共享一份输出逻辑

完成标准：

- YAML / markdown / mermaid 序列化不再在多个脚本中复制

### Phase E: 收敛 orchestration contract

目标：

- 让 pipeline dependency 不再只是“文件存在”
- 把 phase 输入输出变成显式 contract
- 决定 Gastown formula 与本地 fallback 如何共用一个 orchestration surface

这一步之后，才适合真正做更高级的并发和失败恢复。

### Phase F: 再评估 Go

只在以下条件成立时启动：

- listener / action runtime 要常驻运行
- 需要更强的 worker 隔离
- 需要长期稳定的并发任务执行层
- Python core 已经把 phase contract 稳定下来

如果这些前提未满足，上 Go 只会放大迁移面。

## 迁移原则

### 1. Replace, do not stack

不要在 bash 外再包一层 Python，但旧 shell 逻辑还继续存在。

应该是：

- shell 入口保留
- 核心逻辑迁出
- 旧的 inline 逻辑逐步删除

### 2. Contract before implementation

先定义 authoritative artifact，再迁语言层。

否则只是在新语言里继续复制漂移的接口。

### 3. State before report

先把运行时状态产物收敛，再考虑 markdown/diagram。

报告是视图，不应反过来决定核心模型。

### 4. Keep formulas stable

公式和 `gt sling` 入口尽量保持不变。

迁移优先做“内部替换”，避免同时改：

- 语言层
- 目录结构
- 公式行为
- phase 语义

### 5. Extend state-root model upward

`Phase 4` 的 `code root / state root` 分离不应该停在 Phase 4。

后续 Phase 2/3 若继续参与 worker fan-out，也应复用同一套状态根语义。

## 近期可执行切片

下面这些切片足够小，适合作为真正开始迁语言层时的第一批任务。

1. 建 `python/pyproject.toml` 与 `src/twinbox_core/`
2. 迁 `twinbox_paths` 到 Python，并让 shell 只做薄封装
3. 迁 `llm_common.sh` 到 Python client
4. 把 `phase2_loading` 和 `phase3_loading` 的共享逻辑抽成 `context_builder`
5. 把 `phase4_merge` 与 `phase4_thinking_parallel` 的重复渲染逻辑合并到 `render.phase4`
6. 单独定义 `attention-budget` 的真实 owner、真实读者和真实写者

## 非目标

这轮语言层优化不应顺手做这些事：

- 全量重写成 Go
- 改变 Phase 1-4 的产品语义
- 现在就做 listener runtime
- 引入前端或服务化部署
- 为了“类型更强”而先大规模改目录

## 与现有文档的关系

- `docs/architecture.md` 定义目标架构与长期原则
- `docs/plans/progressive-validation-framework.md` 定义阶段漏斗与验证语义
- `docs/plans/gastown-multi-agent-integration.md` 定义 Gastown 编排现状
- 本文档只回答一个问题：当前仓库应如何优化语言层和中编程层，才能支撑后续架构收敛

## 推荐决策

如果下一轮真的开始动语言层，我建议按这个顺序决策：

1. 先确认 `attention-budget` 是否继续作为 authoritative phase contract
2. 再建立 `Python core`
3. 先迁 shared builder / LLM / renderer
4. 最后才评估是否需要 `Go runtime`

这比“先选一门更强的语言”更重要。
