import json

from app.live.chat_live import (chat_source_for, handle_twitch_line, parse_kick_event, parse_twitch_irc,
                                parse_youtube_live_chat)


def test_parse_twitch_privmsg_with_and_without_tags():
    assert parse_twitch_irc(":nick123!nick123@nick123.tmi.twitch.tv PRIVMSG #chan :hello world") == ("nick123", "hello world")
    assert parse_twitch_irc("@badge-info=;color=#FF0000 :a_b!a_b@a_b.tmi.twitch.tv PRIVMSG #chan :LOL :)") == ("a_b", "LOL :)")


def test_twitch_ignores_ping_join_notice_garbage():
    for line in ("PING :tmi.twitch.tv", ":tmi.twitch.tv 001 justinfan1 :Welcome", ":x!x@x.tmi.twitch.tv JOIN #c",
                 ":tmi.twitch.tv NOTICE * :Login unsuccessful", "", "garbage"):
        assert parse_twitch_irc(line) is None


def test_twitch_ping_gets_pong():
    assert handle_twitch_line("PING :tmi.twitch.tv") == "PONG :tmi.twitch.tv\r\n"
    assert handle_twitch_line(":a!a@a.tmi.twitch.tv PRIVMSG #c :hi") is None


def test_parse_kick_chat_message_event_and_ignores_others():
    data = {"id": "1", "content": "KEKW", "sender": {"username": "viewer1"}}
    ev = json.dumps({"event": "App\\Events\\ChatMessageEvent", "channel": "chatrooms.1.v2", "data": json.dumps(data)})
    assert parse_kick_event(ev) == ("viewer1", "KEKW")
    assert parse_kick_event(json.dumps({"event": "pusher:pong", "data": "{}"})) is None
    assert parse_kick_event("not json") is None


def test_parse_youtube_live_chat_actions():
    def item(author, text):
        return {"addChatItemAction": {"item": {"liveChatTextMessageRenderer": {
            "authorExternalChannelId": author, "message": {"runs": [{"text": text}]}}}}}
    obj = {"continuationContents": {"liveChatContinuation": {"actions": [item("UC1", "hi"), {"other": 1}, item("UC2", "LOL")]}}}
    assert parse_youtube_live_chat(obj) == [("UC1", "hi"), ("UC2", "LOL")]
    assert parse_youtube_live_chat({}) == []


def test_chat_source_for_hosts():
    assert chat_source_for("https://www.twitch.tv/somechannel") is not None
    assert chat_source_for("https://www.youtube.com/watch?v=abc") is not None
    assert chat_source_for("https://kick.com/somechannel") is not None
    assert chat_source_for("https://example.com/x") is None


def _page(menu=True, key=True):
    import json as _j
    data = {"contents": {"liveChatRenderer": {"header": {"liveChatHeaderRenderer": {"viewSelector": {
        "sortFilterSubMenuRenderer": {"subMenuItems": [
            {"title": "Top Chat", "selected": True, "continuation": {"reloadContinuationData": {"continuation": "TOPCONT"}}},
            {"title": "Live-Chat", "selected": False, "continuation": {"reloadContinuationData": {"continuation": "LIVECONT"}}},
        ]}}}}}}} if menu else {}
    head = '"INNERTUBE_API_KEY":"KEY123","INNERTUBE_CLIENT_VERSION":"2.2026.01.01",' if key else ""
    return f'<html><script>{head}</script><script>window["ytInitialData"] = {_j.dumps(data)};</script>"continuation":"FALLBACK"</html>'


def test_youtube_bootstrap_prefers_live_chat_continuation():
    from app.live.chat_live import extract_youtube_bootstrap
    assert extract_youtube_bootstrap(_page()) == ("KEY123", "2.2026.01.01", "LIVECONT")


def test_youtube_bootstrap_falls_back_to_first_continuation():
    from app.live.chat_live import extract_youtube_bootstrap
    assert extract_youtube_bootstrap(_page(menu=False)) == ("KEY123", "2.2026.01.01", "FALLBACK")


def test_youtube_bootstrap_raises_on_stub_page():
    import pytest
    from app.live.chat_live import extract_youtube_bootstrap
    with pytest.raises(ValueError):
        extract_youtube_bootstrap("<html>blocked</html>")
