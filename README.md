# Research Initiation Program (Experiments-Only)

本仓库仅保留 `Game-RL/experiments` 的可复现实验资产，聚焦三条假设：

- **H1**：代码执行可作为过程验证信号（网格任务 A 文本 vs B 可执行代码）。
- **H2**：成功轨迹可抽象为可复用技能模板（scratch vs skill）。
- **H3**：游戏场景验证方法可迁移到图表/表格推理（A 文本答案 vs B `ans=<expr>` 沙箱执行）。

## 目录

- `exp1_code_verify/`：实验一任务、提示词、沙箱、评分与批跑脚本
- `exp2_skill_reuse/`：实验二任务、技能模板、token 对比脚本
- `exp3_chart_transfer/`：实验三图表/表格任务、沙箱、评分与汇总脚本
- `scripts/`：夜间批跑、预检、任务生成工具
- `config_overnight/`：示例配置模板
- `EXPERIMENTS_1_AND_2_REPORT_CN.md`：实验一/二长版报告
- `EXPERIMENTS_THREE_MERGED_CN.md`：三实验合并版设计与结果说明

## 当前最佳结果（截至最新一次完整 overnight）

数据来自一次完整跑批（日志已确认到 `"[overnight] 全部完成。"`），对应输出文件：

- `exp1_code_verify/graded_overnight.jsonl`
- `exp2_skill_reuse/exp2_results_overnight.jsonl`
- `exp3_chart_transfer/exp3_graded_overnight.jsonl`

### 实验一（H1, N=100）

- `mode_a` 正确率：**0.07**
- `mode_b` 正确率：**0.06**

### 实验二（H2, N=100 对）

- `completion_tokens_mean_scratch`：**4055.84**
- `completion_tokens_mean_skill`：**26.04**
- `paired_mean_scratch_minus_skill`：**4029.80**
- `skill_rate_vs_scratch_completion`：**0.0064**
- `reach_goal_rate_scratch`：**0.02**
- `reach_goal_rate_skill`：**0.28**

### 实验三（H3, N=180）

- `mode_a_accuracy`：**0.6667**
- `mode_b_accuracy`：**0.6389**

## 说明

- 已移除失败的历史日志目录（`logs_overnight_*`）。
- 本仓库仅保留可复现实验代码与结果文件，不包含 Game-RL 其他模块。
