"""极简网格世界：用于实验一（受限代码 + 沙箱执行）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple


DIR_MAP = {
    "up": (-1, 0),
    "u": (-1, 0),
    "上": (-1, 0),
    "down": (1, 0),
    "d": (1, 0),
    "下": (1, 0),
    "left": (0, -1),
    "l": (0, -1),
    "左": (0, -1),
    "right": (0, 1),
    "r": (0, 1),
    "右": (0, 1),
}

DIR_CN = {"up": "上", "down": "下", "left": "左", "right": "右"}


class MoveExecutionError(RuntimeError):
    """strict_move_errors 模式下，撞墙/越界等可诊断失败。"""


@dataclass
class GridEnv:
    """grid[r][c]：0 空地，1 墙。坐标为 (行, 列)。"""

    grid: List[List[int]]
    start: Tuple[int, int]
    goal: Tuple[int, int]
    strict_move_errors: bool = False
    _step_num: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.rows = len(self.grid)
        self.cols = len(self.grid[0]) if self.rows else 0
        self.player_r, self.player_c = int(self.start[0]), int(self.start[1])
        self._validate_cell(self.player_r, self.player_c, "start")
        gr, gc = int(self.goal[0]), int(self.goal[1])
        self._validate_cell(gr, gc, "goal")
        if self.grid[self.player_r][self.player_c] == 1:
            raise ValueError("start on wall")
        if self.grid[gr][gc] == 1:
            raise ValueError("goal on wall")

    def _validate_cell(self, r: int, c: int, name: str) -> None:
        if not (0 <= r < self.rows and 0 <= c < self.cols):
            raise ValueError(f"{name} out of bounds: ({r},{c})")

    def reset(self) -> None:
        self.player_r, self.player_c = int(self.start[0]), int(self.start[1])
        self._step_num = 0

    def move(self, direction: str) -> bool:
        self._step_num += 1
        step = self._step_num
        d_raw = str(direction).strip()
        d = d_raw.lower() if d_raw.lower() in DIR_MAP else d_raw
        if d not in DIR_MAP:
            msg = (
                f"执行失败：第{step}步使用了非法方向 {direction!r}，"
                f"必须是 up/down/left/right（或 上/下/左/右）。"
                f"当前位置是({self.player_r},{self.player_c})。"
            )
            if self.strict_move_errors:
                raise MoveExecutionError(msg)
            raise ValueError(f"unknown direction: {direction!r}")
        dr, dc = DIR_MAP[d]
        nr, nc = self.player_r + dr, self.player_c + dc
        dir_word = DIR_CN.get(d, d)
        if not (0 <= nr < self.rows and 0 <= nc < self.cols):
            msg = (
                f"执行失败：第{step}步试图向{dir_word}移动但越界了。"
                f"当前位置是({self.player_r},{self.player_c})，"
                f"目标格 ({nr},{nc}) 在网格外。"
            )
            if self.strict_move_errors:
                raise MoveExecutionError(msg)
            return False
        if self.grid[nr][nc] == 1:
            msg = (
                f"执行失败：第{step}步试图向{dir_word}移动但撞墙了。"
                f"当前位置是({self.player_r},{self.player_c})，"
                f"{dir_word}方是墙壁。"
            )
            if self.strict_move_errors:
                raise MoveExecutionError(msg)
            return False
        self.player_r, self.player_c = nr, nc
        return True

    def at_goal(self) -> bool:
        return (self.player_r, self.player_c) == (
            int(self.goal[0]),
            int(self.goal[1]),
        )
