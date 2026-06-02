"""Channel management demo.

Commands
--------
!newchannel [name]          -- create a channel in this community
!rename <name>              -- rename the current channel
!nukechannel                -- delete the current channel
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


@bot.command("newchannel")
async def newchannel(ctx: Context, *, name: str = "general") -> None:
    if ctx.community is None:
        await ctx.reply("Run this in a community channel.")
        return
    channel = await ctx.community.create_channel(name=name)
    await ctx.reply(f"Created #{channel.name} (id {channel.id}).")


@bot.command("rename")
async def rename(ctx: Context, *, name: str) -> None:
    await ctx.channel.edit(name=name)
    await ctx.reply(f"Renamed channel to #{name}.")


@bot.command("nukechannel")
async def nukechannel(ctx: Context) -> None:
    name = ctx.channel.name or str(ctx.channel.id)
    await ctx.channel.delete()
    logger.info("Deleted channel #%s", name)


if __name__ == "__main__":
    run(bot.connect(token="..."))
