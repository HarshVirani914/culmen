"""Live chat readers. Parsers are unit tested; the network clients are best-effort and checked by hand
(YouTube, Kick). Any failure just means the session runs on audio alone."""
import asyncio
import json
import random
import re
from typing import Callable
from urllib.parse import urlparse

_TWITCH = re.compile(r"^(?:@\S+ )?:([A-Za-z0-9_]{2,25})!\S+ PRIVMSG #\S+ :(.*)$")


def parse_twitch_irc(line: str) -> tuple[str, str] | None:
    m = _TWITCH.match(line.strip())
    return (m.group(1), m.group(2)) if m else None


def handle_twitch_line(line: str) -> str | None:
    """Reply to send for a server line (PONG for PING), else None."""
    return "PONG :tmi.twitch.tv\r\n" if line.startswith("PING") else None


def parse_kick_event(raw: str) -> tuple[str, str] | None:
    try:
        ev = json.loads(raw)
        if ev.get("event") != "App\\Events\\ChatMessageEvent":
            return None
        data = json.loads(ev["data"]) if isinstance(ev["data"], str) else ev["data"]
        return data["sender"]["username"], data.get("content", "")
    except (ValueError, KeyError, TypeError):
        return None


def parse_youtube_live_chat(obj: dict) -> list[tuple[str, str]]:
    out = []
    actions = obj.get("continuationContents", {}).get("liveChatContinuation", {}).get("actions", [])
    for a in actions:
        r = a.get("addChatItemAction", {}).get("item", {}).get("liveChatTextMessageRenderer")
        if r:
            text = "".join(run.get("text", "") for run in r.get("message", {}).get("runs", []))
            out.append((r.get("authorExternalChannelId", ""), text))
    return out


BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/124.0 Safari/537.36")  # a bare "Mozilla/5.0" gets a stub page without chat data


def extract_youtube_bootstrap(html: str) -> tuple[str, str, str]:
    """(api key, client version, continuation token) from YouTube's live chat page."""
    key = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html)
    ver = re.search(r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', html)
    if not key:
        raise ValueError("YouTube did not return the live chat page (blocked or not a live chat)")
    cont = None
    m = re.search(r'(?:window\["ytInitialData"\]|var ytInitialData)\s*=\s*(\{.*?\});\s*</script>', html, re.S)
    if m:
        try:
            lcr = json.loads(m.group(1))["contents"]["liveChatRenderer"]
            subs = lcr["header"]["liveChatHeaderRenderer"]["viewSelector"]["sortFilterSubMenuRenderer"]["subMenuItems"]
            for item in subs:
                if "live" in item.get("title", "").lower():
                    cont = item["continuation"]["reloadContinuationData"]["continuation"]
        except (ValueError, KeyError, TypeError):
            cont = None
    if not cont:
        first = re.search(r'"continuation":"([^"]+)"', html)
        if not first:
            raise ValueError("no chat continuation found")
        cont = first.group(1)
    return key.group(1), ver.group(1) if ver else "2.20240101.00.00", cont


class ChatSource:
    def __init__(self) -> None:
        self._closed = False

    def close(self) -> None:
        self._closed = True

    async def run(self, on_message: Callable[[str, str], None]) -> None:  # pragma: no cover - network
        raise NotImplementedError


class TwitchChat(ChatSource):
    def __init__(self, channel: str):
        super().__init__()
        self.channel = channel.lower()

    async def run(self, on_message):  # pragma: no cover - network
        while not self._closed:
            try:
                reader, writer = await asyncio.open_connection("irc.chat.twitch.tv", 6697, ssl=True)
                writer.write(f"NICK justinfan{random.randint(10000, 99999)}\r\nJOIN #{self.channel}\r\n".encode())
                await writer.drain()
                while not self._closed:
                    raw = await asyncio.wait_for(reader.readline(), 30)
                    if not raw:
                        break
                    line = raw.decode("utf-8", "replace").rstrip("\r\n")
                    reply = handle_twitch_line(line)
                    if reply:
                        writer.write(reply.encode())
                        await writer.drain()
                    msg = parse_twitch_irc(line)
                    if msg:
                        on_message(*msg)
            except Exception:
                pass
            await asyncio.sleep(5)


class YouTubeChat(ChatSource):
    def __init__(self, url: str):
        super().__init__()
        m = re.search(r"[?&]v=([\w-]{11})", url) or re.search(r"/(?:live|shorts)/([\w-]{11})", url) \
            or re.search(r"youtu\.be/([\w-]{11})", url)
        self.video_id = m.group(1) if m else urlparse(url).path.strip("/")

    async def run(self, on_message):  # pragma: no cover - network
        import httpx

        async with httpx.AsyncClient(timeout=20, headers={"User-Agent": BROWSER_UA}, follow_redirects=True) as c:
            while not self._closed:
                try:
                    page = (await c.get(f"https://www.youtube.com/live_chat?is_popout=1&v={self.video_id}")).text
                    key, ver, cont = extract_youtube_bootstrap(page)
                    while not self._closed and cont:
                        r = await c.post(
                            f"https://www.youtube.com/youtubei/v1/live_chat/get_live_chat?key={key}",
                            json={"context": {"client": {"clientName": "WEB", "clientVersion": ver}},
                                  "continuation": cont})
                        obj = r.json()
                        for msg in parse_youtube_live_chat(obj):
                            on_message(*msg)
                        nxt = obj["continuationContents"]["liveChatContinuation"]["continuations"][0]
                        d = nxt.get("invalidationContinuationData") or nxt.get("timedContinuationData")
                        cont = d["continuation"]
                        await asyncio.sleep(min(max(d.get("timeoutMs", 3000), 1000), 8000) / 1000)
                except Exception:
                    await asyncio.sleep(10)


class KickChat(ChatSource):
    # Unverified: relies on Kick's public pusher key and channel API, which may be blocked.
    PUSHER = "wss://ws-us2.pusher.com/app/32cbd69e4b950bf97679?protocol=7&client=js&version=8.4.0-rc2&flash=false"

    def __init__(self, slug: str):
        super().__init__()
        self.slug = slug

    async def run(self, on_message):  # pragma: no cover - network
        import httpx
        import websockets

        while not self._closed:
            try:
                async with httpx.AsyncClient(timeout=20, headers={"User-Agent": BROWSER_UA}) as c:
                    room = (await c.get(f"https://kick.com/api/v2/channels/{self.slug}")).json()["chatroom"]["id"]
                async with websockets.connect(self.PUSHER) as ws:
                    await ws.send(json.dumps({"event": "pusher:subscribe",
                                              "data": {"auth": "", "channel": f"chatrooms.{room}.v2"}}))
                    async for raw in ws:
                        if self._closed:
                            return
                        msg = parse_kick_event(raw)
                        if msg:
                            on_message(*msg)
            except Exception:
                await asyncio.sleep(15)


def chat_source_for(url: str) -> ChatSource | None:
    host = (urlparse(url).hostname or "").lower()
    path = [p for p in urlparse(url).path.split("/") if p]
    if host.endswith("twitch.tv") and path:
        return TwitchChat(path[0])
    if host.endswith("kick.com") and path:
        return KickChat(path[0])
    if host.endswith("youtube.com") or host.endswith("youtu.be"):
        return YouTubeChat(url)
    return None
