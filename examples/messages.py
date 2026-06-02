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

from osmium_chat.bot import Bot
from osmium_chat.content import Bold, Code, CodeBlock, Content, Italic, Strikethrough, Underline
from osmium_chat.context import Context


logger = getLogger("osmium_chat")
logger.setLevel(DEBUG)
_handler = StreamHandler()
_handler.setFormatter(Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logger.addHandler(_handler)

bot = Bot(prefix="!", client_id=150896, logger=logger)


@bot.on("connect")
async def on_connect() -> None:
    logger.info("Bot connected")


@bot.command("say")
async def say(ctx: Context, *, words: str | None = None) -> None:
    await ctx.channel.send(words or "You didn't say anything!")


@bot.command("markdowntest")
async def markdowntest(ctx: Context) -> None:
    await ctx.channel.send(Content(
        "Hello", Bold("world"), Italic("italic"),
        Code("code"),
        CodeBlock("code block"),
        Strikethrough("strikethrough"),
        Underline("underline"),
        Underline(Bold(Italic(f"combined {Strikethrough('formatting')}"))),
    ))


@bot.command("editmsg")
async def editmsg(ctx: Context) -> None:
    message = await ctx.channel.send("This message will edit itself...")
    await message.edit("(edited by the bot)")


@bot.command("delete")
async def delete(ctx: Context) -> None:
    await ctx.message.delete()


@bot.command("sum")
async def sum_(ctx: Context, *numbers: int) -> None:
    await ctx.channel.send(str(sum(numbers)))


@bot.command("dm")
async def dm(ctx: Context) -> None:
    if ctx.author is None:
        await ctx.channel.send("I don't know who you are!")
        return
    # requires the user to have opened a DM channel first
    await ctx.author.dm_channel.send("hi there!")


@bot.command("whoami")
async def whoami(ctx: Context) -> None:
    author = ctx.message.author
    if author is None:
        await ctx.reply("I don't know who you are!")
        return
    await ctx.reply(f"You are {author.name} (id {author.id}).")


if __name__ == "__main__":
    run(bot.connect(token="..."))
