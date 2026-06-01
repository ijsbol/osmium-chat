from osmium_chat.bot import Bot

from asyncio import run
from logging import DEBUG, Formatter, StreamHandler, getLogger

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


@bot.command("say")
async def say(ctx: Context, *, words: str | None = None) -> None:
    words = words or "You didn't say anything!"
    await ctx.channel.send(words)


@bot.command("sum")
async def sum_(ctx: Context, *numbers: int) -> None:
    await ctx.channel.send(str(sum(numbers)))


if __name__ == "__main__":
    run(bot.connect(
        token="...",
    ))
