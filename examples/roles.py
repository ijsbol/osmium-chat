"""Role management demo.

Commands
--------
!listroles                          -- list all roles in the community
!myroles                            -- show your own roles
!memberroles <@user>                -- show a member's roles
!addrole <@user> <role>             -- add a role to a member
!removerole <@user> <role>          -- remove a role from a member
"""

from asyncio import run
from logging import DEBUG, Formatter, StreamHandler, getLogger

from osmium_chat import Bot, Context, commands
from osmium_chat.member import Member
from osmium_chat.role import Role


logger = getLogger("osmium_chat")
logger.setLevel(DEBUG)
_handler = StreamHandler()
_handler.setFormatter(Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logger.addHandler(_handler)

bot = Bot(prefix="!", client_id=00000, logger=logger)


class RoleCommands(commands.Commands):
    @commands.listen("connect")
    async def on_connect(self) -> None:
        logger.info("Bot connected")

    @commands.guild_command("listroles")
    async def listroles(self, ctx: Context) -> None:
        assert ctx.community is not None
        await ctx.community.fetch_roles()
        roles = ctx.community.roles
        if not roles:
            await ctx.reply("This community has no roles.")
            return
        lines = ["Roles in this community:"]
        for role in roles:
            lines.append(f"  {role.name} (id {role.id}, priority {role.priority})")
        await ctx.reply("\n".join(lines))

    @commands.guild_command("myroles")
    async def myroles(self, ctx: Context) -> None:
        assert ctx.community is not None
        if not isinstance(ctx.author, Member):
            await ctx.reply("Could not resolve your member data.")
            return
        roles = ctx.author.roles
        if not roles:
            await ctx.reply("You have no roles.")
            return
        await ctx.reply("Your roles: " + ", ".join(r.name for r in roles))

    @commands.guild_command("memberroles")
    async def memberroles(self, ctx: Context, member: Member) -> None:
        roles = member.roles
        if not roles:
            await ctx.reply(f"{member.display_name} has no roles.")
            return
        await ctx.reply(f"{member.display_name}'s roles: " + ", ".join(r.name for r in roles))

    @commands.guild_command("addrole")
    async def addrole(self, ctx: Context, member: Member, role: Role) -> None:
        await member.add_role(role)
        await ctx.reply(f"Added role {role.name!r} to {member.display_name}.")

    @commands.guild_command("removerole")
    async def removerole(self, ctx: Context, member: Member, role: Role) -> None:
        await member.remove_role(role)
        await ctx.reply(f"Removed role {role.name!r} from {member.display_name}.")


bot.add_commands(RoleCommands)

if __name__ == "__main__":
    run(bot.connect(token="..."))
