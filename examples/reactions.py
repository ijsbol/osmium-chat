"""Reaction demo.

Commands
--------
!react <emoji>              -- add a Unicode emoji reaction to the command message
!unreact <emoji>            -- remove a Unicode emoji reaction from the command message
!reactemoji <name>          -- react with a community custom emoji by name
!unreactemoji <name>        -- remove a custom emoji reaction by name
!thumbsup                   -- react with 👍
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


@bot.command("react")
async def react(ctx: Context, emoji: str) -> None:
    # Resolve custom emoji by name first; fall back to Unicode string.
    target = None
    if ctx.community is not None:
        emojis = await ctx.community.fetch_custom_emojis()
        target = next((e for e in emojis if e.name == emoji), None)
    await ctx.message.add_reaction(target if target is not None else emoji)


@bot.command("unreact")
async def unreact(ctx: Context, emoji: str) -> None:
    target = None
    if ctx.community is not None:
        emojis = await ctx.community.fetch_custom_emojis()
        target = next((e for e in emojis if e.name == emoji), None)
    await ctx.message.remove_reaction(target if target is not None else emoji)


@bot.command("reactemoji")
async def reactemoji(ctx: Context, name: str) -> None:
    if ctx.community is None:
        await ctx.reply("Run this in a community channel.")
        return
    emojis = await ctx.community.fetch_custom_emojis()
    target = next((e for e in emojis if e.name == name), None)
    if target is None:
        await ctx.reply(f"No emoji named :{name}: found.")
        return
    await ctx.message.add_reaction(target)


@bot.command("unreactemoji")
async def unreactemoji(ctx: Context, name: str) -> None:
    if ctx.community is None:
        await ctx.reply("Run this in a community channel.")
        return
    emojis = await ctx.community.fetch_custom_emojis()
    target = next((e for e in emojis if e.name == name), None)
    if target is None:
        await ctx.reply(f"No emoji named :{name}: found.")
        return
    await ctx.message.remove_reaction(target)


@bot.command("thumbsup")
async def thumbsup(ctx: Context) -> None:
    await ctx.message.add_reaction("👍")


if __name__ == "__main__":
    run(bot.connect(token="..."))
