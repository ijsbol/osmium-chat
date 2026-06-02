# osmium-chat

A Python API wrapper for [Osmium](https://osmium.chat).

![enbyware](https://pride-badges.pony.workers.dev/static/v1?label=enbyware&labelColor=%23555&stripeWidth=8&stripeColors=FCF434%2CFFFFFF%2C9C59D1%2C2C2C2C)

> [!NOTE]
> the documentation was ai-assisted as i suck at writing documentation lol

---

## Installation

```bash
pip install osmium-chat
```

Requires Python 3.13+.

---

## Quick start

```python
from osmium_chat import Bot, Context
from osmium_chat.commands import CommandRestriction

bot = Bot(prefix="!", client_id=YOUR_CLIENT_ID)


@bot.on("connect")
async def on_connect() -> None:
    print("Connected!")


@bot.command("ping")
async def ping(ctx: Context) -> None:
    await ctx.channel.send("Pong!")


@bot.command("say", restriction=CommandRestriction.COMMUNITY_ONLY)
async def say(ctx: Context, *, words: str) -> None:
    await ctx.channel.send(words)


bot.run(token="YOUR_TOKEN")
```

---

### Rich text formatting

```python
from osmium_chat.content import Bold, CodeBlock, Content, Italic, Spoiler, TextUrl

await ctx.channel.send(Content(
    f"Hello, {Bold('world')}! ",
    TextUrl("osmium.chat", url="https://osmium.chat"),
))
```

---

## Features

- **Commands** — prefix-based command routing with automatic argument parsing and type conversion
- **Command restrictions** — `CommandRestriction.NONE` (default), `DM_ONLY`, or `COMMUNITY_ONLY`
- **Rich text** — `Bold`, `Italic`, `Underline`, `Code`, `CodeBlock`, `Spoiler`, `TextUrl`, and more
- **Communities** — create/manage channels, categories, and roles
- **Invites** — create, list, look up, and revoke invite links
- **File attachments** — upload files from bytes, download and save attachments to disk
- **Events** — `connect`, `message`, `guild_message`, `dm_message`, `command_error`

---

## Documentation

Full API reference: [osmium-chat.readthedocs.io](https://osmium-chat.readthedocs.io)

More examples in the [`examples/`](examples/) directory.

---

## Links

- [GitHub](https://github.com/ijsbol/osmium-chat)
- [Bug tracker](https://github.com/ijsbol/osmium-chat/issues)
- [PyPI](https://pypi.org/project/osmium-chat/)
- [Osmium](https://osmium.chat)
