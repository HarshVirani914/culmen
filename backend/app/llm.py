import json
from dataclasses import dataclass

from openai import OpenAI

from .candidates import Candidate
from .config import Settings


@dataclass
class RankedCandidate:
    candidate: Candidate
    title: str
    hook: str
    llm_score: float | None


def _fallback(candidates: list[Candidate]) -> list[RankedCandidate]:
    return [RankedCandidate(c, f"Moment {i + 1}", "", None) for i, c in enumerate(candidates)]


def _extract_json(text: str):
    a, b = text.find("["), text.rfind("]")
    if a == -1 or b <= a:
        raise ValueError("no JSON array")
    return json.loads(text[a:b + 1])


def rank_candidates(candidates: list[Candidate], transcripts: dict[int, str], notes: str,
                    settings: Settings) -> list[RankedCandidate]:
    if not settings.llm_enabled or not candidates:
        return _fallback(candidates)
    try:
        listing = "\n".join(
            f"{i + 1}. [{c.start:.0f}s-{c.end:.0f}s] signal={c.score:.2f} transcript: "
            f"{transcripts.get(i, '(none)')[:600]}" for i, c in enumerate(candidates))
        prompt = (
            "You pick the most viral moments from a gaming live stream for YouTube Shorts.\n"
            f"Creator's focus notes: {notes or 'none'}\n\nCandidates:\n{listing}\n\n"
            'Reply with ONLY a JSON array, one object per candidate: '
            '{"index": <number>, "score": <1-10 virality>, "title": "<short title>", "hook": "<one-line hook>"}')
        client = OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key, timeout=30)
        resp = client.chat.completions.create(
            model=settings.llm_model, messages=[{"role": "user", "content": prompt}])
        items = _extract_json(resp.choices[0].message.content)
        by_idx = {}
        for it in items:
            i = int(it["index"]) - 1
            if 0 <= i < len(candidates):
                by_idx[i] = it
        if not by_idx:
            raise ValueError("no usable items")
        ranked = sorted(by_idx, key=lambda i: float(by_idx[i].get("score", 0)), reverse=True)
        rest = [i for i in range(len(candidates)) if i not in by_idx]
        out = []
        for i in ranked:
            it = by_idx[i]
            out.append(RankedCandidate(candidates[i], str(it.get("title") or f"Moment {i + 1}"),
                                       str(it.get("hook") or ""), float(it.get("score", 0))))
        out += [RankedCandidate(candidates[i], f"Moment {i + 1}", "", None) for i in rest]
        return out
    except Exception:  # noqa: BLE001
        return _fallback(candidates)
