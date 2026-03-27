# 如何跑测试

> 适合第一次接触这个项目的人阅读。不需要提前了解 pytest。

---

## 第一步：确认环境

```bash
cd /home/caapap/fun/twinbox/python
python3 -m pytest --version   # 确认 pytest 已安装
```

如果报错 `No module named pytest`，先安装：

```bash
pip install pytest pyyaml
```

---

## 第二步：跑所有测试

```bash
python3 -m pytest tests/ -v
```

跑完你会看到类似这样的输出：

```
tests/test_llm.py::TestCleanJsonText::test_removes_markdown_fence ... PASSED
tests/test_task_cli.py::TestActionCard::test_risk_boundary_80_is_high ... PASSED
...
112 passed in 0.4s
```

- **PASSED** = 通过
- **FAILED** = 失败，会显示原因
- **ERROR** = 测试本身崩了，通常是环境问题

---

## 第三步：只跑某一个文件

```bash
python3 -m pytest tests/test_task_cli.py -v
```

---

## 第四步：只跑某一个测试

```bash
python3 -m pytest tests/test_task_cli.py::TestActionCard::test_risk_boundary_80_is_high -v
```

---

## 这些测试在测什么

把所有测试文件按「你关心什么」分组：

### 🟢 数据结构是否正确
**文件**: `test_task_cli.py`（TestThreadCard、TestQueueView、TestActionCard 等）

测的是：把一个数据对象转成 JSON，字段还在不在、值对不对。

比如：
```
test_to_dict_is_json_serializable   — 验证转出来的是合法 JSON，不会序列化失败
test_risk_boundary_80_is_high       — urgency_score=80 时，风险等级必须是 "high"
test_risk_boundary_79_is_medium     — urgency_score=79 时，风险等级必须是 "medium"
```

---

### 🟢 命令行能不能跑通
**文件**: `test_task_cli.py`（TestActionCommands、TestReviewCommands、TestQueueDigestThreadCli）

测的是：执行一条 `twinbox` 命令，它应该成功退出（返回 0）还是报错退出（返回 1），以及 JSON 输出的字段有没有缺。

比如：
```
test_action_suggest_empty_returns_empty_list  — 没有 artifact 时，输出是 [] 而不是崩溃
test_action_materialize_not_found_exits_1     — 找不到 action ID 时，退出码是 1
test_queue_list_json_returns_three_queue_types — 队列列表必须包含 urgent/pending/sla_risk 三种
```

---

### 🟢 LLM 输出修复是否可靠
**文件**: `test_llm.py`

测的是：LLM 返回了带 markdown fence（` ```json ` 包裹）或 trailing comma 的响应，修复后是否是真正合法的 JSON。

重点：每个用例都会调用 `json.loads()`，如果修复后还不是合法 JSON，测试就失败。

---

### 🟢 评测指标计算是否正确
**文件**: `test_evaluation.py`

测的是：给定预测结果和标准答案，F1 分数算出来对不对，以及评测门禁（比「当分数比基准下降超过 1pp 时返回非零退出码」）有没有正确触发。

关注的边界：
```
test_perfect_match_gives_f1_of_1    — 预测 == 标准答案时 F1 = 1.0
test_zero_overlap_gives_f1_of_0     — 没有一个预测正确时 F1 = 0.0
test_empty_predicted_gives_f1_of_0  — 预测为空时 F1 = 0.0
test_gate_passes_when_no_regression — 没有退步时门禁应该放行（exit 0）
```

---

### 🟢 fixture 数据质量

信封类探测用例使用 `test_envelope_recipient_probe.py` 内联 JSON 结构，不再依赖大体积 `fixtures/` 目录。

---

## 测试失败了怎么办

### 看报错信息

```
FAILED tests/test_evaluation.py::TestCliGate::test_gate_fails_on_regression_above_threshold
AssertionError: assert 0 == 1
```

意思是：这个测试期望 exit code = 1，但实际得到了 0。

### 复制那一行单独跑

```bash
python3 -m pytest "tests/test_evaluation.py::TestCliGate::test_gate_fails_on_regression_above_threshold" -v -s
```

加 `-s` 可以看到 print 输出，有助于调试。

### 看具体 diff

```bash
python3 -m pytest tests/ -v --tb=short
```

`--tb=short` 显示精简的错误堆栈，比默认输出更容易读。

---

## 常用 fixtures 说明

测试文件里经常出现这些参数，不用手动传，pytest 会自动注入：

| 参数名 | 意思 |
|--------|------|
| `tmp_path` | pytest 自动创建的临时目录，测试结束后自动清理 |
| `monkeypatch` | 临时修改环境变量 / 函数，测试结束后自动还原 |
| `capsys` | 捕获 `print()` 输出，让测试可以检查命令行打印了什么 |
| `phase4_root` | 本项目自定义：创建 Phase 4 目录 + 设置环境变量（见 conftest.py） |
| `write_phase4` | 本项目自定义：往 phase4 目录写一个 YAML 文件 |
| `sample_urgent_item` | 本项目自定义：一条带所有字段的 urgent 样本数据 |
