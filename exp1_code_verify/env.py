"""极简网格世界：用于实验一（代码执行 vs 纯文本动作）。"""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass
class GridEnv:
    """grid[r][c]：0 空地，1 墙。坐标为 (行, 列)。"""

    grid: List[List[int]]
    start: Tuple[int, int]
    goal: Tuple[int, int]

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

    def move(self, direction: str) -> bool:
        d = str(direction).strip().lower()
        if d not in DIR_MAP:
            # 允许中文不 lower
            d = str(direction).strip()
        if d not in DIR_MAP:
            raise ValueError(f"unknown direction: {direction!r}")
        dr, dc = DIR_MAP[d]
        nr, nc = self.player_r + dr, self.player_c + dc
        if not (0 <= nr < self.rows and 0 <= nc < self.cols):
            return False
        if self.grid[nr][nc] == 1:
            return False
        self.player_r, self.player_c = nr, nc
        return True

    def at_goal(self) -> bool:
        return (self.player_r, self.player_c) == (
            int(self.goal[0]),
            int(self.goal[1]),
        )

    def ascii_map(self, mark_path: List[Tuple[int, int]] | None = None) -> str:
        marks = set(mark_path or [])
        lines = []
        for r in range(self.rows):
            row = []
            for c in range(self.cols):
                if self.grid[r][c] == 1:
                    ch = "#"
                elif (r, c) == (int(self.goal[0]), int(self.goal[1])):
                    ch = "G"
                elif (r, c) == (int(self.start[0]), int(self.start[1])):
                    ch = "S"
                else:
                    ch = "."
                if (r, c) in marks:
                    ch = "*"
                row.append(ch)
            lines.append("".join(row))
        pr, pc = self.player_r, self.player_c
        line = list(lines[pr])
        if self.grid[pr][pc] != 1:
            line[pc] = "P"
        lines[pr] = "".join(line)
        return "\n".join(lines)
