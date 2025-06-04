import os
import sys
from pathlib import Path
from collections import deque
from collections.abc import Iterable
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from PIL.ImageFont import FreeTypeFont
from PIL.Image import Image as IMG
from typing import cast, TypedDict, Literal, Protocol, TypeGuard
from .linecard_parsing import parse_str

match sys.platform:
    case "win32":
        FONT_PATHS = [
            "C:/Windows/Fonts",
            f"{os.environ["LOCALAPPDATA"]}/Microsoft/Windows/Fonts",
        ]
    case "darwin":
        FONT_PATHS = ["/Library/Fonts"]
    case "linux":
        FONT_PATHS = ["/usr/share/fonts"]
    case _:
        FONT_PATHS = os.environ["LINECARD_FONT_PATH"].split(";")


def find_font(font_name: str, search_paths: Iterable[Path] = [Path(FONT_PATH) for FONT_PATH in FONT_PATHS]):
    def check_font(font_file: Path, font_name: str):
        suffix = font_file.suffix.lower()
        if not suffix.endswith((".ttf", ".otf", ".ttc")):
            return False
        if not font_name.lower() == font_file.stem.lower():
            return False
        try:
            TTFont(font_file, recalcBBoxes=False, recalcTimestamp=False, fontNumber=0)
        except:
            return False
        return True

    try:
        TTFont(font_name, recalcBBoxes=False, recalcTimestamp=False, fontNumber=0)
        return Path(font_name).absolute().as_posix()
    except:
        pass
    for search_path in search_paths:
        if not search_path.exists():
            continue
        for file in search_path.iterdir():
            if check_font(file, font_name):
                return file.absolute().as_posix()
    return None


def to_int(n: str | None):
    try:
        return int(n) if n else None
    except ValueError:
        pass


def line_wrap(line: str, width: int, font: FreeTypeFont, start: float = 0.0) -> str:
    """调整文字排版到指定宽度，并添加换行符

    Args:
        line (str): 待排版的文本,一般是
        width: 文字换行宽度
        font (FreeTypeFont): 字体
        start: 首行起始位置 default to 0.0

    Returns:
        str: 排版后的文本
    """

    text_x = start
    new_str = ""
    for char in line:
        if char == "\n":
            new_str += "\n"
            text_x = 0
        else:
            char_lenth = font.getlength(char)
            text_x += char_lenth
            if text_x > width:
                new_str += "\n" + char
                text_x = char_lenth
            else:
                new_str += char
    return new_str


def CropResize(img: IMG, size: tuple[int, int]) -> IMG:
    """
    修改图像尺寸
    """

    test_x = img.size[0] / size[0]
    test_y = img.size[1] / size[1]

    if test_x < test_y:
        width = img.size[0]
        height = size[1] * test_x
    else:
        width = size[0] * test_y
        height = img.size[1]

    center = (img.size[0] / 2, img.size[1] / 2)
    output = img.crop(
        (
            int(center[0] - width / 2),
            int(center[1] - height / 2),
            int(center[0] + width / 2),
            int(center[1] + height / 2),
        )
    )
    output = output.resize(size)
    return output


type ImageList = list[IMG]


class CanvasEffectHandler(Protocol):
    """图片蒙版效果处理器

    Args:
        canvas (IMG): 被处理的背景图片
        image (IMG): 被处理的前景图片
        padding (int): 图片边距
        x (int): image 起始像素 x 轴坐标
        y (int): image 起始像素 y 轴坐标

    Returns:
        None
    """

    def __call__(self, canvas: IMG, image: IMG, padding: int, x: int, y: int) -> None: ...


