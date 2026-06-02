"""Category management demo.

Commands
--------
!newcategory <name>              -- create a category in this community
!newchannel <category> <channel> -- create a channel nested under a category
!categories                      -- list all categories and their channels
!deletecategory <name>           -- delete a category and all its child channels
!movechannel <channel> <category>-- move an existing channel into a category
"""

from asyncio import run
from logging import DEBUG, Formatter, StreamHandler, getLogger

from osmium_chat.bot import Bot
from osmium_chat.commands import CommandRestriction
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


@bot.command("newcategory", restriction=CommandRestriction.COMMUNITY_ONLY)
async def newcategory(ctx: Context, *, name: str) -> None:
    assert ctx.community is not None
    category = await ctx.community.create_category(name)
    await ctx.reply(f"Created category \"{category.name}\" (id {category.id}).")


@bot.command("newchannel", restriction=CommandRestriction.COMMUNITY_ONLY)
async def newchannel(ctx: Context, category_name: str, *, channel_name: str) -> None:
    assert ctx.community is not None
    await ctx.community.fetch_channels()
    parent = next(
        (c for c in ctx.community.categories if c.name == category_name), None
    )
    if parent is None:
        await ctx.reply(f"No category named \"{category_name}\" found.")
        return
    channel = await ctx.community.create_channel(channel_name, parent_id=parent.id)
    await ctx.reply(f"Created #{channel.name} (id {channel.id}) under \"{parent.name}\".")


@bot.command("categories", restriction=CommandRestriction.COMMUNITY_ONLY)
async def categories(ctx: Context) -> None:
    assert ctx.community is not None
    await ctx.community.fetch_channels()
    cats = ctx.community.categories
    if not cats:
        await ctx.reply("No categories in this community.")
        return
    lines: list[str] = []
    for cat in cats:
        child_names = ", ".join(f"#{c.name}" for c in cat.channels) or "(empty)"
        lines.append(f"[{cat.name}]: {child_names}")
    uncategorised = [c for c in ctx.community.channels if c.category is None]
    if uncategorised:
        lines.append(f"(uncategorised): {', '.join(f'#{c.name}' for c in uncategorised)}")
    await ctx.reply("\n".join(lines))


@bot.command("deletecategory", restriction=CommandRestriction.COMMUNITY_ONLY)
async def deletecategory(ctx: Context, *, name: str) -> None:
    assert ctx.community is not None
    await ctx.community.fetch_channels()
    target = next((c for c in ctx.community.categories if c.name == name), None)
    if target is None:
        await ctx.reply(f"No category named \"{name}\" found.")
        return
    for child in list(target.channels):
        await child.delete()
    await target.delete()
    await ctx.reply(f"Deleted \"{name}\" and {len(target.channels)} child channel(s).")


@bot.command("movechannel", restriction=CommandRestriction.COMMUNITY_ONLY)
async def movechannel(ctx: Context, channel_name: str, *, category_name: str) -> None:
    assert ctx.community is not None
    await ctx.community.fetch_channels()
    target_channel = next(
        (c for c in ctx.community.channels if c.name == channel_name), None
    )
    if target_channel is None:
        await ctx.reply(f"No channel named \"{channel_name}\" found.")
        return
    target_cat = next(
        (c for c in ctx.community.categories if c.name == category_name), None
    )
    if target_cat is None:
        await ctx.reply(f"No category named \"{category_name}\" found.")
        return
    await target_channel.edit(parent_id=target_cat.id)
    await ctx.reply(f"Moved #{target_channel.name} into \"{target_cat.name}\".")


if __name__ == "__main__":
    run(bot.connect(token="..."))
