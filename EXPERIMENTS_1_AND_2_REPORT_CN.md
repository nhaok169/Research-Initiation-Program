# 实验一与实验二：详细设计说明与结果汇总

> **精简合并（三实验设计 + 理由 + 结果一页稿）**：见同目录 [`EXPERIMENTS_THREE_MERGED_CN.md`](./EXPERIMENTS_THREE_MERGED_CN.md)。

本文档汇总仓库内 **实验一（过程验证信号）** 与 **实验二（技能复用与生成效率）** 的研究问题、实验设计、实现位置、指标定义、运行方式，以及**一次示例跑批**得到的结果（便于写启研/论文；**重新跑 API 后数字会变**，以你本地 `*.jsonl` 与终端汇总为准）。

---

## 一、总览：两个实验在验证什么

| 项目 | 实验一 | 实验二 |
|------|--------|--------|
| **核心假设** | **H1**：代码执行可作为**过程验证信号**——在受控协议下，相对纯文本推理，可执行代码路径更利于得到**可靠到达策略**（以「是否到达终点」为主指标）。 | **H2**：成功轨迹可抽象为**可复用技能**——在**同一类任务**上，**复用技能模板**比**从零生成**更省**模型生成 token**（主指标：`completion_tokens`）。 |
| **自变量** | 回答形式：**A 纯文本动作** vs **B 受限 Python + 沙箱执行**。 | 提示结构：**从零（无技能段）** vs **技能（曼哈顿模板 + 填 `range`）**。 |
| **任务域** | **10** 个带墙网格寻径实例（`t01`–`t10`），文本描述含 ASCII 图与 `grid` JSON。 | **20** 个 **5×5 全空地**实例（`s01`–`s20`），仅起点/终点变化。 |
| **主因变量** | **到达终点正确率**（A：解析文本动作后仿真；B：沙箱执行后仿真）。 | **配对比较**下的 **completion_tokens**（及可选 `total_tokens`）。 |
| **代码目录** | `experiments/exp1_code_verify/` | `experiments/exp2_skill_reuse/` |

两实验衔接关系：**实验一**在「文本 vs 代码」层面看**正确率**；**实验二**在**已定代码范式**内，看**是否提供结构化技能**对**生成长度**与**任务完成率**的影响。

---

## 二、实验一（exp1）：详细设计

### 2.1 研究问题与假设（H1）

- **问题**：同一网格任务下，模型用**自然语言动作**作答 vs 用**可在沙箱中执行的 `move` 代码**作答，哪种更常使角色**到达终点**？
- **动机**：可执行代码将「规划」与「逐步状态更新」交给**确定性环境**，减轻纯语言推理中的计数/方向错误；与 Game-RL / 校验中枢叙事一致。
- **注意**：主指标是**终止状态是否到达终点**，而非「代码无异常即正确」——避免把语法通过但路径错误判成对。

### 2.2 任务与数据

- **任务文件**：`experiments/exp1_code_verify/tasks.json`
- **任务数量**：**10** 条，`id` 为 `t01` … `t10`。
- **地图表示**：`grid[r][c]`，`0` 空地，`1` 墙；坐标 **`(行, 列)`**，行向下增大、列向右增大。
- **每条字段**：`id`、`name`、`grid`、`start`、`goal`、`question`（题干片段）。
- **数据质检**：`experiments/exp1_code_verify/validate_tasks.py`  
  - 检查起点/终点不在墙上、在界内、**BFS 可达**；  
  - **跑 API 前**应执行，避免「题干与评测网格不一致」（曾修复 `t02`/`t07` 起点落在墙上的错误）。

### 2.3 环境与执行语义

- **实现**：`experiments/exp1_code_verify/env.py` 中 `GridEnv`。
- **`move(direction)`**：`up/down/left/right` 或 `上/下/左/右`；撞墙或越界则**该步不移动**（不抛错），与 SYSTEM 说明一致。
- **成功判据**：执行完模型给出的动作序列（A 由解析得到，B 由沙箱执行）后，**`(player_r, player_c) == goal`**。

### 2.4 方式 B：受限沙箱（可复现、可辩护）

- **实现**：`experiments/exp1_code_verify/sandbox.py`
- **允许语法**（顶层）：
  - `move("...")`，参数为**字符串常量**；
  - `for ... in range(整数常量):`，循环体仅允许上述允许的语句嵌套。
- **禁止**：`def` / `import` / `print` / `while` / 赋值 / 其它函数调用等（通过 AST 白名单检查）。
- **设计理由**：与「环境注入唯一 `move`」一致，防止模型自定义 `def move` 导致评测与真实环境脱节。

