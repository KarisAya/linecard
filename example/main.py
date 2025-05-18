if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.append(Path(__file__).parent.parent.as_posix())
    from clovers_utils.linecard import FontManager, linecard

    linecard(
        Path(__file__).parent.joinpath("example.txt").read_text(encoding="utf-8"),
        FontManager("msyh", ["simfang"], [40]),
        40,
        width=1600,
        bg_color="#FFFFFF",
        autowrap=True,
        padding=(20, 40),
    ).save("example.png")
