# Research Initiation Program

这是一个面向启研/开题汇报的**最小复现仓库**，只保留三条核心假设对应的实验代码、任务生成、运行脚本与结果文件。

## 三条假设

- **H1：反馈优于盲目重试**
  在相同最多 3 次 Chat 调用预算下，比较开环独立重采样与闭环执行错误反馈修正谁更高效。
- **H2：技能模板可显著降低生成成本**
  成功轨迹模板化后，在同类任务上可显著减少生成 token，并尽量不牺牲任务成功率。
- **H3：游戏中的“受限代码 -> 沙箱执行 -> 结构化错误”协议可迁移到图表推理**
  重点不再是 mode A/B 总准确率谁更高，而是证明同一套**可验证协议**在图表/表格任务上也能跑通，并保留与游戏场景同等粒度的错误诊断能力。

## 仓库结构

- `exp1_code_verify/`：实验1，开环 3 次独立采样 vs 闭环最多 3 轮带错误反馈修正
- `exp2_skill_reuse/`：实验2，scratch vs skill 模板
- `exp3_chart_transfer/`：实验3，图表/表格场景下的受限代码执行与错误诊断
- `scripts/run_exp1_2_3.sh`：一键运行实验 1/2/3
- `scripts/run_overnight_123.sh`：与上面等价的夜间批跑脚本

## 实验设计

### 实验1：开环多采样 vs 闭环多轮修正

- 任务是网格导航，输出受限 `python`（`move` + `for range`）
- 开环组：同一任务独立生成 3 次，不共享历史
- 闭环组：最多 3 轮，每轮把沙箱返回的结构化错误追加到对话里
- 主指标：成功率、成功时平均调用次数、闭环首轮成功率

### 实验2：scratch vs skill

- 任务是 5x5 全空地曼哈顿路径
- scratch：不给模板，从零生成代码
- skill：给固定骨架，模型主要填两个 `range` 常数
- 主指标：`completion_tokens`；辅以 `reach_goal`

### 实验3：可验证协议迁移到图表/表格

- 输入是 **ASCII 柱状图 / 表格 + JSON 数值**，避免依赖多模态 API
- mode B 只允许 `ans = <expr>`，表达式受 AST 白名单限制
- 评测不只看对错，还输出结构化诊断字段：
  - `success`
  - `answer_wrong`
  - `syntax_or_rule_error`
  - `runtime_error`
- 运行时还会尽量给出**精确定位**信息：行号、列号、代码片段、越界位置等
- 诊断分析脚本：`exp3_chart_transfer/analyze_exp3_diagnostics.py`

## 当前已有结果

### 实验1（已跑完，N=100）

- 开环成功率：`0.03`
- 闭环成功率：`0.18`
- 闭环首轮成功率：`0.03`
- 结论：在相同最多 3 次调用预算下，**闭环反馈修正明显优于开环盲目重试**。

### 实验2（已跑完，N=100 对）

- `completion_tokens`：scratch `4055.84` -> skill `26.04`
- `reach_goal`：scratch `0.02` -> skill `0.28`
- 结论：当前强模板设定下，**技能模板显著降低成本且质量更高**。

### 实验3（文档暂不写结论，先保留设计与诊断能力）

- 已支持 `mode=b` 的结构化错误诊断与失败分布统计
- 可直接分析：

```bash
cd exp3_chart_transfer
python grade_jsonl.py --tasks tasks_overnight.json --input exp3_model_outputs_overnight.jsonl --out exp3_graded_overnight.jsonl
python analyze_exp3_diagnostics.py --tasks tasks_overnight.json --graded exp3_graded_overnight.jsonl
```

## 一键运行

```bash
export NVIDIA_API_KEY=你的key
cd /home/niuhaokai/niuhaokai/Research-Initiation-Program
./scripts/run_exp1_2_3.sh
```

前台运行：

```bash
./scripts/run_exp1_2_3.sh --foreground
```

## 结果文件

- `exp1_code_verify/exp1_compare_overnight.jsonl`
- `exp2_skill_reuse/exp2_results_overnight.jsonl`
- `exp3_chart_transfer/exp3_graded_overnight.jsonl`
- `exp3_chart_transfer/exp3_diagnostics_overnight.txt`（若用一键脚本重跑实验3）
