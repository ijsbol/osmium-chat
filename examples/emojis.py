"""Custom emoji management demo.

Commands
--------
!listemojis                         -- list all custom emojis in this community
!createemoji <name> <image_path>    -- upload a PNG as a custom emoji
!deleteemoji :name:                 -- delete a custom emoji by mention
!renameemoji :name: <new_name>      -- rename a custom emoji locally
!sendemoji :name:                   -- send a message containing a custom emoji
"""

from asyncio import run
from logging import DEBUG, Formatter, StreamHandler, getLogger
from pathlib import Path

from osmium_chat import Bot, Context, commands
from osmium_chat.content import Content
from osmium_chat.emoji import CustomEmoji


logger = getLogger("osmium_chat")
logger.setLevel(DEBUG)
_handler = StreamHandler()
_handler.setFormatter(Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logger.addHandler(_handler)

bot = Bot(prefix="!", client_id=150896, logger=logger)


class EmojiCommands(commands.Commands):
    @commands.listen("connect")
    async def on_connect(self) -> None:
        logger.info("Bot connected")

    @commands.guild_command("listemojis")
    async def listemojis(self, ctx: Context) -> None:
        assert ctx.community is not None
        emojis = await ctx.community.fetch_custom_emojis()
        if not emojis:
            await ctx.reply("This community has no custom emojis.")
            return
        parts: list = [f"Custom emojis in {ctx.community.name}:"]
        for emoji in emojis:
            parts.append("\n  ")
            parts.append(emoji)
            parts.append(f" {emoji.name}")
        await ctx.channel.send(Content(*parts))

    @commands.guild_command("createemoji")
    async def createemoji(self, ctx: Context, name: str, image_path: str) -> None:
        assert ctx.community is not None
        path = Path(image_path)
        if not path.exists():
            await ctx.reply(f"File not found: {image_path}")
            return
        image = path.read_bytes()
        mimetype = "image/png" if path.suffix.lower() == ".png" else "image/webp"
        emoji = await ctx.community.create_custom_emoji(image, name, mimetype=mimetype)
        await ctx.reply(f"Created :{emoji.name}: (id {emoji.id}).")

    @commands.command("deleteemoji")
    async def deleteemoji(self, ctx: Context, emoji: CustomEmoji) -> None:
        await emoji.delete()
        await ctx.reply(f"Deleted :{emoji.name}:.")

    @commands.command("renameemoji")
    async def renameemoji(self, ctx: Context, emoji: CustomEmoji, new_name: str) -> None:
        old_name = emoji.name
        emoji.rename(new_name)
        await ctx.reply(f"Renamed :{old_name}: → :{new_name}: (local only).")

    @commands.command("sendemoji")
    async def sendemoji(self, ctx: Context, emoji: CustomEmoji) -> None:
        await ctx.channel.send(Content("Here it is: ", emoji))


bot.add_commands(EmojiCommands)

if __name__ == "__main__":
    run(bot.connect(token="..."))
