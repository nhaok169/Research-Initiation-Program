"""实验三：受限 `ans = <expr>` 代码执行与可诊断错误分析。"""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from typing import Any, Optional, Sequence, Union


Number = Union[int, float]


class UnsafeCodeError(ValueError):
    pass


@dataclass
class DiagnosticError(Exception):
    bucket: str
    code: str
    message: str
    line: int | None = None
    col: int | None = None
    end_line: int | None = None
    end_col: int | None = None
    fragment: str | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "error_bucket": self.bucket,
            "error_code": self.code,
            "diagnostic_message": self.message,
            "line": self.line,
            "col": self.col,
            "end_line": self.end_line,
            "end_col": self.end_col,
            "fragment": self.fragment,
            "precise_location": self.line is not None and self.col is not None,
        }


@dataclass
class Diagnosis:
    ok: bool
    answer: Any = None
    error: DiagnosticError | None = None


def _node_fragment(source: str, node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        frag = ast.get_source_segment(source, node)
    except Exception:
        frag = None
    return frag.strip() if isinstance(frag, str) and frag.strip() else None


def _node_meta(source: str, node: ast.AST | None) -> dict[str, Any]:
    if node is None:
        return {
            "line": None,
            "col": None,
            "end_line": None,
            "end_col": None,
            "fragment": None,
        }
    return {
        "line": getattr(node, "lineno", None),
        "col": getattr(node, "col_offset", None),
        "end_line": getattr(node, "end_lineno", None),
        "end_col": getattr(node, "end_col_offset", None),
        "fragment": _node_fragment(source, node),
    }


def _raise_diag(bucket: str, code: str, source: str, node: ast.AST | None, message: str) -> None:
    meta = _node_meta(source, node)
    raise DiagnosticError(bucket=bucket, code=code, message=message, **meta)


def _as_index(v: Any, source: str, node: ast.AST) -> int:
    if isinstance(v, bool):
        _raise_diag("runtime_error", "invalid_index_type", source, node, "索引不能是布尔值。")
    if isinstance(v, int):
        return v
    if isinstance(v, float) and float(v).is_integer():
        return int(v)
    _raise_diag("runtime_error", "invalid_index_type", source, node, f"索引必须是整数，实际得到 {v!r}。")


def _check_subscript(node: ast.Subscript, allow_table: bool, source: str) -> None:
    slices: list[ast.AST] = []
    cur: ast.AST = node
    while isinstance(cur, ast.Subscript):
        slices.append(cur.slice)
        cur = cur.value
    if not isinstance(cur, ast.Name):
        _raise_diag("syntax_or_rule_error", "bad_subscript_root", source, node, "下标链必须从 series 或 table 开始。")
    root = cur.id
    if root == "series":
        pass
    elif root == "table":
        if not allow_table:
            _raise_diag("syntax_or_rule_error", "table_unavailable", source, node, "本题没有 table，不能使用 table[...]。")
    else:
        _raise_diag("syntax_or_rule_error", "bad_subscript_root", source, node, "只允许 series[...] 或 table[r][c]。")
    if len(slices) != (2 if root == "table" else 1):
        _raise_diag("syntax_or_rule_error", "bad_subscript_arity", source, node, "series 只能有 1 个下标，table 必须有 2 个下标。")
    for sl in slices:
        if isinstance(sl, ast.Slice):
            _raise_diag("syntax_or_rule_error", "slice_not_allowed", source, sl, "不允许使用切片。")
        _check_expr(sl, allow_table, source)


def _check_call(node: ast.Call, allow_table: bool, source: str) -> None:
    if node.keywords:
        _raise_diag("syntax_or_rule_error", "keyword_not_allowed", source, node, "不允许关键字参数。")
    if not isinstance(node.func, ast.Name):
        _raise_diag("syntax_or_rule_error", "complex_call_not_allowed", source, node, "只允许简单函数名调用。")
    name = node.func.id
    args = node.args

    if name in ("len", "abs", "int", "float"):
        if len(args) != 1:
            _raise_diag("syntax_or_rule_error", f"{name}_arity", source, node, f"{name} 需要 1 个参数。")
        if name == "len":
            if not isinstance(args[0], ast.Name) or args[0].id not in {"series", "table"}:
                _raise_diag("syntax_or_rule_error", "len_arg_invalid", source, args[0], "len 只允许用于 len(series) 或 len(table)。")
        else:
            _check_expr(args[0], allow_table, source)
        return
    if name in ("max", "min"):
        if len(args) != 2:
            _raise_diag("syntax_or_rule_error", f"{name}_arity", source, node, f"{name} 需要 2 个参数。")
        for a in args:
            _check_expr(a, allow_table, source)
        return
    if name in ("argmax", "argmin", "sum_series", "max_series", "min_series"):
        if len(args) != 1 or not isinstance(args[0], ast.Name) or args[0].id != "series":
            _raise_diag("syntax_or_rule_error", f"{name}_arg_invalid", source, node, f"{name} 只允许写成 {name}(series)。")
        return
    if name in ("row_sum", "col_sum"):
        if not allow_table:
            _raise_diag("syntax_or_rule_error", f"{name}_needs_table", source, node, f"{name} 仅用于表格题。")
        if len(args) != 2 or not isinstance(args[0], ast.Name) or args[0].id != "table":
            _raise_diag("syntax_or_rule_error", f"{name}_arg_invalid", source, node, f"{name} 只允许写成 {name}(table, 整数字面量)。")
        if not isinstance(args[1], ast.Constant) or not isinstance(args[1].value, int):
            _raise_diag("syntax_or_rule_error", f"{name}_index_not_literal", source, args[1], f"{name} 的第二个参数必须是整数字面量。")
        return
    if name in ("argmax_row", "argmax_col"):
        if not allow_table:
            _raise_diag("syntax_or_rule_error", f"{name}_needs_table", source, node, f"{name} 仅用于表格题。")
        if len(args) != 1 or not isinstance(args[0], ast.Name) or args[0].id != "table":
            _raise_diag("syntax_or_rule_error", f"{name}_arg_invalid", source, node, f"{name} 只允许写成 {name}(table)。")
        return
    _raise_diag("syntax_or_rule_error", "disallowed_call", source, node, f"不允许调用函数 {name}。")


def _check_expr(node: ast.AST, allow_table: bool, source: str) -> None:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return
        _raise_diag("syntax_or_rule_error", "bad_literal", source, node, "表达式里只允许 int/float 字面量。")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        _check_expr(node.operand, allow_table, source)
        return
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod)):
        _check_expr(node.left, allow_table, source)
        _check_expr(node.right, allow_table, source)
        return
    if isinstance(node, ast.Subscript):
        _check_subscript(node, allow_table, source)
        return
    if isinstance(node, ast.Call):
        _check_call(node, allow_table, source)
        return
    if isinstance(node, ast.Name):
        _raise_diag("syntax_or_rule_error", "bare_name_not_allowed", source, node, "表达式里不允许裸变量名；请使用函数调用或下标访问。")
    _raise_diag("syntax_or_rule_error", "disallowed_expr", source, node, f"不允许的表达式类型：{type(node).__name__}。")


