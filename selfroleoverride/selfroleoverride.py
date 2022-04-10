from io import BytesIO

from redbot.core import commands
from redbot.core.utils.chat_formatting import box
from tsutils.converters import CaseInsensitiveRole


class SelfRoleOverride(commands.Cog):
    """Overrides of builtin commands"""

    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.old_cmds = []
        for cmd in self.all_commands:
            old_cmd = bot.get_command(cmd)
            if old_cmd:
                bot.remove_command(old_cmd.name)
                self.old_cmds.append(old_cmd)

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        data = "No data is stored for user with ID {}.\n".format(user_id)
        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data.

        No personal data is stored in this cog.
        """
        return

    def cog_unload(self):
        if self.bot.get_cog("Admin") is not None:
            for cmd in self.old_cmds:
                try:
                    self.bot.remove_command(cmd.name)
                except Exception:
                    pass
                self.bot.add_command(cmd)

    @commands.guild_only()
    @commands.group()
    async def selfrole(self, ctx: commands.Context):
        """Apply selfroles."""
        pass

    @selfrole.command(name="add")
    async def selfrole_add(self, ctx: commands.Context, *, selfrole: CaseInsensitiveRole):
        """
        Add a selfrole to yourself.

        Server admins must have configured the role as user settable.
        """
        a_cog = self.bot.get_cog("Admin")
        selfroles = await a_cog._valid_selfroles(ctx.guild)
        if selfrole in selfroles:
            await a_cog._addrole(ctx, ctx.author, selfrole, check_user=False)
        else:
            await ctx.send(f"The role {selfrole.name} is not user settable. See `{ctx.prefix}selfrole list` for valid selfroles.")
        

    @selfrole.command(name="remove")
    async def selfrole_remove(self, ctx: commands.Context, *, selfrole: CaseInsensitiveRole):
        """
        Remove a selfrole from yourself.

        Server admins must have configured the role as user settable.
        """
        a_cog = self.bot.get_cog("Admin")
        selfroles = await a_cog._valid_selfroles(ctx.guild)
        if selfrole in selfroles:
            await a_cog._removerole(ctx, ctx.author, selfrole, check_user=False)
        else:
            await ctx.send(f"The role {selfrole.name} is not user settable. See `{ctx.prefix}selfrole list` for valid selfroles.")

    @selfrole.command(name="list")
    async def selfrole_list(self, ctx: commands.Context):
        """Lists all available selfroles."""
        a_cog = self.bot.get_cog("Admin")
        if a_cog is None:
            await ctx.send("Admin cog not loaded.")

        selfroles = await a_cog._valid_selfroles(ctx.guild)
        fmt_selfroles = "\n".join(["+ " + r.name for r in selfroles])

        if not fmt_selfroles:
            await ctx.send("There are currently no selfroles.")
            return

        msg = "Available Selfroles:\n{selfroles}".format(selfroles=fmt_selfroles)
        await ctx.send(box(msg, "diff"))
