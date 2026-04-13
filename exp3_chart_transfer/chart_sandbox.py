"""实验三：受限 Python，仅允许 `ans = <expr>`，expr 内仅含白名单运算与注入函数。"""

from __future__ import annotations

import ast
import math
from typing import Any, List, Optional, Sequence, Tuple, Union


class UnsafeCodeError(ValueError):
    pass


Number = Union[int, float]


def _series_helpers(s: List[Number]) -> Tuple[Any, ...]:
    """s 必须与执行环境中注入的 series 为同一 list 对象（避免闭包与 globals 不一致）。"""

    def argmax(arr: Sequence[Number]) -> int:
        if arr is not s:
            raise ValueError("argmax only accepts series")
        return max(range(len(s)), key=lambda i: s[i])

    def argmin(arr: Sequence[Number]) -> int:
        if arr is not s:
            raise ValueError("argmin only accepts series")
        return min(range(len(s)), key=lambda i: s[i])

    def sum_series(arr: Sequence[Number]) -> Number:
        if arr is not s:
            raise ValueError("sum_series only accepts series")
        return sum(s)

    def max_series(arr: Sequence[Number]) -> Number:
        if arr is not s:
            raise ValueError("max_series only accepts series")
        return max(s)

    def min_series(arr: Sequence[Number]) -> Number:
        if arr is not s:
            raise ValueError("min_series only accepts series")
        return min(s)

    return argmax, argmin, sum_series, max_series, min_series


def _table_helpers(t: List[List[Number]]) -> Tuple[Any, ...]:
    """t 必须与执行环境中注入的 table 为同一对象。"""

    def row_sum(tbl: Any, r: int) -> Number:
        if tbl is not t:
            raise ValueError("row_sum only accepts table")
        return sum(t[int(r)])

    def col_sum(tbl: Any, c: int) -> Number:
        if tbl is not t:
            raise ValueError("col_sum only accepts table")
        cc = int(c)
        return sum(row[cc] for row in t)

    def argmax_row(tbl: Any) -> int:
        if tbl is not t:
            raise ValueError("argmax_row only accepts table")
        sums = [sum(row) for row in t]
        return max(range(len(sums)), key=lambda i: sums[i])

    def argmax_col(tbl: Any) -> int:
        if tbl is not t:
            raise ValueError("argmax_col only accepts table")
        if not t:
            return 0
        cols = len(t[0])
        best_c = 0
        best_v = float("-inf")
        for c in range(cols):
            v = sum(row[c] for row in t)
            if v > best_v:
                best_v = v
                best_c = c
        return best_c

    return row_sum, col_sum, argmax_row, argmax_col


def _check_subscript(node: ast.Subscript, allow_table: bool) -> None:
    slices: List[ast.AST] = []
    cur: ast.AST = node
    while isinstance(cur, ast.Subscript):
        slices.append(cur.slice)
        cur = cur.value
    if not isinstance(cur, ast.Name):
        raise UnsafeCodeError("subscript chain must start from series or table")
    root = cur.id
    if root == "series":
        pass
    elif root == "table":
        if not allow_table:
            raise UnsafeCodeError("table is not available in this task")
    else:
        raise UnsafeCodeError("only series[...] or table[...] subscripts are allowed")
    if len(slices) != (2 if root == "table" else 1):
        raise UnsafeCodeError("series uses one index; table uses two indices")
    for sl in slices:
        if isinstance(sl, ast.Slice):
            raise UnsafeCodeError("slices are not allowed")
        _check_expr(sl, allow_table, in_series_index=(root == "series"))


