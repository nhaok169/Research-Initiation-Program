"""复制到 Qwen2.5-VL API 的 system/user 模板（实验一）。"""

SYSTEM_SHARED = (
    "你是网格导航助手。坐标一律为 (行,列)，先行后列；行号向下增大，列号向右增大。"
    "合法移动：up/down/left/right（或 上/下/左/右）。撞墙或越界则该步无效（不会移动）。"
    "你必须严格依据给定的 grid（0 空地，1 墙）与起点、终点作答。"
)


def user_mode_a(block: str) -> str:
    return (
        block
        + "\n【方式 A】请只用自然语言给出从起点到终点的移动步骤，"
        "例如：先向上走 3 步，再向右走 4 步；或列出动作序列如：上,上,上,右,右,右,右。"
        "不要写代码，不要写 markdown 代码块。"
    )


def user_mode_b(block: str) -> str:
    example = (
        "\n【方式 B — 必须严格遵守，否则判 0 分】\n"
        "评测器已在沙箱里注入 **move(\"up\"|\"down\"|\"left\"|\"right\")**（无参数、无返回值，只改变角色位置）。\n"
        "**禁止**：def / class / import / print / while / if（除隐含在 for 外）/ 赋值 / 自己重新定义 move / "
        "除 range 以外的任何函数调用。\n"
        "**只允许** 两种顶层语句，且只能写在 ```python 代码块里，不要解释：\n"
        "  1) move(\"down\")  这种单行调用，方向必须是英文小写字符串常量；\n"
        "  2) for _ in range(3): move(\"up\")  其中 range( ) 里必须是 **正整数常量**（不要用变量）。\n"
        "可写多行、多个 for。下面是一个合法示例（若你的路径不同请改数字与方向，但格式必须同类）：\n"
        "```python\n"
        "for i in range(4):\n"
        "    move(\"down\")\n"
        "for i in range(4):\n"
        "    move(\"right\")\n"
        "```\n"
    )
    return block + example
