"""Channel management demo.

Commands
--------
!newchannel [name]          -- create a channel in this community
!rename <name>              -- rename the current channel
!nukechannel                -- delete the current channel
"""

from asyncio import run
from logging import DEBUG, Formatter, StreamHandler, getLogger

from osmium_chat import Bot, Context, commands


logger = getLogger("osmium_chat")
logger.setLevel(DEBUG)
_handler = StreamHandler()
_handler.setFormatter(Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logger.addHandler(_handler)

bot = Bot(prefix="!", client_id=00000, logger=logger)


class ChannelCommands(commands.Commands):
    @commands.listen("connect")
    async def on_connect(self) -> None:
        logger.info("Bot connected")

    @commands.guild_command("newchannel")
    async def newchannel(self, ctx: Context, *, name: str = "general") -> None:
        assert ctx.community is not None
        channel = await ctx.community.create_channel(name=name)
        await ctx.reply(f"Created #{channel.name} (id {channel.id}).")

    @commands.command("rename")
    async def rename(self, ctx: Context, *, name: str) -> None:
        await ctx.channel.edit(name=name)
        await ctx.reply(f"Renamed channel to #{name}.")

    @commands.command("nukechannel")
    async def nukechannel(self, ctx: Context) -> None:
        name = ctx.channel.name or str(ctx.channel.id)
        await ctx.channel.delete()
        logger.info("Deleted channel #%s", name)


bot.add_commands(ChannelCommands)

if __name__ == "__main__":
    run(bot.connect(token="..."))
