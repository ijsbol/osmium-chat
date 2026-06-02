"""Mention argument demo.

Commands
--------
!whois @<username>      -- resolve a user mention and echo it back
!whorole &<name>        -- resolve a role by name and echo it
!whochannel #<name>     -- resolve a channel by name and echo it
!whocategory #<name>    -- resolve a category by name and echo it
!whoemoji :name:        -- resolve a custom emoji by name and echo it back
!whouni <emoji>         -- echo a unicode emoji back
"""

from asyncio import run
from logging import DEBUG, Formatter, StreamHandler, getLogger

from osmium_chat.bot import Bot
from osmium_chat.category import Category
from osmium_chat.channel import Channel
from osmium_chat.content import Content, UnicodeEmoji
from osmium_chat.context import Context
from osmium_chat.emoji import CustomEmoji
from osmium_chat.mentions import UserMention
from osmium_chat.role import Role
from osmium_chat.user.user import User


logger = getLogger("osmium_chat")
logger.setLevel(DEBUG)
_handler = StreamHandler()
_handler.setFormatter(Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logger.addHandler(_handler)

bot = Bot(prefix="!", client_id=00000, logger=logger)


@bot.on("connect")
async def on_connect() -> None:
    logger.info("Bot connected")


@bot.command("whois")
async def whois(ctx: Context, user: User) -> None:
    """!whois @<username> — resolve a user mention and echo it back as an entity."""
    await ctx.channel.send(Content(UserMention(user), f" (name: {user.name!r})"))


@bot.command("whorole")
async def whorole(ctx: Context, role: Role) -> None:
    """!whorole &<name> — resolve a role by name and echo it."""
    await ctx.reply(f"That role is {role.name!r} (id {role.id})")


@bot.command("whochannel")
async def whochannel(ctx: Context, channel: Channel) -> None:
    """!whochannel #<name> — resolve a channel by name and echo it."""
    await ctx.reply(f"That channel is #{channel.name} (id {channel.id})")


@bot.command("whocategory")
async def whocategory(ctx: Context, category: Category) -> None:
    """!whocategory #<name> — resolve a category by name and echo it."""
    child_names = ", ".join(f"#{c.name}" for c in category.channels) or "(empty)"
    await ctx.reply(f"That category is {category.name!r} — channels: {child_names}")


@bot.command("whoemoji")
async def whoemoji(ctx: Context, emoji: CustomEmoji) -> None:
    """!whoemoji :name: — resolve a custom emoji by name and echo it back."""
    await ctx.reply(Content(f"Found custom emoji ", emoji, f" (id {emoji.id})"))


@bot.command("whouni")
async def whouni(ctx: Context, emoji: UnicodeEmoji) -> None:
    """!whouni <emoji> — wrap any token as a UnicodeEmoji and echo it back."""
    await ctx.reply(f"Unicode emoji: {emoji.emoji}")


if __name__ == "__main__":
    run(bot.connect(token="..."))
