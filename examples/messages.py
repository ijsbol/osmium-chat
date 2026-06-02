"""Message sending and formatting demo.

Commands
--------
!say [words]                -- echo words back to the channel
!markdowntest               -- send a message with every formatting style
!editmsg                    -- send a message then edit it
!delete                     -- delete the invoking message
!sum <n> [n ...]            -- sum a list of numbers
!dm                         -- DM the invoking user
!whoami                     -- report the invoking user's name and id
"""

from asyncio import run
from logging import DEBUG, Formatter, StreamHandler, getLogger

from osmium_chat import Bot, Context, commands
from osmium_chat.content import Bold, Code, CodeBlock, Content, Italic, Strikethrough, Underline
from osmium_chat.mentions import UserMention


logger = getLogger("osmium_chat")
logger.setLevel(DEBUG)
_handler = StreamHandler()
_handler.setFormatter(Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logger.addHandler(_handler)

bot = Bot(prefix="!", client_id=00000, logger=logger)


class MessageCommands(commands.Commands):
    @commands.listen("connect")
    async def on_connect(self) -> None:
        logger.info("Bot connected")

    @commands.command("say")
    async def say(self, ctx: Context, *, words: str | None = None) -> None:
        await ctx.channel.send(words or "You didn't say anything!")

    @commands.command("markdowntest")
    async def markdowntest(self, ctx: Context) -> None:
        await ctx.channel.send(Content(
            "Hello", Bold("world"), Italic("italic"),
            Code("code"),
            CodeBlock("code block"),
            Strikethrough("strikethrough"),
            Underline("underline"),
            Underline(Bold(Italic(f"combined {Strikethrough('formatting')}"))),
        ))

    @commands.command("editmsg")
    async def editmsg(self, ctx: Context) -> None:
        message = await ctx.channel.send("This message will edit itself...")
        await message.edit("(edited by the bot)")

    @commands.command("delete")
    async def delete(self, ctx: Context) -> None:
        await ctx.message.delete()

    @commands.command("sum")
    async def sum_(self, ctx: Context, *numbers: int) -> None:
        await ctx.channel.send(str(sum(numbers)))

    @commands.command("dm")
    async def dm(self, ctx: Context) -> None:
        if ctx.author is None:
            await ctx.channel.send("I don't know who you are!")
            return
        # requires the user to have opened a DM channel first
        await ctx.author.dm_channel.send("hi there!")

    @commands.command("whoami")
    async def whoami(self, ctx: Context) -> None:
        author = ctx.message.author
        if author is None:
            await ctx.reply("I don't know who you are!")
            return
        await ctx.channel.send(Content("You are ", UserMention(author), "!"))


bot.add_commands(MessageCommands)

if __name__ == "__main__":
    run(bot.connect(token="..."))