def _check_module(tree: ast.Module, allow_table: bool, source: str) -> ast.Assign:
    if len(tree.body) != 1:
        _raise_diag("syntax_or_rule_error", "top_level_stmt_count", source, tree, "必须且只能有 1 条顶层语句。")
    stmt = tree.body[0]
    if not isinstance(stmt, ast.Assign):
        _raise_diag("syntax_or_rule_error", "not_assignment", source, stmt, "唯一允许的语句是 ans = <expr>。")
    if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
        _raise_diag("syntax_or_rule_error", "bad_assignment_target", source, stmt, "只允许单目标赋值给 ans。")
    if stmt.targets[0].id != "ans":
        _raise_diag("syntax_or_rule_error", "assignment_target_not_ans", source, stmt.targets[0], '赋值目标必须是 "ans"。')
    _check_expr(stmt.value, allow_table, source)
    return stmt


def _eval_subscript(node: ast.Subscript, ctx: dict[str, Any], source: str) -> Any:
    slices: list[ast.AST] = []
    cur: ast.AST = node
    while isinstance(cur, ast.Subscript):
        slices.append(cur.slice)
        cur = cur.value
    assert isinstance(cur, ast.Name)
    root = cur.id
    idx_nodes = list(reversed(slices))
    if root == "series":
        idx = _as_index(_eval_expr(idx_nodes[0], ctx, source), source, idx_nodes[0])
        series = ctx["series"]
        if not (0 <= idx < len(series)):
            _raise_diag("runtime_error", "index_out_of_range", source, idx_nodes[0], f"series[{idx}] 越界；合法范围是 [0, {len(series) - 1}]。")
        return series[idx]
    table = ctx["table"]
    r = _as_index(_eval_expr(idx_nodes[0], ctx, source), source, idx_nodes[0])
    c = _as_index(_eval_expr(idx_nodes[1], ctx, source), source, idx_nodes[1])
    if not (0 <= r < len(table)):
        _raise_diag("runtime_error", "row_out_of_range", source, idx_nodes[0], f"table 的行索引 {r} 越界；合法范围是 [0, {len(table) - 1}]。")
    cols = len(table[0]) if table else 0
    if not (0 <= c < cols):
        _raise_diag("runtime_error", "col_out_of_range", source, idx_nodes[1], f"table 的列索引 {c} 越界；合法范围是 [0, {cols - 1}]。")
    return table[r][c]


