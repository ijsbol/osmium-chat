"""Hello world bot — minimal starting point.

See the other examples for focused feature demos:
  invites.py   -- invite creation, listing, lookup
  channels.py  -- channel create / rename / delete
  categories.py -- category create / manage / delete
  messages.py  -- sending, formatting, editing, DMs
"""

from asyncio import run
from logging import DEBUG, Formatter, StreamHandler, getLogger

from osmium_chat.bot import Bot
from osmium_chat.commands import CommandRestriction
from osmium_chat.context import Context


logger = getLogger("osmium_chat")
logger.setLevel(DEBUG)
_handler = StreamHandler()
_handler.setFormatter(Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logger.addHandler(_handler)

bot = Bot(prefix="!", client_id=150896, logger=logger)


@bot.on("connect")
async def on_connect() -> None:
    logger.info("Bot connected to WebSocket server")
    # await bot.use_invite("your_invite_code_here")


@bot.on("message")
async def on_message(ctx: Context) -> None:
    who = ctx.message.author.name if ctx.message.author else "someone"
    logger.info("message from %s: %s", who, ctx.message.content)


@bot.on("guild_message")
async def on_guild_message(ctx: Context) -> None:
    logger.info("guild message: %s", ctx.message.content)


@bot.on("dm_message")
async def on_dm_message(ctx: Context) -> None:
    logger.info("dm message: %s", ctx.message.content)


@bot.command("say")
async def say(ctx: Context, *, words: str | None = None) -> None:
    await ctx.channel.send(words or "You didn't say anything!")


@bot.command("dm", restriction=CommandRestriction.DM_ONLY)
async def dm(ctx: Context) -> None:
    await ctx.channel.send("This command only works in DMs!")


@bot.command("community", restriction=CommandRestriction.COMMUNITY_ONLY)
async def community(ctx: Context) -> None:
    await ctx.channel.send("This command only works in community channels!")


if __name__ == "__main__":
    run(bot.connect(token="..."))
