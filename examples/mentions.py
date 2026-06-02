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

from osmium_chat import Bot, Context, commands
from osmium_chat.category import Category
from osmium_chat.channel import Channel
from osmium_chat.content import Content, UnicodeEmoji
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


class MentionCommands(commands.Commands):
    @commands.listen("connect")
    async def on_connect(self) -> None:
        logger.info("Bot connected")

    @commands.command("whois")
    async def whois(self, ctx: Context, user: User) -> None:
        await ctx.channel.send(Content(UserMention(user), f" (name: {user.name!r})"))

    @commands.command("whorole")
    async def whorole(self, ctx: Context, role: Role) -> None:
        await ctx.reply(f"That role is {role.name!r} (id {role.id})")

    @commands.command("whochannel")
    async def whochannel(self, ctx: Context, channel: Channel) -> None:
        await ctx.reply(f"That channel is #{channel.name} (id {channel.id})")

    @commands.command("whocategory")
    async def whocategory(self, ctx: Context, category: Category) -> None:
        child_names = ", ".join(f"#{c.name}" for c in category.channels) or "(empty)"
        await ctx.reply(f"That category is {category.name!r} — channels: {child_names}")

    @commands.command("whoemoji")
    async def whoemoji(self, ctx: Context, emoji: CustomEmoji) -> None:
        await ctx.reply(Content(f"Found custom emoji ", emoji, f" (id {emoji.id})"))

    @commands.command("whouni")
    async def whouni(self, ctx: Context, emoji: UnicodeEmoji) -> None:
        await ctx.reply(f"Unicode emoji: {emoji.emoji}")


bot.add_commands(MentionCommands)

if __name__ == "__main__":
    run(bot.connect(token="..."))
