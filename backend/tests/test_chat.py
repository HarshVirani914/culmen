import json

from app.chat import parse_live_chat


def line(offset_ms, text, author, kind="liveChatTextMessageRenderer"):
    item = {kind: {"message": {"runs": [{"text": text}]}, "authorExternalChannelId": author}}
    return json.dumps({"replayChatItemAction": {
        "actions": [{"addChatItemAction": {"item": item}}], "videoOffsetTimeMsec": str(offset_ms)}})


def test_parses_text_messages_with_time_text_and_author():
    out = parse_live_chat([line(27780, "Up", "UC1"), line(30000, "LOL", "UC2")])
    assert out == [(27.78, "Up", "UC1"), (30.0, "LOL", "UC2")]


def test_skips_engagement_banner_garbage_and_missing_offsets():
    lines = [
        line(1000, "Live chat replay is on", "x", kind="liveChatViewerEngagementMessageRenderer"),
        "not json",
        json.dumps({"other": 1}),
        json.dumps({"replayChatItemAction": {"actions": []}}),
        line(2000, "ok", "UC9"),
    ]
    assert parse_live_chat(lines) == [(2.0, "ok", "UC9")]


def test_emote_runs_without_text_are_kept_as_empty_text_not_crash():
    item = {"liveChatTextMessageRenderer": {"message": {"runs": [{"emoji": {"shortcuts": [":hi:"]}}]},
                                            "authorExternalChannelId": "UC3"}}
    ln = json.dumps({"replayChatItemAction": {"actions": [{"addChatItemAction": {"item": item}}],
                                              "videoOffsetTimeMsec": "5000"}})
    assert parse_live_chat([ln]) == [(5.0, "", "UC3")]
