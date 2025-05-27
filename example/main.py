import sys
from pathlib import Path

sys.path.append(Path(__file__).parent.parent.as_posix())
from linecard import Linecard, info_splicing

linecard = Linecard("simfang", ["simsun", "Arial", "Tahoma"])
path = Path(__file__).parent

image = linecard(
    path.joinpath("example.txt").read_text(encoding="utf-8"),
    40,
    width=1600,
    autowrap=True,
    padding=(20, 40),
)

info_splicing([image], width=1600, BG_path=path.joinpath("bg.png"), BG_type="#FFFFFF99").save("example.png", format="png")