### 2.5 提示词（A / B）

- **文件**：`experiments/exp1_code_verify/prompts.py`
- **共用 SYSTEM**（`SYSTEM_SHARED`）：坐标系、合法移动、撞墙规则、`grid` 含义。
- **方式 A**（`user_mode_a`）：仅自然语言步骤；明确要求**不要代码**、不要 markdown 代码块。
- **方式 B**（`user_mode_b`）：强调环境已注入 `move`、禁止自定义函数与多余语法；给出**合法代码形态示例**；要求输出 **```python** 代码块。

### 2.6 评分与汇总

- **核心逻辑**：`experiments/exp1_code_verify/evaluator.py`
  - `build_prompt_block(task)`：拼 ASCII 图 + 起终点 + JSON grid（供导出或在线构造请求）。
  - `grade_mode_a(task, raw)`：从文本中**启发式抽取**动作（中英文、逗号分隔、「向上 3 步」等）；在 `GridEnv` 上逐步 `move`；判 `at_goal`。
  - `grade_mode_b(task, raw)`：`extract_python_code` 取**最后一个** fenced 代码块（避免模型复述示例时误抓）；`exec_user_code`；判 `at_goal`。
- **批量读模型输出**：`experiments/exp1_code_verify/grade_jsonl.py`  
  - 输入 jsonl 每行：`{"task_id","mode","raw"}`，`mode` 为 `a` 或 `b`。  
  - `--verbose` / `-v`：逐条打印 `reason`（如 `ok`、`not_at_goal`、`unsafe_or_invalid:...`、`runtime_error:...`）。

### 2.7 API 批跑与工程辅助

- **导出全部 SYSTEM/user 文本**：`dump_prompts.py` → `prompt_dump/`。
- **OpenAI 兼容接口批跑**（百炼 / NVIDIA 等）：`bailian_batch_from_dump.py` + `config.json`（`api_key_env`、`base_url`、`model`、`request_timeout_seconds` 等）。
- **进度条**：优先 `tqdm`，否则 ASCII 条；`--no-progress` 可关。
- **柱状图（示例）**：`plot_bar.py`（需 `matplotlib`）。

### 2.8 实验一局限（写进论文「讨论」更合适）

1. **任务规模**：当前 **N=10**，适合预实验；正式结论需扩题或分层（易/难）。
2. **方式 A**：自动解析**不能覆盖**所有自然语言变体；重要工作可**人工抽检**与 `reason` 对照。
3. **方式 B**：沙箱**刻意偏严**；模型常倾向写完整程序，需**强提示**（已在 `prompts.py` 加强）才能与协议对齐。
4. **模态**：当前主要为**文本态地图**（ASCII + JSON）；若强调 VLM，需补**渲染图**或真实游戏帧，并在文中单独说明。
5. **与「推箱子」**：本网格任务为**寻径**；完整 Sokoban 推箱子在 `src/sokoban/`，复杂度更高，需另设实验。

### 2.9 实验一：示例结果（单次跑批，仅供参考）

以下为对话中**一次** `grade_jsonl.py -v` 的汇总（模型与温度以你当时 `config` 为准）：

**汇总准确率**

| 模式 | 正确率 | 说明 |
|------|--------|------|
| **mode_a** | **0.10** | 10 题中约 1 题解析+执行后到达终点。 |
| **mode_b** | **0.20** | 10 题中约 2 题沙箱执行后到达终点。 |

**逐题明细（摘录逻辑）**

- **双对**：`t01` 的 A、B 均为 `ok`；`t08` 的 B 为 `ok`。
- **多数未到达**：大量 `not_at_goal`（A）或 `executed_but_not_at_goal`（B）——代码能跑通但路径错误，或文本规划错误。
- **异常样本**：如 `t05` 的 B 出现 **`SyntaxError`（超长未闭合字符串等）**——属输出质量失败，非沙箱误杀。

**解读提示**：该次结果**支持「B 略高于 A」的方向**，但绝对准确率仍低，更宜配合**更强模型 / 更大 N / 分层难度**再下结论；并与「协议对齐后 B 可跑通」的工程现象一并报告。

---

## 三、实验二（exp2）：详细设计

### 3.1 研究问题与假设（H2）

- **问题**：在任务类型固定时，给模型**结构化技能模板**（仅填参数）是否比**从零写代码**显著减少**生成 token**？
- **操作化主指标**：OpenAI 兼容 API 返回的 **`usage.completion_tokens`**。
- **辅助质量指标**：复用实验一的 **`grade_mode_b`**，得到 **`reach_goal`**，避免「变短但全错」。

### 3.2 为何任务选「全空地 5×5」

- **同一类任务**：仅 **起点/终点** 变，`grid` 全 **0**，保证存在**无墙曼哈顿路径**。
- **技能可声明「恒适用」**：技能模板为「先完成全部纵向 `move`，再完成全部横向 `move`」，方向按 `(start, goal)` **预先算好**，模型主要填两个 **`range` 的非负整数**（含 0）。
- **隔离变量**：比较的是**信息是否以技能形式给出**，而非地图是否存在多种拓扑技巧。

### 3.3 自变量：两种 user 构造

- **实现**：`experiments/exp2_skill_reuse/prompts_exp2.py`
- **共用**：通过 `exp1_code_verify.evaluator.build_prompt_block` 生成与实验一**同构**的地图块（ASCII + JSON + 起终点）。
- **从零（scratch）**：在 block 上追加「**未提供技能模板**」，要求只输出 ```python。
- **技能（skill）**：追加 **版本化技能段** `SKILL_VERSION=v1`：给出已定向的两行骨架  
  `for i in range(____): move("…")` ×2，要求只填数字、只输出一个代码块。