def _call_allowed(name: str, args: list[Any], node: ast.Call, ctx: dict[str, Any], source: str) -> Any:
    series = ctx["series"]
    table = ctx["table"]
    if name == "len":
        target = node.args[0]
        if isinstance(target, ast.Name) and target.id == "series":
            return len(series)
        return len(table)
    if name == "abs":
        return abs(args[0])
    if name == "int":
        return int(args[0])
    if name == "float":
        return float(args[0])
    if name == "max":
        return max(args[0], args[1])
    if name == "min":
        return min(args[0], args[1])
    if name == "argmax":
        return max(range(len(series)), key=lambda i: series[i])
    if name == "argmin":
        return min(range(len(series)), key=lambda i: series[i])
    if name == "sum_series":
        return sum(series)
    if name == "max_series":
        return max(series)
    if name == "min_series":
        return min(series)
    if name == "row_sum":
        r = int(args[1])
        if not (0 <= r < len(table)):
            _raise_diag("runtime_error", "row_out_of_range", source, node.args[1], f"row_sum 的行索引 {r} 越界；合法范围是 [0, {len(table) - 1}]。")
        return sum(table[r])
    if name == "col_sum":
        cols = len(table[0]) if table else 0
        c = int(args[1])
        if not (0 <= c < cols):
            _raise_diag("runtime_error", "col_out_of_range", source, node.args[1], f"col_sum 的列索引 {c} 越界；合法范围是 [0, {cols - 1}]。")
        return sum(row[c] for row in table)
    if name == "argmax_row":
        sums = [sum(row) for row in table]
        return max(range(len(sums)), key=lambda i: sums[i])
    if name == "argmax_col":
        cols = len(table[0]) if table else 0
        best_c = 0
        best_v = float("-inf")
        for c in range(cols):
            v = sum(row[c] for row in table)
            if v > best_v:
                best_v = v
                best_c = c
        return best_c
    _raise_diag("runtime_error", "unknown_runtime_call", source, node, f"运行时遇到未支持的调用 {name}。")


def _eval_expr(node: ast.AST, ctx: dict[str, Any], source: str) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_expr(node.operand, ctx, source)
    if isinstance(node, ast.BinOp):
        left = _eval_expr(node.left, ctx, source)
        right = _eval_expr(node.right, ctx, source)
        try:
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.FloorDiv):
                return left // right
            if isinstance(node.op, ast.Mod):
                return left % right
        except ZeroDivisionError:
            _raise_diag("runtime_error", "zero_division", source, node.right, "出现除以 0。")
    if isinstance(node, ast.Subscript):
        return _eval_subscript(node, ctx, source)
    if isinstance(node, ast.Call):
        name = node.func.id if isinstance(node.func, ast.Name) else "?"
        args = []
        if name == "len":
            args = [None]
        else:
            args = [_eval_expr(a, ctx, source) for a in node.args]
        try:
            return _call_allowed(name, args, node, ctx, source)
        except DiagnosticError:
            raise
        except Exception as e:
            _raise_diag("runtime_error", type(e).__name__, source, node, f"运行时错误：{type(e).__name__}: {e}")
    if isinstance(node, ast.Name):
        if node.id == "series":
            return ctx["series"]
        if node.id == "table":
            return ctx["table"]
    _raise_diag("runtime_error", "eval_failed", source, node, f"无法执行表达式类型 {type(node).__name__}。")


def diagnose_answer_code(code: str, series: Sequence[Number], table: Optional[Sequence[Sequence[Number]]]) -> Diagnosis:
    source = code.strip()
    if not source:
        return Diagnosis(False, error=DiagnosticError("syntax_or_rule_error", "empty_code", "未提供任何代码。"))
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as e:
        return Diagnosis(
            False,
            error=DiagnosticError(
                "syntax_or_rule_error",
                "syntax_error",
                f"语法错误：{e.msg}",
                line=e.lineno,
                col=e.offset - 1 if e.offset else None,
                end_line=e.end_lineno,
                end_col=(e.end_offset - 1) if e.end_offset else None,
                fragment=(e.text or "").strip() or None,
            ),
        )
    allow_table = table is not None and len(table) > 0
    try:
        stmt = _check_module(tree, allow_table, source)
        ctx = {
            "series": [float(x) for x in series],
            "table": [list(map(float, row)) for row in table] if allow_table else [],
        }
        ans = _eval_expr(stmt.value, ctx, source)
        return Diagnosis(True, answer=ans)
    except DiagnosticError as e:
        return Diagnosis(False, error=e)


def exec_answer_code(code: str, series: Sequence[Number], table: Optional[Sequence[Sequence[Number]]]) -> Any:
    diag = diagnose_answer_code(code, series, table)
    if diag.ok:
        return diag.answer
    assert diag.error is not None
    if diag.error.bucket == "syntax_or_rule_error":
        raise UnsafeCodeError(diag.error.message)
    raise RuntimeError(diag.error.message)


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
