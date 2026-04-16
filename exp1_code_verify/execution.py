"""在 strict 网格环境下执行模型输出的代码，返回结构化结果（供闭环反馈）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from env import GridEnv, MoveExecutionError
from evaluator import extract_python_code
from sandbox import UnsafeCodeError, exec_user_code


@dataclass
class ExecuteResult:
    at_goal: bool
    error: str | None
    code: str


def execute(task: Dict[str, Any], model_raw: str) -> ExecuteResult:
    """解析 ```python```，在 strict GridEnv 中执行；失败时 error 为人类可读中文说明。"""
    env = GridEnv(
        task["grid"],
        tuple(task["start"]),
        tuple(task["goal"]),
        strict_move_errors=True,
    )
    env.reset()
    code = extract_python_code(model_raw)
    if not code.strip():
        return ExecuteResult(False, "未找到非空的 ```python``` 代码块；请只输出一个合法代码块。", code)
    try:
        exec_user_code(code, env)
    except UnsafeCodeError as e:
        return ExecuteResult(False, f"代码未通过安全校验（AST 白名单）：{e}", code)
    except MoveExecutionError as e:
        return ExecuteResult(False, str(e), code)
    except Exception as e:
        return ExecuteResult(
            False,
            f"执行失败：运行时错误 {type(e).__name__}: {e}",
            code,
        )
    if env.at_goal():
        return ExecuteResult(True, None, code)
    gr, gc = int(task["goal"][0]), int(task["goal"][1])
    return ExecuteResult(
        False,
        f"代码已完整执行且无异常，但未到达终点。"
        f"当前位置是({env.player_r},{env.player_c})，终点是({gr},{gc})。",
        code,
    )
