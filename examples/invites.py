"""Invite management demo.

Commands
--------
!create_invite              -- create an invite for the current channel
!get_invites                -- list all active invites for the current channel
!lookup_invite <code>       -- look up an invite's metadata by code
!join <code>                -- join via an invite code
"""

from asyncio import run
from logging import DEBUG, Formatter, StreamHandler, getLogger

from osmium_chat.bot import Bot
from osmium_chat.context import Context


logger = getLogger("osmium_chat")
logger.setLevel(DEBUG)
_handler = StreamHandler()
_handler.setFormatter(Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logger.addHandler(_handler)

bot = Bot(prefix="!", client_id=00000, logger=logger)


@bot.on("connect")
async def on_connect() -> None:
    logger.info("Bot connected")


@bot.command("create_invite")
async def create_invite(ctx: Context) -> None:
    invite = await ctx.channel.create_invite()
    await ctx.reply(f"Invite created: https://osmium.chat/i/{invite.code}")


@bot.command("get_invites")
async def get_invites(ctx: Context) -> None:
    invites = await ctx.channel.get_invites()
    if not invites:
        await ctx.reply("No active invites for this channel.")
        return
    lines = ["Active invites:"]
    for invite in invites:
        expires = f", expires {invite.expires_at}" if invite.expires_at else ""
        lines.append(f"  {invite.code} — creator {invite.creator_id}{expires}")
    await ctx.reply("\n".join(lines))


@bot.command("lookup_invite")
async def lookup_invite(ctx: Context, code: str) -> None:
    invite = await ctx.bot.lookup_invite(code)
    expires = f", expires {invite.expires_at}" if invite.expires_at else ""
    await ctx.reply(
        f"{code}: type={invite.target_type.name}, target={invite.target_id}, "
        f"creator={invite.creator_id}{expires}"
    )


@bot.command("join")
async def join(ctx: Context, code: str) -> None:
    await ctx.bot.use_invite(code)
    await ctx.reply(f"Joined via {code}.")


if __name__ == "__main__":
    run(bot.connect(token="..."))
