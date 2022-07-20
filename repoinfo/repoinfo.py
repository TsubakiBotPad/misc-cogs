from collections import namedtuple
from io import BytesIO

import discord.utils
from redbot.core import commands
from redbot.core.utils.chat_formatting import box, inline, pagify

EmbedField = namedtuple("EmbedField", "name value inline")


class RepoInfo(commands.Cog):
    """A cog to get information about specific repos or cogs

    Credit to Red and d.py for some of this oh god save me
    """

    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        data = "No data is stored for user with ID {}.\n".format(user_id)
        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data.

        No personal data is stored in this cog.
        """
        return

    @commands.command()
    async def repoinfo(self, ctx, repo_name):
        DLCOG = self.bot.get_cog("Downloader")
        if DLCOG is None:
            await ctx.send(inline("Downloader cog not loaded."))
            return
        repo = DLCOG._repo_manager.get_repo(repo_name)
        if repo is None:
            await ctx.send(box("Repo not found.\n\nAvaliable Repos:\n" +
                               "\n".join(
                                   DLCOG._repo_manager.get_all_repo_names())))
            return
        extensions = [i.name for i in repo.available_cogs]
        cogs = filter(lambda x: x.__module__.split(".")[0] in extensions,
                      self.bot.cogs.values())

        hs = await commands.help.HelpSettings.from_context(ctx)
        rhf = commands.help.RedHelpFormatter()
        coms = [(
            cog.__cog_name__,
            await commands.help.RedHelpFormatter().get_cog_help_mapping(ctx, cog, hs)
        ) for cog in cogs]

        if not coms:
            await ctx.send(inline("There are no loaded cogs on the repo!"))
            return

        if await ctx.embed_requested():

            emb = {"embed": {"title": "", "description": ""},
                   "footer": {"text": ""}, "fields": []}

            for cog_name, data in coms:

                if cog_name:
                    title = f"**__{cog_name}:__**"
                else:
                    title = "**__No Category:__**"

                def shorten_line(a_line: str) -> str:
                    if len(a_line) < 70:
                        return a_line
                    return a_line[:67] + "..."

                cog_text = "\n".join(
                    shorten_line(
                        f"**{name}** {command.format_shortdoc_for_context(ctx)}")
                    for name, command in sorted(data.items())
                )

                for i, page in enumerate(
                        pagify(cog_text, page_length=1000, shorten_by=0)):
                    title = title if i < 1 else f"{title} (continued)"
                    field = EmbedField(title, page, False)
                    emb["fields"].append(field)

            await rhf.make_and_send_embeds(ctx, emb, help_settings=hs)

        else:
            to_join = ["Commands for {}:\n".format(repo_name)]

            names = []
            for k, v in coms:
                names.extend(list(v.name for v in v.values()))

            max_width = max(
                discord.utils._string_width(name or "No Category:") for name in
                names)

            def width_maker(cmds):
                doc_max_width = 80 - max_width
                for nm, com in cmds:
                    width_gap = discord.utils._string_width(nm) - len(nm)
                    doc = com.format_shortdoc_for_context(ctx)
                    if len(doc) > doc_max_width:
                        doc = doc[: doc_max_width - 3] + "..."
                    yield nm, doc, max_width - width_gap

            for cog_name, data in coms:

                title = f"{cog_name}:" if cog_name else "No Category:"
                to_join.append(title)

                for name, doc, width in width_maker(sorted(data.items())):
                    to_join.append(f"  {name:<{width}} {doc}")

            to_page = "\n".join(to_join)
            pages = [box(p) for p in pagify(to_page)]
            await rhf.send_pages(ctx, pages, embed=False, help_settings=hs)

    @commands.command()
    async def coginfo(self, ctx, cog_name):
        cog = self.bot.get_cog(cog_name)
        if cog is None and cog_name in self.bot.extensions:
            cog_name = self.bot.extensions[cog_name].__name__
            for cog in self.bot.cogs.values():
                if cog.__module__.startswith(cog_name + '.') or cog.__module__ == cog_name:
                    break
        else:
            return await ctx.send(f"Cog `{cog_name}` not found.")

        hs = await commands.help.HelpSettings.from_context(ctx)
        rhf = commands.help.RedHelpFormatter()
        cog_name = cog.__cog_name__
        data = await commands.help.RedHelpFormatter().get_cog_help_mapping(ctx, cog, hs)

        if await ctx.embed_requested():
            emb = {"embed": {"title": "", "description": ""},
                   "footer": {"text": f"For more help, use {ctx.prefix}help <command_name>"}, "fields": []}

            title = f"**__{cog.__module__.split('.')[0]}:__**"

            def shorten_line(a_line: str) -> str:
                if len(a_line) < 70:
                    return a_line
                return a_line[:67] + "..."

            cog_text = "\n".join(
                shorten_line(
                    f"**{name}** {command.format_shortdoc_for_context(ctx)}")
                for name, command in sorted(data.items())
            )

            for i, page in enumerate(
                    pagify(cog_text, page_length=1000, shorten_by=0)):
                title = title if i < 1 else f"{title} (continued)"
                field = EmbedField(title, page, False)
                emb["fields"].append(field)

            await rhf.make_and_send_embeds(ctx, emb, help_settings=hs)

        else:
            to_join = ["Commands for {}:\n".format(cog_name)]

            names = []
            names.extend(list(v.name for v in data.values()))

            max_width = max(
                discord.utils._string_width(name or "No Category:") for name in
                names)

            def width_maker(cmds):
                doc_max_width = 80 - max_width
                for nm, com in cmds:
                    width_gap = discord.utils._string_width(nm) - len(nm)
                    doc = com.format_shortdoc_for_context(ctx)
                    if len(doc) > doc_max_width:
                        doc = doc[: doc_max_width - 3] + "..."
                    yield nm, doc, max_width - width_gap

            to_join.append(cog_name + ":")

            for name, doc, width in width_maker(sorted(data.items())):
                to_join.append(f"  {name:<{width}} {doc}")

            to_page = "\n".join(to_join)
            pages = [box(p) for p in pagify(to_page)]
            await rhf.send_pages(ctx, pages, embed=False, help_settings=hs)
