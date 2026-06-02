from osmium_chat.bot import Bot

from asyncio import run
from logging import DEBUG, Formatter, StreamHandler, getLogger

from osmium_chat.content import Bold, Code, CodeBlock, Content, Italic, Strikethrough, Underline
from osmium_chat.context import Context


logger = getLogger("osmium_chat")
logger.setLevel(DEBUG)
_handler = StreamHandler()
_handler.setFormatter(Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logger.addHandler(_handler)


bot = Bot(
    prefix="!",
    client_id=150896,
    logger=logger,
)


@bot.on("connect")
async def on_connect() -> None:
    logger.info("Bot connected to WebSocket server")
    # await bot.use_invite("your_invite_code_here")


@bot.on("message")
async def on_message(ctx: Context) -> None:
    # Fires for every message; ctx.message.author is the resolved sender.
    who = ctx.message.author.name if ctx.message.author else "someone"
    logger.info("message from %s: %s", who, ctx.message.content)


@bot.on("guild_message")
async def on_guild_message(ctx: Context) -> None:
    logger.info("guild message in channel: %s", ctx.message.content)


@bot.on("dm_message")
async def on_dm_message(ctx: Context) -> None:
    logger.info("dm message: %s", ctx.message.content)


@bot.command("say")
async def say(ctx: Context, *, words: str | None = None) -> None:
    words = words or "You didn't say anything!"
    await ctx.channel.send(words)


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


@bot.command("sum")
async def sum_(ctx: Context, *numbers: int) -> None:
    await ctx.channel.send(str(sum(numbers)))


@bot.command("dm")
async def dm(ctx: Context) -> None:
    if ctx.author is None:
        await ctx.channel.send("I don't know who you are!")
        return
    # currently requires users to create the dm channel
    await ctx.author.dm_channel.send("hi there!")


@bot.command("whoami")
async def whoami(ctx: Context) -> None:
    author = ctx.message.author
    if author is None:
        await ctx.reply("I don't know who you are!")
        return
    await ctx.reply(f"You are {author.name} (id {author.id})")


@bot.command("editmsg")
async def editmsg(ctx: Context) -> None:
    # channel.send() returns the created Message, so we can edit (or delete) it.
    message = await ctx.channel.send("This message will edit itself...")
    await message.edit("(edited by the bot)")


@bot.command("delete")
async def delete(ctx: Context) -> None:
    # Delete the message that invoked the command.
    await ctx.message.delete()


@bot.command("newchannel")
async def newchannel(ctx: Context, *, name: str = "general") -> None:
    if ctx.community is None:
        await ctx.reply("Run this in a community channel!")
        return
    channel = await ctx.community.create_channel(name=name)
    await ctx.reply(f"Created a new #{channel.id} channel!")


@bot.command("rename")
async def rename(ctx: Context, *, name: str) -> None:
    # Edit the current channel's name in place.
    await ctx.channel.edit(name=name)


@bot.command("nukechannel")
async def nukechannel(ctx: Context) -> None:
    # Delete the channel this command was invoked in.token
    await ctx.channel.delete()


if __name__ == "__main__":
    run(bot.connect(
        token="...",
    ))