- **独立 SYSTEM**（`prompts_exp2.SYSTEM`）：再次声明 `move`/沙箱协议，与实验一 B 一致。

### 3.4 流程、配对与顺序控制

- **脚本**：`experiments/exp2_skill_reuse/run_exp2_tokens.py`
- **对每个 `task_id`**：各调用 **1 次 scratch + 1 次 skill**，共 **40 次**请求（20 题 × 2）。
- **顺序**：每个任务内 **scratch/skill 先后随机**，`random_seed` 写入 `config.json` 可**复现**。
- **输出**：`exp2_results.jsonl`，每条含：`task_id`、`condition`、`order_plan`、`skill_version`、`model`、`prompt_tokens`、`completion_tokens`、`total_tokens`、`raw`、（若开启）`reach_goal`、`grade_reason`。

### 3.5 汇总统计

- **脚本**：`experiments/exp2_skill_reuse/summarize_exp2.py`
- **配对**：按 `task_id` 合并 scratch 与 skill，计算：
  - 各条件 **completion_tokens** 均值、标准差；
  - **配对差** `scratch − skill` 的均值；
  - `skill / scratch` 的 completion 比例；
  - 若有 `reach_goal`，报告两种条件的**到达率**。

### 3.6 实验二局限

1. **技能很强、很具体**：当前技能几乎把解法空间**收缩到两行**，completion 极低在预期内；泛化到「技能库检索 + 多技能选择」需 **v2** 设计。
2. **从零侧方差可能极大**：若模型偶发**长篇重复**，会拉高 **mean / stdev**；正式报告建议补充**中位数、分位数**或**截尾稳健统计**。
3. **总成本**：技能增长 **prompt_tokens**；若论「端到端账单」需显式报告 **total_tokens**。

### 3.7 实验二：示例结果（单次跑批，仅供参考）

以下为对话中**一次** `summarize_exp2.py --input exp2_results.jsonl` 的输出：

```json
{
  "n_pairs": 20,
  "completion_tokens_mean_scratch": 3201.2,
  "completion_tokens_mean_skill": 26.05,
  "completion_tokens_stdev_scratch": 3897.02,
  "completion_tokens_stdev_skill": 0.22,
  "paired_mean_scratch_minus_skill": 3175.15,
  "skill_rate_vs_scratch_completion": 0.0081,
  "reach_goal_rate_scratch": 0.1,
  "reach_goal_rate_skill": 0.35
}
```

**简要解读**

- **生成长度**：技能侧平均 completion 约为从零侧的 **~0.81%**；配对平均**少约 3175 completion tokens**（量级上极强支持 H2 的「更省生成」）。
- **稳定性**：从零侧 **标准差极大**，技能侧几乎常数长度——报告时需讨论**异常长回复**对均值的影响。
- **任务完成**：技能侧 **reach_goal 率（0.35）高于从零侧（0.1）**，说明至少在该次跑批中**不是**「更短但更差」单故事。

---

## 四、可复现命令索引

### 实验一

```text
cd experiments/exp1_code_verify
python validate_tasks.py
python dump_prompts.py --out prompt_dump
# 配置 API 后：
python bailian_batch_from_dump.py --config config.json
python grade_jsonl.py --input model_outputs.jsonl --out graded.jsonl -v
```

