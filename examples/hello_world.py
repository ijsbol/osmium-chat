"""Hello world bot — minimal starting point.

See the other examples for focused feature demos:
  invites.py   -- invite creation, listing, lookup
  channels.py  -- channel create / rename / delete
  categories.py -- category create / manage / delete
  messages.py  -- sending, formatting, editing, DMs
"""

from asyncio import run
from logging import DEBUG, Formatter, StreamHandler, getLogger

from osmium_chat import Bot, Context, Message, commands


logger = getLogger("osmium_chat")
logger.setLevel(DEBUG)
_handler = StreamHandler()
_handler.setFormatter(Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logger.addHandler(_handler)

bot = Bot(prefix="!", client_id=150896, logger=logger)


class HelloCommands(commands.Commands):
    @commands.listen("connect")
    async def on_connect(self) -> None:
        logger.info("Bot connected to WebSocket server")
        # await self.bot.use_invite("your_invite_code_here")

    @commands.listen("message")
    async def on_message(self, message: Message) -> None:
        who = message.author.name if message.author else "someone"
        logger.info("message from %s: %s", who, message.content)

    @commands.listen("guild_message")
    async def on_guild_message(self, message: Message) -> None:
        logger.info("guild message: %s", message.content)

    @commands.listen("dm_message")
    async def on_dm_message(self, message: Message) -> None:
        logger.info("dm message: %s", message.content)

    @commands.command("say")
    async def say(self, ctx: Context, *, words: str | None = None) -> None:
        await ctx.channel.send(words or "You didn't say anything!")

    @commands.dm_command("dm")
    async def dm(self, ctx: Context) -> None:
        await ctx.channel.send("This command only works in DMs!")

    @commands.guild_command("community")
    async def community(self, ctx: Context) -> None:
        await ctx.channel.send("This command only works in community channels!")


bot.add_commands(HelloCommands)

if __name__ == "__main__":
    run(bot.connect(token="..."))
