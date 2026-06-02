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

from osmium_chat import Bot, Context, commands


logger = getLogger("osmium_chat")
logger.setLevel(DEBUG)
_handler = StreamHandler()
_handler.setFormatter(Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logger.addHandler(_handler)

bot = Bot(prefix="!", client_id=00000, logger=logger)


class ReactionCommands(commands.Commands):
    @commands.listen("connect")
    async def on_connect(self) -> None:
        logger.info("Bot connected")

    @commands.command("react")
    async def react(self, ctx: Context, emoji: str) -> None:
        target = None
        if ctx.community is not None:
            emojis = await ctx.community.fetch_custom_emojis()
            target = next((e for e in emojis if e.name == emoji), None)
        await ctx.message.add_reaction(target if target is not None else emoji)

    @commands.command("unreact")
    async def unreact(self, ctx: Context, emoji: str) -> None:
        target = None
        if ctx.community is not None:
            emojis = await ctx.community.fetch_custom_emojis()
            target = next((e for e in emojis if e.name == emoji), None)
        await ctx.message.remove_reaction(target if target is not None else emoji)

    @commands.guild_command("reactemoji")
    async def reactemoji(self, ctx: Context, name: str) -> None:
        assert ctx.community is not None
        emojis = await ctx.community.fetch_custom_emojis()
        target = next((e for e in emojis if e.name == name), None)
        if target is None:
            await ctx.reply(f"No emoji named :{name}: found.")
            return
        await ctx.message.add_reaction(target)

    @commands.guild_command("unreactemoji")
    async def unreactemoji(self, ctx: Context, name: str) -> None:
        assert ctx.community is not None
        emojis = await ctx.community.fetch_custom_emojis()
        target = next((e for e in emojis if e.name == name), None)
        if target is None:
            await ctx.reply(f"No emoji named :{name}: found.")
            return
        await ctx.message.remove_reaction(target)

    @commands.command("thumbsup")
    async def thumbsup(self, ctx: Context) -> None:
        await ctx.message.add_reaction("👍")


bot.add_commands(ReactionCommands)

if __name__ == "__main__":
    run(bot.connect(token="..."))
