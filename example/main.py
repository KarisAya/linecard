if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.append(Path(__file__).parent.parent.as_posix())
    import time
    from linecard import Linecard

    linecard = Linecard(
        "汉仪家书简",
        [
            "msyh",
            "Arial",
            "Tahoma",
            "Microsoft YaHei",
            "Segoe UI",
            "Segoe UI Emoji",
            "Segoe UI Symbol",
            "Helvetica Neue",
            "PingFang SC",
            "Hiragino Sans GB",
            "Source Han Sans SC",
            "Noto Sans SC",
            "Noto Sans CJK JP",
            "WenQuanYi Micro Hei",
            "Apple Color Emoji",
            "Noto Color Emoji",
        ],
        [40],
    )

    start = time.time()

    # for i in range(1, 100):

    linecard(
        Path(__file__).parent.joinpath("example.txt").read_text(encoding="utf-8"),
        40,
        width=1600,
        bg_color="#FFFFFF",
        autowrap=True,
        padding=(20, 40),
    ).show()

    print(time.time() - start)
