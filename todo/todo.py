import asyncio
import json
import re
from redbot.core import Config, checks, commands
from redbot.core.utils.chat_formatting import box, inline, pagify


class Todo(commands.Cog):
    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.config = Config.get_conf(self, identifier=7000)
        self.config.register_user(todos={'todo':[]}, focus='todo')

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
        todos = await self.config.user(ctx.author).todos()
        focus = await self.config.user(ctx.author).focus()
        todo = todos[focus]

        msg = focus.title() + ":\n"
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
        focus = await self.config.user(ctx.author).focus()
        async with self.config.user(ctx.author).todos() as todos:
            todos[focus].append(item)
            await ctx.send(inline("Added as item #{}.".format(len(todos[focus]))))

    @todo.command(aliases=['rm', 'finish', 'complete'])
    async def remove(self, ctx, number: int):
        """Remove the nth item from your todo list."""
        focus = await self.config.user(ctx.author).focus()
        async with self.config.user(ctx.author).todos() as todos:
            if len(todos[focus]) < number or number < 1:
                await ctx.send(inline("Your todo list isn't that long"))
                return
            item = todos[focus].pop(number - 1)
            await ctx.send(inline("Removed '{}' from your todo list.".format(item)))

    @todo.command(aliases=[])
    async def purge(self, ctx):
        """Remove the nth item from your todo list."""
        focus = await self.config.user(ctx.author).focus()
        if not await tsutils.confirm_message(ctx, "Are you sure you want to clear the todo list '{}'?".format(focus)):
            return
        async with self.config.user(ctx.author).todos() as todos:
            todos[focus] = []
            await ctx.tick()

    @todo.command()
    async def edit(self, ctx, number: int, *, new_item):
        """Edit/Reword the nth item of your todo list."""
        focus = await self.config.user(ctx.author).focus()
        async with self.config.user(ctx.author).todos() as todos:
            if len(todos[focus]) < number or number < 1:
                await ctx.send(inline("Your todo list isn't that long"))
                return
            old_item = todos[focus][number - 1]
            todos[focus][number - 1] = new_item
            await ctx.send(inline("Edited '{}' to '{}'.".format(old_item, new_item)))

    @todo.command()
    async def prioritize(self, ctx, number: int):
        """Move the nth item to number 1 in your todo list."""
        focus = await self.config.user(ctx.author).focus()
        async with self.config.user(ctx.author).todos() as todos:
            if len(todos[focus]) < number or number < 1:
                await ctx.send(inline("Your todo list isn't that long"))
                return
            item = todos[focus].pop(number - 1)
            todos[focus].insert(0, item)
            await ctx.send(inline("Moved '{}' to the top of your todo list.".format(item)))

    @todo.command(aliases=['focus'])
    async def changelist(self, ctx, name):
        """Focus on a different list."""
        name = name.lower()
        lists = await self.config.user(ctx.author).todos()
        if name not in lists:
            await ctx.send("You don't have a list named that.")
            return
        await self.config.user(ctx.author).focus.set(name)
        await ctx.tick()

    @todo.group()
    async def lists(self, ctx):
        """Commands relating to alternate todo lists!"""

    @lists.command(name="add")
    async def lists_add(self, ctx, name):
        """Add a new list"""
        name = name.lower()
        async with self.config.user(ctx.author).todos() as todos:
            todos[name] = []
        await ctx.tick()

    @lists.command(name="remove", aliases=['rm','delete'])
    async def lists_remove(self, ctx, name):
        """Remove a todo list"""
        name = name.lower()
        if name == "todo":
            await ctx.send(inline("You cannot delete this list."))
            return
        async with self.config.user(ctx.author).todos() as todos:
            if name in todos:
                del todos[name]
        if name == await self.config.user(ctx.author).focus():
            await self.config.user(ctx.author).focus.set("todo")
        await ctx.tick()

    @lists.command(name="get", aliases=['list'])
    async def lists_get(self, ctx):
        """List your lists"""
        todo = await self.config.user(ctx.author).todos()

        msg = "Todo Lists:\n"
        for c, item in enumerate(todo, 1):
            msg += "{}) {}\n".format(str(c).rjust(len(str(len(todo)))), item)
        msg = msg.rstrip()
        for page in pagify(msg):
            await ctx.send(box(page))