def info_splicing(
    info: ImageList,
    BG_path: str | Path | None = None,
    width: int = 880,
    padding: int = 20,
    spacing: int = 20,
    BG_type: str | CanvasEffectHandler = "GAUSS",
) -> IMG:
    """
    信息拼接
        info:信息图片列表
        bg_path:背景地址
    """

    height = padding
    for image in info:
        # x = image.size[0] if x < image.size[0] else x
        height += image.size[1]
        height += spacing * 2
    else:
        height = height - spacing + padding

    size = (width + padding * 2, height)
    if BG_path is not None and ((BG_path := Path(BG_path)) if isinstance(BG_path, str) else BG_path).exists():
        bg = Image.open(BG_path).convert("RGB")
        canvas = CropResize(bg, size)
    else:
        canvas = Image.new("RGB", size, "white")
        BG_type = "NONE"

    CanvasEffect: CanvasEffectHandler

    if isinstance(BG_type, str):
        if BG_type == "NONE":

            def BG(canvas: IMG, image: IMG, padding: int, x: int, y: int):
                canvas.paste(image, (padding, y), mask=image)

        elif BG_type.startswith("GAUSS"):
            arg = BG_type.split(":")
            if len(arg) > 1:
                try:
                    radius = int(arg[1])
                except ValueError:
                    radius = 4
            else:
                radius = 4

            def BG(canvas: IMG, image: IMG, padding: int, x: int, y: int):
                box = (padding, y, x + padding, y + image.size[1])
                region = canvas.crop(box)
                blurred_region = region.filter(ImageFilter.GaussianBlur(radius=radius))
                canvas.paste(blurred_region, box)
                canvas.paste(image, (padding, y), mask=image)

        else:

            def BG(canvas: IMG, image: IMG, padding: int, x: int, y: int):
                colorBG = Image.new("RGBA", (x, image.size[1]), BG_type)
                canvas.paste(colorBG, (padding, y), mask=colorBG)
                canvas.paste(image, (padding, y), mask=image)

        CanvasEffect = BG
    else:
        CanvasEffect = BG_type

    height = padding

    for image in info:
        CanvasEffect(canvas, image, padding, width, height)
        height += image.size[1] + spacing * 2

    return canvas


