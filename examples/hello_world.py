from osmium_chat import Bot
from osmium_chat.context import Context


bot = Bot(
    prefix=">",
    client_id=0000000,
)


@bot.command("hello")
async def hello(ctx: Context) -> None:
    await ctx.channel.send(f"Hello, {ctx.author}!")


if __name__ == "__main__":
    bot.run(
        token="",
    )