### 实验二

```text
cd experiments/exp2_skill_reuse
copy config.example.json config.json   # 按需改 base_url / model
python run_exp2_tokens.py --config config.json
python summarize_exp2.py --input exp2_results.jsonl
```

---

## 五、文件路径速查

| 内容 | 路径 |
|------|------|
| 实验一任务 | `experiments/exp1_code_verify/tasks.json` |
| 实验一环境/沙箱/评分 | `env.py`、`sandbox.py`、`evaluator.py` |
| 实验一提示 | `prompts.py` |
| 实验一批跑 | `bailian_batch_from_dump.py`、`dump_prompts.py` |
| 实验一任务校验 | `validate_tasks.py` |
| 实验二任务 | `experiments/exp2_skill_reuse/tasks.json` |
| 实验二提示 | `experiments/exp2_skill_reuse/prompts_exp2.py` |
| 实验二跑批与汇总 | `run_exp2_tokens.py`、`summarize_exp2.py` |
| 实验二设计草稿 | `experiments/exp2_skill_reuse/DESIGN_CN.md` |

---

## 六、版本与维护

- 实验一技能段落、实验二 **`SKILL_VERSION`** 变更时，应在论文/附录中**注明版本号**，并**重新跑批**更新结果表。
- 本文档中的**示例数值**不随 CI 自动更新；以你本地最新 `model_outputs.jsonl` / `exp2_results.jsonl` 为准。

---

## 七、时间紧、未跑大规模批批时：你「手里有什么」与启研计划怎么写

### 7.1 现在仍然成立、可直接写进启研/开题材料的内容

| 类型 | 说明 |
|------|------|
| **问题与假设** | **H1**（代码执行作过程验证信号）、**H2**（技能模板降生成量）；若涉及迁移再加 **H3**（游戏式协议 → 图表/表格文本呈现），见下。 |
| **方法与设计** | 本文 **§2–§3** 的自变量、沙箱协议、指标定义、局限与讨论点；**可复现**（代码路径、校验脚本、评分逻辑）。 |
| **小规模预实验结果** | **§2.9、§3.7** 的表格与 JSON：**明确标注**为「单次 API 跑批、N=10 / N=20 **预实验**」，**不作为正式统计结论**，只作**可行性/趋势示意**。 |
| **工程与扩展** | 仓库内已具备：`scripts/generate_exp1_tasks.py`、`generate_exp2_tasks.py`、`run_overnight_123.sh`、实验三目录 `exp3_chart_transfer/`（设计见 `DESIGN_CN.md`）。未跑完或未跑通时，在计划里写「**正式数据待 N 扩大后补全**」即可。 |

### 7.2 实验三（H3）与本文档关系

- **设计说明**：`experiments/exp3_chart_transfer/DESIGN_CN.md`（图表/表格 ASCII + JSON，A/B 与 H1 同构）。  
- **尚未并入**上文 §一 表格：若开题需要三条假设并列，可从该文件摘 1 段「研究问题 + 指标」放进计划正文，并注明「**实现已完成，统计待跑**」。

### 7.3 启研计划正文建议结构（你可按需删减）

1. **背景与意义**：游戏/交互环境中「规划可执行、可验证」；连接到代码作为过程信号、技能复用、向视觉推理任务迁移。  
2. **研究目标**：验证 H1/H2（必选）；H3 可作为**拓展目标**或第二阶段。  
3. **研究内容与技术路线**：网格环境 + 受限沙箱 + 自动评分；实验二在固定代码范式下比较技能提示；实验三同构协议到读表/读柱。  
4. **已有基础**：原型代码与 **N=10/20 预实验**（引用本文 §2.9、§3.7，写清模型与日期可选）。  
5. **工作计划**：例如「扩大任务集与重复跑批 → 报告均值/置信区间或分层难度 → 可选补多模态输入」。  
6. **预期成果**：可复现实验协议 + 指标对比表 + 讨论局限（本文 §2.8、§3.6 可直接改编）。  

**不必**把未完成的大规模 `*_overnight.jsonl` 写进计划当作「已完成结果」；若某次夜间跑**部分完成**，可写「已获得中间日志，待整理」并**以文件时间戳为准**。

---

*文档生成说明：根据仓库当前实现与用户一次示例跑批整理；若你之后升级 `summarize_exp2.py`（如增加中位数），可在本节附录自行粘贴新表。*