class Linecard:
    """
    文本标记
        ----:横线
        [left]靠左
        [right]靠右
        [center]居中
        [pixel 400]指定像素
        [font size = 50,name = simsun,color = red,highlight = yellow]指定文本格式
        [style **kwargs] 控制参数
            height: 行高
            width: 行宽
            color: 本行颜色
        [nowrap]不换行
        [passport]保持标记
        [autowrap]自动换行
        [noautowrap]不自动换行
    """

    def __init__(self, font_name: str, fallback: list[str], sizes: Iterable[int] | None = None) -> None:
        path = find_font(font_name)
        if not path:
            raise ValueError(f"Font:{font_name} not found")
        self.font_path = path
        self.font_cache: dict[str, dict[int, ImageFont.FreeTypeFont]] = {}
        self.font_cache = {}
        fallback_paths: list[str] = [path for font in fallback if (path := find_font(font))]
        self.cmaps = {fallback_path: TTFont(fallback_path, fontNumber=0).getBestCmap() for fallback_path in fallback_paths}
        self.cmaps = {k: v for k, v in self.cmaps.items() if v is not None}
        self.fallback_paths = list(self.cmaps.keys())
        if sizes:
            for size in sizes:
                self.get_font(self.font_path, size)

    def get_font(self, name: str, size: int):
        try:
            font_cache = self.font_cache.get(name)
            if font_cache:
                if size in font_cache:
                    font = font_cache[size]
                else:
                    font = font_cache[size] = ImageFont.truetype(font=name, size=size, encoding="utf-8")
            else:
                font = ImageFont.truetype(font=name, size=size, encoding="utf-8")
                name = Path(cast(str, font.path)).absolute().as_posix()
                self.font_cache.setdefault(name, {})[size] = font
            if name in self.cmaps:
                cmap = self.cmaps[name]
            else:
                cmap = self.cmaps[name] = TTFont(name, fontNumber=font.index).getBestCmap()
            return font, cast(dict[int, int], cmap)
        except OSError:
            return

    class CharSingle(TypedDict):
        char: str
        color: str
        y: int
        x: int
        end_x: int
        font: FreeTypeFont
        align: str
        highlight: str | None

    class CharLine(TypedDict):
        char: Literal["----"]
        color: str
        y: int
        size: int
        color: str

    type CharStyle = CharSingle | CharLine
    type CharStyleList = list[CharStyle]

    @staticmethod
    def is_charsingle(chaestyle: CharStyle) -> TypeGuard[CharSingle]:
        return chaestyle["char"] != "----"

    def __call__(
        self,
        text: str,
        font_size: int,
        width: int | None = None,
        height: int | None = None,
        padding: tuple[int, int] = (20, 20),
        spacing: float = 1.2,
        color: str = "black",
        bg_color: str | None = None,
        autowrap: bool = False,
        canvas: IMG | None = None,
    ) -> IMG:
        font_cmap = self.get_font(self.font_path, font_size)
        assert font_cmap is not None, "字体文件不存在"
        text, tags = parse_str(text)
        tags = deque(tags)
        padding_x, padding_y = padding

        charlist: Linecard.CharStyleList = []

        wrap_width: int = width - padding_x if width else 0
        absolute_spacing: int = int(font_size * (spacing - 1.0) + 0.5)

        line_height: int = 0
        line_width: int = 0

        line_align: str = "left"
        line_font, line_cmap = font_cmap

        line_passport: bool = False
        line_autowrap: bool = False
        line_nowrap: bool = False

        line_color: str = color
        line_highlight: str | None = None

        inline_height: int = 0

        def line_init() -> None:
            nonlocal line_height, line_width, line_align, line_font, line_cmap, line_passport, line_autowrap, line_nowrap, line_color, line_highlight, inline_height
            line_height = font_size
            line_width = wrap_width

            line_align = line_align if line_nowrap else "left"

            line_font, line_cmap = font_cmap

            line_passport = False
            line_autowrap = autowrap
            line_nowrap = False

            line_color = color
            line_highlight = None

            inline_height = 0

        x: int = 0
        max_x: int = 0
        y: int = 0

        for line in text.split("\n"):
            # 检查继承格式
            if line_passport:
                line_passport = False
            else:
                line_init()
            tmp_height: int = 0
            for unit_rawline in line.split("{"):
                # 渲染行单位存在格式标签
                if unit_rawline.startswith("}"):
                    unit_line = unit_rawline = unit_rawline[1:]
                    tag, param = tags.popleft()
                    match tag:
                        # 原样输出字符串
                        case b"r":
                            unit_line = param + unit_rawline
                        # 对齐标签
                        case b"a":
                            unit_align = param
                            if line_align != unit_align:
                                x = 0
                            line_align = unit_align
                        # 字体标签
                        case b"f":
                            fontkwargs = {k: v for k, v in [x.split("=", 1) for x in param.replace(" ", "").split(",")]}
                            if unit_font_name := fontkwargs.get("name"):
                                unit_font_name = find_font(unit_font_name)
                            if unit_font_size := fontkwargs.get("size"):
                                unit_font_size = to_int(unit_font_size)
                            if unit_font_size:
                                if not unit_font_name:
                                    unit_font_name = cast(str, line_font.path)
                                line_font_cmap = self.get_font(unit_font_name, unit_font_size)
                                if line_font_cmap:
                                    line_font, line_cmap = line_font_cmap
                            elif unit_font_name:
                                unit_font_size = int(line_font.size)
                                line_font_cmap = self.get_font(unit_font_name, unit_font_size)
                                if line_font_cmap:
                                    line_font, line_cmap = line_font_cmap
                            line_color = fontkwargs.get("color", line_color)
                            line_highlight = fontkwargs.get("highlight")
                        # 样式标签
                        case b"s":
                            stylekwargs = {k: v for k, v in [x.split("=", 1) for x in param.replace(" ", "").split(",")]}
                            if unit_height := stylekwargs.get("height"):
                                line_height = to_int(unit_height) or line_height
                            if unit_width := stylekwargs.get("width"):
                                line_width = to_int(unit_width) or line_height
                            line_color = stylekwargs.get("color", color)
                        case b"t":
                            match param:
                                case "nowrap":
                                    line_nowrap = True
                                case "autowrap":
                                    line_autowrap = True
                                case "noautowrap":
                                    line_autowrap = False
                                case "passport":
                                    line_passport = True
                else:
                    unit_line = unit_rawline
                # 渲染行单位格式标签外的文本
                if not unit_line:
                    continue
                elif unit_rawline == "----":
                    line_height = line_height or font_size
                    charlist.append({"char": "----", "color": line_color, "y": y, "size": line_height})
                    x = 0
                else:
                    inline_height = int(line_font.size)
                    if line_width and line_autowrap:
                        if line_align in ("left", "right", "center"):
                            start_x = x
                            char_align = 0
                        else:
                            char_align = to_int(line_align) or 0
                            start_x = char_align + x
                        if line_font.getlength(unit_line) > line_width - start_x:
                            if (inner_wrap_width := line_width - char_align) > inline_height:
                                unit_line = line_wrap(unit_line, inner_wrap_width, line_font, x)
                    line_seg = unit_line.split("\n")
                    line_seg_l = len(line_seg)
                    for i, seg in enumerate(line_seg, 1):
                        for char in seg:
                            charcode = ord(char)
                            if charcode in line_cmap:
                                inner_font = line_font
                            else:
                                for fallback_path in self.fallback_paths:
                                    if charcode in self.cmaps[fallback_path]:
                                        inner_font = self.get_font(fallback_path, inline_height)
                                        assert inner_font is not None
                                        inner_font = inner_font[0]
                                        break
                                else:
                                    inner_font = line_font
                                    char = "□"
                            temp_x = x
                            x += int(inner_font.getlength(char))
                            charlist.append(
                                {
                                    "char": char,
                                    "color": line_color,
                                    "y": y + tmp_height,
                                    "x": temp_x,
                                    "end_x": x,
                                    "font": inner_font,
                                    "align": line_align,
                                    "highlight": line_highlight,
                                }
                            )
                        max_x = max(max_x, x)
                        if i < line_seg_l:
                            x = 0
                            tmp_height += absolute_spacing + inline_height
                    inline_height = tmp_height + absolute_spacing + inline_height
                line_height = max(line_height, inline_height)
            if not line_nowrap:
                x = 0
                y += absolute_spacing + line_height
                line_height = 0

        width = width if width else int(max_x + padding_x * 2)
        height = height if height else int(y + padding_y * 2)
        canvas = canvas if canvas else Image.new("RGBA", (width, height), bg_color)
        draw = ImageDraw.Draw(canvas)
        i = 0
        loop = len(charlist)
        while i < loop:
            charstyle = charlist[i]
            if self.is_charsingle(charstyle):
                charstyle = cast(Linecard.CharSingle, charstyle)
                align = charstyle["align"]
                y = charstyle["y"]
                start_y = y + padding_y
                if align == "left":
                    start_x = padding_x
                elif align == "right":
                    last_charstyle_index = i
                    # 获取下次换行前最后一个的文字样式
                    for inner_charstyle in charlist[i:]:
                        if self.is_charsingle(inner_charstyle) and inner_charstyle["y"] == y and inner_charstyle["align"] == align:
                            last_charstyle_index += 1
                        else:
                            break
                    last_charstyle = cast(Linecard.CharSingle, charlist[last_charstyle_index - 1])
                    start_x = width - padding_x - last_charstyle["end_x"]
                    for inner_charstyle in cast(list[Linecard.CharSingle], charlist[i:last_charstyle_index]):
                        inner_x = inner_charstyle["x"]
                        inner_font = inner_charstyle["font"]
                        inner_highlight = inner_charstyle["highlight"]
                        if inner_highlight:
                            draw.rectangle(
                                (
                                    start_x + inner_x,
                                    start_y,
                                    start_x + inner_charstyle["end_x"],
                                    start_y + inner_font.size,
                                ),
                                fill=inner_highlight,
                            )
                        draw.text(
                            (start_x + inner_x, start_y),
                            inner_charstyle["char"],
                            fill=inner_charstyle["color"],
                            font=inner_font,
                        )
                    i = last_charstyle_index
                    continue
                elif align == "center":
                    last_charstyle_index = i
                    # 获取下次换行前最后一个的文字样式
                    for inner_charstyle in charlist[i:]:
                        if self.is_charsingle(inner_charstyle) and inner_charstyle["y"] == y and inner_charstyle["align"] == align:
                            last_charstyle_index += 1
                        else:
                            break
                    last_charstyle = cast(Linecard.CharSingle, charlist[last_charstyle_index - 1])
                    start_x = (width - last_charstyle["end_x"]) // 2
                    for inner_charstyle in cast(list[Linecard.CharSingle], charlist[i:last_charstyle_index]):
                        inner_x = inner_charstyle["x"]
                        inner_font = inner_charstyle["font"]
                        inner_highlight = inner_charstyle["highlight"]
                        if inner_highlight:
                            draw.rectangle(
                                (
                                    start_x + inner_x,
                                    start_y,
                                    start_x + inner_charstyle["end_x"],
                                    start_y + inner_font.size,
                                ),
                                fill=inner_highlight,
                            )
                        draw.text(
                            (start_x + inner_x, start_y),
                            inner_charstyle["char"],
                            fill=inner_charstyle["color"],
                            font=inner_font,
                        )
                    i = last_charstyle_index
                    continue
                else:
                    start_x = to_int(align) or 0
                x = charstyle["x"]
                font = charstyle["font"]
                highlight = charstyle["highlight"]
                if highlight:
                    draw.rectangle(
                        (
                            start_x + x,
                            start_y,
                            start_x + charstyle["end_x"],
                            start_y + font.size,
                        ),
                        fill=highlight,
                    )
                draw.text(
                    (start_x + x, start_y),
                    charstyle["char"],
                    fill=charstyle["color"],
                    font=font,
                )
                i += 1
            else:
                charstyle = cast(Linecard.CharLine, charstyle)
                inner_y = charstyle["y"] + padding_y + (charstyle["size"] + 0.5) // 2 + 4
                draw.line(((0, inner_y), (width, inner_y)), fill=charstyle["color"], width=4)
                i += 1
        return canvas
