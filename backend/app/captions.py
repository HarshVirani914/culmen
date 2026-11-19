from dataclasses import dataclass
from pathlib import Path


@dataclass
class Word:
    text: str
    start: float
    end: float


HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Cap,Arial,84,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,2,2,60,60,300,1
Style: Credit,Arial,36,&H00DDDDDD,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,3,1,8,40,40,40,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""


def _t(sec: float) -> str:
    sec = max(sec, 0.0)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def build_ass(words: list[Word], path: Path, credit: str | None = None, clip_len: float = 120,
              group: int = 3) -> None:
    lines = [HEADER]
    for i in range(0, len(words), group):
        chunk = words[i:i + group]
        text = " ".join(w.text.strip() for w in chunk).upper().replace("{", "(").replace("}", ")")
        lines.append(f"Dialogue: 0,{_t(chunk[0].start)},{_t(chunk[-1].end)},Cap,,0,0,0,,{text}\n")
    if credit:
        safe = credit.replace("{", "(").replace("}", ")")
        lines.append(f"Dialogue: 1,{_t(0)},{_t(clip_len)},Credit,,0,0,0,,{safe}\n")
    path.write_text("".join(lines))
