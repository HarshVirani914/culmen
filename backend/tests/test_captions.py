import re

from app.captions import Word, build_ass


def test_build_ass_groups_words_and_timing(tmp_path):
    words = [Word(f"w{i}", i * 0.5, i * 0.5 + 0.4) for i in range(8)]
    p = tmp_path / "c.ass"
    build_ass(words, p)
    text = p.read_text()
    assert "PlayResX: 1080" in text and "PlayResY: 1920" in text
    lines = [l for l in text.splitlines() if l.startswith("Dialogue:")]
    assert 2 <= len(lines) <= 3
    starts = [re.search(r"Dialogue: \d+,([\d:.]+),", l).group(1) for l in lines]
    assert starts == sorted(starts)


def test_credit_line_included_without_words(tmp_path):
    p = tmp_path / "c.ass"
    build_ass([], p, credit="Source: Chan", clip_len=30)
    assert "Source: Chan" in p.read_text()
