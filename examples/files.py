"""File upload and download demo.

Commands
--------
!sendtext [words]           -- upload words as a .txt file attachment
!replyfile                  -- reply to the invoking message with a .txt file
!fileinfo                   -- report metadata of any file attached to a message
!download                   -- download the first attachment and echo its contents
!savefile [path]            -- save the first attachment to disk (default: cwd)
"""

from asyncio import run
from logging import DEBUG, Formatter, StreamHandler, getLogger

from osmium_chat.bot import Bot
from osmium_chat.context import Context


logger = getLogger("osmium_chat")
logger.setLevel(DEBUG)
_handler = StreamHandler()
_handler.setFormatter(Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logger.addHandler(_handler)

bot = Bot(prefix="!", client_id=00000, logger=logger)


@bot.on("connect")
async def on_connect() -> None:
    logger.info("Bot connected")


@bot.command("sendtext")
async def sendtext(ctx: Context, *, words: str = "Hello from osmium-py!") -> None:
    data = words.encode()
    await ctx.channel.send_file(data, "message.txt", mimetype="text/plain")


@bot.command("replyfile")
async def replyfile(ctx: Context) -> None:
    data = b"This is a file reply from the bot."
    await ctx.message.reply_file(data, "reply.txt", mimetype="text/plain")


@bot.command("fileinfo")
async def fileinfo(ctx: Context) -> None:
    attachments = ctx.message.attachments
    if not attachments:
        await ctx.reply("No file attachments on that message.")
        return
    lines = [f"Found {len(attachments)} file(s):"]
    for f in attachments:
        name = f.filename or "(unnamed)"
        lines.append(f"- {name} — {f.mimetype}, {f.size} bytes (id {f.file_id})")
    await ctx.reply("\n".join(lines))


@bot.command("download")
async def download(ctx: Context) -> None:
    attachments = ctx.message.attachments
    if not attachments:
        await ctx.reply("Attach a file and run !download again.")
        return
    f = attachments[0]
    data = await f.download()
    name = f.filename or "file"
    await ctx.reply(f"{name} ({len(data)} bytes):\n{data.decode(errors='replace')[:500]}")


@bot.command("savefile")
async def savefile(ctx: Context, *, dest: str = ".") -> None:
    attachments = ctx.message.attachments
    if not attachments:
        await ctx.reply("Attach a file and run !savefile again.")
        return
    path = await attachments[0].save(dest)
    await ctx.reply(f"Saved to {path}")


if __name__ == "__main__":
    run(bot.connect(token="..."))
