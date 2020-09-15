import json
import re
import asyncio

from redbot.core import checks, commands, Config
from redbot.core.utils.chat_formatting import box, pagify, inline


class Todo(commands.Cog):
    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.config = Config.get_conf(self, identifier=7000)
        self.config.register_user(todo=[])

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        udata = await self.config.user_from_id(user_id).ans()

        data = "\n".join(udata)

        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data."""
        await self.config.user_from_id(user_id).clear()

    @commands.group()
    async def todo(self, ctx):
        """Manage your todo list."""

    @todo.command(aliases=['show'])
    async def list(self, ctx):
        """View your todo list."""
        todo = await self.config.user(ctx.author).todo()
        msg = ""
        for c, item in enumerate(todo, 1):
            msg += "{}) {}\n".format(str(c).rjust(len(str(len(todo)))), item)
        msg = msg.rstrip()
        if not msg:
            await ctx.send(inline("Your todo list is empty.  Yay!"))
        for page in pagify(msg):
            await ctx.send(box(page))

    @todo.command()
    async def add(self, ctx, *, item):
        """Add an item to your todo list."""
        async with self.config.user(ctx.author).todo() as todo:
            todo.append(item)
            await ctx.send(inline("Added as item #{}.".format(len(todo))))

    @todo.command(aliases=['rm', 'finish', 'complete'])
    async def remove(self, ctx, number: int):
        """Remove the nth item from your todo list."""
        async with self.config.user(ctx.author).todo() as todo:
            if len(todo) < number or number < 1:
                await ctx.send(inline("Your todo list isn't that long"))
                return
            item = todo.pop(number-1)
            await ctx.send(inline("Removed '{}' from your todo list.".format(item)))

    @todo.command()
    async def edit(self, ctx, number: int, *, new_item):
        """Edit/Reword the nth item of your todo list."""
        async with self.config.user(ctx.author).todo() as todo:
            if len(todo) < number or number < 1:
                await ctx.send(inline("Your todo list isn't that long"))
                return
            old_item = todo[number-1]
            todo[number-1] = new_item
            await ctx.send(inline("Edited '{}' to '{}'.".format(old_item, new_item)))

    @todo.command()
    async def prioritize(self, ctx, number: int):
        """Move the nth item to number 1 in your todo list."""
        async with self.config.user(ctx.author).todo() as todo:
            if len(todo) < number or number < 1:
                await ctx.send(inline("Your todo list isn't that long"))
                return
            item = todo.pop(number-1)
            todo.insert(0, item)
            await ctx.send(inline("Moved '{}' to the top of your todo list.".format(item)))
