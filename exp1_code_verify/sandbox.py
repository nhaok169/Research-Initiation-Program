"""对模型生成的 Python 片段做受限执行（仅允许 move 与 range 循环）。"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from env import GridEnv


class UnsafeCodeError(ValueError):
    pass


def _is_int_constant(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, int)


def _check_range_call(call: ast.Call) -> None:
    if not isinstance(call.func, ast.Name) or call.func.id != "range":
        raise UnsafeCodeError("only range(...) is allowed as for-loop iterator")
    if call.keywords:
        raise UnsafeCodeError("range() does not support keyword arguments")
    for a in call.args:
        if not _is_int_constant(a):
            raise UnsafeCodeError("range() arguments must be integer literals")


def _check_move_call(call: ast.Call) -> None:
    if not isinstance(call.func, ast.Name) or call.func.id != "move":
        raise UnsafeCodeError("only move(...) calls are allowed as statements")
    if len(call.args) != 1 or not isinstance(call.args[0], ast.Constant):
        raise UnsafeCodeError('move() requires one string literal, e.g. move("up")')
    if not isinstance(call.args[0].value, str):
        raise UnsafeCodeError('move() requires one string literal, e.g. move("up")')


def _check_stmt(stmt: ast.stmt) -> None:
    if isinstance(stmt, ast.For):
        _check_range_call(stmt.iter)
        for s in stmt.body:
            _check_stmt(s)
        if stmt.orelse:
            raise UnsafeCodeError("for-else is not allowed")
        return
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        _check_move_call(stmt.value)
        return
    raise UnsafeCodeError(f"disallowed statement: {type(stmt).__name__}")


def _check_module(tree: ast.Module) -> None:
    for stmt in tree.body:
        _check_stmt(stmt)


def exec_user_code(code: str, env: GridEnv) -> None:
    tree = ast.parse(code, mode="exec")
    if not isinstance(tree, ast.Module):
        raise UnsafeCodeError("only module code is allowed")
    _check_module(tree)
    safe_builtins = {"range": range}
    g = {"__builtins__": safe_builtins, "move": env.move}
    exec(compile(tree, "<model>", "exec"), g, g)
