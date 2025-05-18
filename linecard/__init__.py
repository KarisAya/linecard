import sys
from pathlib import Path
from collections.abc import Iterable
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from PIL.ImageFont import FreeTypeFont
from PIL.Image import Image as IMG
from typing import TypedDict, Literal, Protocol
from .linecard_parsing import parse_str

match sys.platform:
    case "win32":
        FONT_PATH = "C:/Windows/Fonts"
    case "darwin":
        FONT_PATH = "/Library/Fonts"
    case "linux":
        FONT_PATH = "/usr/share/fonts"
    case _:
        import os

        FONT_PATH = os.environ["LINECARD_FONT_PATH"]


class FontManager:
    """
    字体管理器
    """

    def __init__(self, font_name: str, fallback: list[str], size: Iterable[int] | None = None) -> None:
        path = self.find_font(font_name)
        if not path:
            raise ValueError(f"Font:{font_name} not found")
        self.path = path.absolute()
        self.font_name: str = font_name
        self.cmap = TTFont(path, recalcBBoxes=False, recalcTimestamp=False, fontNumber=0).getBestCmap()
        self.fallback: list[str] = fallback
        self.fallback_cmap = {}
        for fallback_name in self.fallback:
            fallback_path = self.find_font(fallback_name)
            if not fallback_path:
                continue
            self.fallback_cmap[fallback_path.absolute()] = TTFont(fallback_path, fontNumber=0).getBestCmap()

        self.font_def = {k: self.new_font(font_name, k) for k in size} if size else {}

    @property
    def fallback_paths(self) -> list[str]:
        return list(self.fallback_cmap.keys())

    def font(self, size: int):
        return self.font_def.get(size) or self.new_font(self.font_name, size)

    def new_font(self, name: str, size: int):
        return ImageFont.truetype(font=name, size=size, encoding="utf-8")

    @staticmethod
    def find_font(font_name: str, search_path=Path(FONT_PATH).absolute()):
        def check_font(font_file: Path, font_name: str):
            suffix = font_file.suffix.lower()
            if not suffix.endswith((".ttf", ".otf", ".ttc")):
                return False
            font_name = font_name.lower()
            if not font_name == font_file.stem.lower():
                return False
            try:
                TTFont(font_file, recalcBBoxes=False, recalcTimestamp=False, fontNumber=0)
            except:
                return False
            return True

        try:
            TTFont(font_name, recalcBBoxes=False, recalcTimestamp=False, fontNumber=0)
            return Path(font_name)
        except:
            pass

        for file in search_path.iterdir():
            if check_font(file, font_name):
                return file
        return None


def line_wrap(line: str, width: int, font: FreeTypeFont, start: float = 0.0) -> str:
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


class CharSingle(TypedDict):
    char: str
    x: int
    end_x: int
    y: int
    font: FreeTypeFont
    color: str
    align: str
    highlight: str | None


class CharLine(TypedDict):
    char: Literal["----"]
    y: int | float
    size: int
    color: str


def try_int(n: str | None):
    if n:
        try:
            return int(n)
        except ValueError:
            pass


def try_float(n: str | None):
    if n:
        try:
            return float(n)
        except ValueError:
            pass