def _check_call(node: ast.Call, allow_table: bool) -> None:
    if node.keywords:
        raise UnsafeCodeError("keyword arguments are not allowed")
    fn = node.func
    if not isinstance(fn, ast.Name):
        raise UnsafeCodeError("only simple function names are allowed")
    name = fn.id
    args = node.args

    if name in ("len", "abs", "int", "float"):
        if len(args) != 1:
            raise UnsafeCodeError(f"{name} expects 1 argument")
        _check_expr(args[0], allow_table, in_series_index=False)
        return
    if name in ("max", "min"):
        if len(args) != 2:
            raise UnsafeCodeError(f"{name} expects 2 arguments")
        _check_expr(args[0], allow_table, in_series_index=False)
        _check_expr(args[1], allow_table, in_series_index=False)
        return
    if name in ("argmax", "argmin", "sum_series", "max_series", "min_series"):
        if len(args) != 1 or not isinstance(args[0], ast.Name) or args[0].id != "series":
            raise UnsafeCodeError(f"{name}(series) only")
        return
    if name in ("row_sum", "col_sum"):
        if not allow_table:
            raise UnsafeCodeError(f"{name} requires table tasks")
        if len(args) != 2 or not isinstance(args[0], ast.Name) or args[0].id != "table":
            raise UnsafeCodeError(f"{name}(table, int_literal) only")
        if not isinstance(args[1], ast.Constant) or not isinstance(args[1].value, int):
            raise UnsafeCodeError("row_sum/col_sum second arg must be int literal")
        return
    if name in ("argmax_row", "argmax_col"):
        if not allow_table:
            raise UnsafeCodeError(f"{name} requires table tasks")
        if len(args) != 1 or not isinstance(args[0], ast.Name) or args[0].id != "table":
            raise UnsafeCodeError(f"{name}(table) only")
        return
    raise UnsafeCodeError(f"disallowed call: {name}")


def _check_expr(node: ast.AST, allow_table: bool, in_series_index: bool) -> None:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return
        raise UnsafeCodeError("only int/float literals are allowed in expressions")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        _check_expr(node.operand, allow_table, in_series_index=False)
        return
    if isinstance(node, ast.BinOp) and isinstance(
        node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod)
    ):
        _check_expr(node.left, allow_table, in_series_index=False)
        _check_expr(node.right, allow_table, in_series_index=False)
        return
    if isinstance(node, ast.Subscript):
        _check_subscript(node, allow_table)
        return
    if isinstance(node, ast.Call):
        _check_call(node, allow_table)
        return
    if isinstance(node, ast.Name):
        if in_series_index and node.id == "series":
            raise UnsafeCodeError("series cannot be used as index")
        raise UnsafeCodeError("bare names are not allowed in expressions")
    raise UnsafeCodeError(f"disallowed expression: {type(node).__name__}")


def _check_module(tree: ast.Module, allow_table: bool) -> None:
    if len(tree.body) != 1:
        raise UnsafeCodeError("exactly one top-level statement is required")
    stmt = tree.body[0]
    if not isinstance(stmt, ast.Assign):
        raise UnsafeCodeError("only assignment to ans is allowed")
    if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
        raise UnsafeCodeError("only single target assignment")
    if stmt.targets[0].id != "ans":
        raise UnsafeCodeError('assignment target must be "ans"')
    _check_expr(stmt.value, allow_table, in_series_index=False)


def exec_answer_code(
    code: str,
    series: Sequence[Number],
    table: Optional[Sequence[Sequence[Number]]],
) -> Any:
    tree = ast.parse(code, mode="exec")
    if not isinstance(tree, ast.Module):
        raise UnsafeCodeError("only module code is allowed")
    allow_table = table is not None and len(table) > 0
    _check_module(tree, allow_table)

    s: List[Number] = list(series)
    argmax, argmin, sum_series, max_series, min_series = _series_helpers(s)
    safe_builtins = {"len": len, "max": max, "min": min, "abs": abs, "int": int, "float": float}
    g: dict[str, Any] = {
        "__builtins__": safe_builtins,
        "series": s,
        "ans": None,
        "argmax": argmax,
        "argmin": argmin,
        "sum_series": sum_series,
        "max_series": max_series,
        "min_series": min_series,
    }
    if allow_table:
        t: List[List[Number]] = [list(row) for row in table or []]
        row_sum, col_sum, argmax_row, argmax_col = _table_helpers(t)
        g["table"] = t
        g["row_sum"] = row_sum
        g["col_sum"] = col_sum
        g["argmax_row"] = argmax_row
        g["argmax_col"] = argmax_col
    else:
        g["table"] = None
    exec(compile(tree, "<model>", "exec"), g, g)
    return g.get("ans")


def answers_match(gold: Number, got: Any, tol: float = 1e-6) -> bool:
    if got is None:
        return False
    try:
        gf = float(gold)
        gv = float(got)
    except (TypeError, ValueError):
        return False
    if isinstance(gold, int) and isinstance(got, (int, float)) and float(got).is_integer():
        return int(got) == int(gold)
    return math.isclose(gf, gv, rel_tol=tol, abs_tol=tol)
