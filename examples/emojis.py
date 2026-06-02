"""Custom emoji management demo.

Commands
--------
!listemojis                         -- list all custom emojis in this community
!createemoji <name> <image_path>    -- upload a PNG as a custom emoji
!deleteemoji :name:                 -- delete a custom emoji by mention
!renameemoji :name: <new_name>      -- rename a custom emoji locally
!sendemoji :name:                   -- send a message containing a custom emoji
"""

from asyncio import run
from logging import DEBUG, Formatter, StreamHandler, getLogger
from pathlib import Path

from osmium_chat.bot import Bot
from osmium_chat.content import Content
from osmium_chat.context import Context
from osmium_chat.emoji import CustomEmoji


logger = getLogger("osmium_chat")
logger.setLevel(DEBUG)
_handler = StreamHandler()
_handler.setFormatter(Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logger.addHandler(_handler)

bot = Bot(prefix="!", client_id=150896, logger=logger)


@bot.on("connect")
async def on_connect() -> None:
    logger.info("Bot connected")


@bot.command("listemojis")
async def listemojis(ctx: Context) -> None:
    if ctx.community is None:
        await ctx.reply("Run this in a community channel.")
        return
    emojis = await ctx.community.fetch_custom_emojis()
    if not emojis:
        await ctx.reply("This community has no custom emojis.")
        return
    parts: list = [f"Custom emojis in {ctx.community.name}:"]
    for emoji in emojis:
        parts.append("\n  ")
        parts.append(emoji)
        parts.append(f" {emoji.name}")
    await ctx.channel.send(Content(*parts))


@bot.command("createemoji")
async def createemoji(ctx: Context, name: str, image_path: str) -> None:
    if ctx.community is None:
        await ctx.reply("Run this in a community channel.")
        return
    path = Path(image_path)
    if not path.exists():
        await ctx.reply(f"File not found: {image_path}")
        return
    image = path.read_bytes()
    mimetype = "image/png" if path.suffix.lower() == ".png" else "image/webp"
    emoji = await ctx.community.create_custom_emoji(image, name, mimetype=mimetype)
    await ctx.reply(f"Created :{emoji.name}: (id {emoji.id}).")


@bot.command("deleteemoji")
async def deleteemoji(ctx: Context, emoji: CustomEmoji) -> None:
    await emoji.delete()
    await ctx.reply(f"Deleted :{emoji.name}:.")


@bot.command("renameemoji")
async def renameemoji(ctx: Context, emoji: CustomEmoji, new_name: str) -> None:
    old_name = emoji.name
    emoji.rename(new_name)
    await ctx.reply(f"Renamed :{old_name}: → :{new_name}: (local only).")


@bot.command("sendemoji")
async def sendemoji(ctx: Context, emoji: CustomEmoji) -> None:
    await ctx.channel.send(Content("Here it is: ", emoji))


if __name__ == "__main__":
    run(bot.connect(token="..."))