def linecard(
    text: str,
    font_manager: FontManager,
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
    text, tags = parse_str(text)
    padding_x, padding_y = padding
    font_def = font_manager.font(font_size)
    cmap_def = font_manager.cmap
    charlist = []

    wrap_width: int = width - padding_x if width else 0
    abslutespacing: int = int(font_size * (spacing - 1.0) + 0.5)

    line_height: int = 0
    line_width: int = 0

    line_align: str = "left"
    line_font: FreeTypeFont = font_def
    line_cmap: dict = cmap_def

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
        line_font = font_def
        line_cmap = cmap_def

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
        for inner_line in line.replace("{", "\n{").split("\n"):
            if inner_line.startswith("{}"):
                inner_line = inner_line[2:]
                tag, textargs = tags[0]
                tags = tags[1:]
                match tag:
                    case b"r":
                        inner_line = textargs + inner_line
                    case b"a":
                        inner_align = textargs
                        if line_align != inner_align:
                            x = 0
                        line_align = inner_align
                    case b"f":
                        fontkwargs = {k: v for k, v in [x.split("=") for x in textargs.replace(" ", "").split(",")]}
                        inner_font_size = try_int(fontkwargs.get("size"))
                        inner_font_name = fontkwargs.get("name")
                        if inner_font_name:
                            inner_font_name = font_manager.find_font(inner_font_name)
                        if inner_font_size or inner_font_name:
                            inner_font_name = inner_font_name or line_font.path
                            inner_font_size = inner_font_size or font_size
                            try:
                                line_font = ImageFont.truetype(font=inner_font_name, size=inner_font_size, encoding="utf-8")
                                line_cmap = TTFont(inner_font_name, fontNumber=line_font.index).getBestCmap()
                            except OSError:
                                pass
                        line_color = fontkwargs.get("color") or line_color
                        line_highlight = fontkwargs.get("highlight")
                    case b"s":
                        stylekwargs = {k: v for k, v in [x.split("=", 1) for x in textargs.replace(" ", "").split(",")]}
                        line_height = try_int(stylekwargs.get("height")) or line_height
                        line_width = try_int(stylekwargs.get("width")) or line_width
                        line_color = stylekwargs.get("color") or color
                    case b"t":
                        match textargs:
                            case "nowrap":
                                line_nowrap = True
                            case "autowrap":
                                line_autowrap = True
                            case "noautowrap":
                                line_autowrap = False
                            case "passport":
                                line_passport = True
            if not inner_line:
                continue
            elif inner_line == "----":
                line_height = line_height or font_size
                charlist.append(
                    {
                        "char": "----",
                        "size": line_height,
                        "y": y,
                        "color": line_color,
                    }
                )
                x = 0
            else:
                inline_height = int(line_font.size)
                if line_width and line_autowrap:
                    if line_align in {"left", "right", "center"}:
                        start_x = x
                        char_align = 0
                    else:
                        char_align = try_int(line_align) or 0
                        start_x = char_align + x
                    if line_font.getlength(inner_line) > line_width - start_x:
                        if (inner_wrap_width := line_width - char_align) > inline_height:
                            inner_line = line_wrap(inner_line, inner_wrap_width, line_font, x)
                seglist = inner_line.split("\n")
                seglist_l = len(seglist)
                for i, seg in enumerate(seglist, 1):
                    for char in seg:
                        charcode = ord(char)
                        if charcode in line_cmap:
                            inner_font = line_font
                        else:
                            for fallback_font, fallback_cmap in font_manager.fallback_cmap.items():
                                if charcode in fallback_cmap:
                                    inner_font = ImageFont.truetype(font=fallback_font, size=inline_height, encoding="utf-8")
                                    break
                            else:
                                inner_font = line_font
                                char = "□"
                        temp_x = x
                        x += int(inner_font.getlength(char))
                        charlist.append(
                            {
                                "char": char,
                                "x": temp_x,
                                "y": y + tmp_height,
                                "font": inner_font,
                                "color": line_color,
                                "align": line_align,
                                "end_x": x,
                                "highlight": line_highlight,
                            }
                        )
                    max_x = max(max_x, x)
                    if i < seglist_l:
                        x = 0
                        tmp_height += abslutespacing + inline_height
                inline_height = tmp_height + abslutespacing + inline_height
            line_height = max(line_height, inline_height)
        if not line_nowrap:
            x = 0
            y += abslutespacing + line_height
            line_height = 0

    width = width if width else int(max_x + padding_x * 2)
    height = height if height else int(y + padding_y * 2)
    canvas = canvas if canvas else Image.new("RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(canvas)
    i = 0
    loop = len(charlist)
    while i < loop:
        tmp_char = charlist[i]
        if tmp_char["char"] == "----":
            char_line: CharLine = tmp_char
            inner_y = char_line["y"] + padding_y + (char_line["size"] + 0.5) // 2 + 4
            draw.line(((0, inner_y), (width, inner_y)), fill=char_line["color"], width=4)
            i += 1
        else:
            char_info: CharSingle = tmp_char
            align = char_info["align"]
            y = char_info["y"]
            start_y = y + padding_y
            if align == "left":
                start_x = padding_x
            elif align == "right":
                inner_i = i
                inner_char_info: CharSingle
                for inner_char_info in charlist[i:]:
                    if inner_char_info["char"] != "----" and inner_char_info["y"] == y and inner_char_info["align"] == align:
                        inner_i += 1
                    else:
                        break
                start_x = width - padding_x - charlist[inner_i - 1]["end_x"]
                for inner_char_info in charlist[i:inner_i]:
                    inner_x = inner_char_info["x"]
                    inner_font = inner_char_info["font"]
                    inner_highlight = inner_char_info["highlight"]
                    if inner_highlight:
                        draw.rectangle(
                            (
                                start_x + inner_x,
                                start_y,
                                start_x + inner_char_info["end_x"],
                                start_y + inner_font.size,
                            ),
                            fill=inner_highlight,
                        )
                    draw.text(
                        (start_x + inner_x, start_y),
                        inner_char_info["char"],
                        fill=inner_char_info["color"],
                        font=inner_font,
                    )
                i = inner_i
                continue
            elif align == "center":
                inner_i = i
                inner_char_info: CharSingle
                for inner_char_info in charlist[i:]:
                    if len(inner_char_info["char"]) == 1 and inner_char_info["y"] == y and inner_char_info["align"] == align:
                        inner_i += 1
                    else:
                        break
                start_x = (width - charlist[inner_i - 1]["end_x"]) // 2
                for inner_char_info in charlist[i:inner_i]:
                    inner_x = inner_char_info["x"]
                    inner_font = inner_char_info["font"]
                    inner_highlight = inner_char_info["highlight"]
                    if inner_highlight:
                        draw.rectangle(
                            (
                                start_x + inner_x,
                                start_y,
                                start_x + inner_char_info["end_x"],
                                start_y + inner_font.size,
                            ),
                            fill=inner_highlight,
                        )
                    draw.text(
                        (start_x + inner_x, start_y),
                        inner_char_info["char"],
                        fill=inner_char_info["color"],
                        font=inner_font,
                    )
                i = inner_i
                continue
            else:
                start_x = try_int(align) or 0
            x = char_info["x"]
            font = char_info["font"]
            highlight = char_info["highlight"]
            if highlight:
                draw.rectangle(
                    (
                        start_x + x,
                        start_y,
                        start_x + char_info["end_x"],
                        start_y + font.size,
                    ),
                    fill=highlight,
                )
            draw.text(
                (start_x + x, start_y),
                char_info["char"],
                fill=char_info["color"],
                font=font,
            )
            i += 1

    return canvas


type ImageList = list[IMG]


class CanvasEffectHandler(Protocol):
    def __call__(self, canvas: IMG, image: IMG, padding: int, width: int, height: int) -> None: ...


def info_splicing(
    info: ImageList,
    BG_path: Path | None = None,
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
    if BG_path and BG_path.exists():
        bg = Image.open(BG_path).convert("RGB")
        canvas = CropResize(bg, size)
    else:
        canvas = Image.new("RGB", size, "white")
        BG_type = "NONE"

    CanvasEffect: CanvasEffectHandler

    if isinstance(BG_type, str):
        if BG_type == "NONE":

            def BG(canvas: IMG, image: IMG, padding: int, width: int, height: int):
                canvas.paste(image, (padding, height), mask=image)

        elif BG_type.startswith("GAUSS"):
            try:
                radius = int(BG_type.split(":")[1])
            except (IndexError, ValueError):
                radius = 4

            def BG(canvas: IMG, image: IMG, padding: int, width: int, height: int):
                box = (padding, height, width + padding, height + image.size[1])
                region = canvas.crop(box)
                blurred_region = region.filter(ImageFilter.GaussianBlur(radius=radius))
                canvas.paste(blurred_region, box)
                canvas.paste(image, (padding, height), mask=image)

        else:

            def BG(canvas: IMG, image: IMG, padding: int, width: int, height: int):
                colorBG = Image.new("RGBA", (width, image.size[1]), BG_type)
                canvas.paste(colorBG, (padding, height), mask=colorBG)
                canvas.paste(image, (padding, height), mask=image)

        CanvasEffect = BG
    else:
        CanvasEffect = BG_type

    height = padding

    for image in info:
        CanvasEffect(canvas, image, padding, width, height)
        height += image.size[1] + spacing * 2

    return canvas


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
