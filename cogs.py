import asyncio
import uuid
import re
import os
import random
import math

from discord import File, Embed
from discord.ext import commands
from discord.ext.commands import UserConverter, CommandError
from datetime import timedelta
from html_profile.generator import generate_profile_html
from html_profile.renderer import render_html_from_string
from utils import is_vaild_url

class BotErr(CommandError):
    def __init__(self, text):
        self.text = text

    def __str__(self):
        return self.text

    @staticmethod
    def raise_if(cond, text):
        if cond:
            raise BotErr(text)

class InvalidNumArguments(BotErr):
    def __init__(self):
        super().__init__('Invalid number of arguments.')

class InvalidUrl(BotErr):
    def __init__(self):
        super().__init__('Invalid URL.')

class InvalidCog(BotErr):
    def __init__(self):
        super().__init__('Invalid cog name.')

def require_admin_privilege(ctx):
    if 'bot commander' not in map(lambda x: x.name.lower(), ctx.message.author.roles):
        raise BotErr('"Bot Commander" role required.')

def table_format(data, min_col_spacing=None):
    def flatten(T):
        if type(T) is not tuple:
            return (T,)
        elif len(T) == 0:
            return ()
        else:
            return flatten(T[0]) + flatten(T[1:])

    data = [flatten(x) for x in data]

    num_cols = len(data[0])
    max_lens = [0] * num_cols
    for row in data:
        for i in range(num_cols):
            max_lens[i] = max(len(str(row[i])), max_lens[i])

    if min_col_spacing is None:
        min_col_spacing = [1] * num_cols

    s = ''
    for row in data:
        for i in range(num_cols):
            x = str(row[i])
            s += x + ' ' * (max_lens[i] - len(x) + min_col_spacing[i])
        s += '\n'
    return s

async def user_or_none(ctx, s):
    try:
        return await UserConverter().convert(ctx, s)
    except:
        return None

def short_fmt(t):
    return t.strftime('%d %b')

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        require_admin_privilege(ctx)
        return True

    @commands.command()
    async def add_pool(self, ctx, name: str):
        '''
        !add_pool name
        [Admin only] Adds a new pool for the challenge
        '''
        await self.bot.add_pool(ctx, name)
        await ctx.send(f'Pool "{name}" has been created.')
        await self.bot.sync(ctx)

    @commands.command()
    async def add_title(self, ctx, *args):
        '''
        !add_title [pool='main'] @user title [url]
        [Admin only] Adds a title for specified user
        '''

        if len(args) < 2 or len(args) > 4:
            raise InvalidNumArguments()

        pool = 'main'
        url = None
        user = await user_or_none(ctx, args[0])
        title = args[1]

        if user is None:
            if len(args) < 3:
                raise InvalidNumArguments()
            if len(args) == 4:
                url = args[-1]
            pool = args[0]
            title = args[2]
            user = await UserConverter().convert(ctx, args[1])
        elif len(args) == 3:
            url = args[-1]

        await self.bot.add_title(ctx, pool, user, title, url)
        await ctx.send(f'Title "{title}" has been added to "{pool}" pool.')
        await self.bot.sync(ctx)

    @commands.command()
    async def add_title2(self, ctx, user: UserConverter, url: str, **kwargs):
        '''
        !add_title2 @user url [title] [pool='main']
        [Admin only] Adds a title for specified user
        '''
        pool = 'main'
        
        if 'pool' in kwargs:
            pool = kwargs['pool']

        title_info = self.bot.get_api_title_info(url)
        print(title_info)
        if 'title' not in kwargs:
            title = title_info.name
        else:
            title = kwargs['title']

        await self.bot.add_title(ctx, pool, user, title, url)
        await ctx.send(f'Title "{title}" has been added to "{pool}" pool.')
        await self.bot.sync(ctx)

    @commands.command()
    async def add_user(self, ctx, user: UserConverter):
        '''
        !add_user @user
        [Admin only] Adds a new user to the challenge
        '''
        await self.bot.add_user(ctx, user)
        await ctx.send(f'User {user.mention} has been added.')
        await self.bot.sync(ctx)

    @commands.command()
    async def create_poll(self, ctx):
        '''
        !create_poll
        [Admin only] Creates a poll of all titles to vote for which ones people have seen
        '''
        titles = await self.bot.current_titles(ctx)
        for t in titles:
            msg = await ctx.send(t.name)
            await msg.add_reaction('👀')

    @commands.command()
    async def end_challenge(self, ctx):
        '''
        !end_challenge
        [Admin only] Ends current challenge
        '''
        challenge = await self.bot.end_challenge(ctx)
        await ctx.send(f'Challenge "{challenge.name}" has been ended.')

    @commands.command()
    async def end_round(self, ctx):
        '''
        !end_challenge
        [Admin only] Ends current round
        '''
        rnd = await self.bot.end_round(ctx)
        await ctx.send(f'Round {rnd.num} has been ended.')

    @commands.command()
    async def extend_round(self, ctx, days: int):
        '''
        !extend_round days
        [Admin only] Extends the current round by N days
        '''
        if days < 1:
            raise BotErr('Invalid number of days.')
        rnd = await self.bot.extend_round(ctx, days)
        await ctx.send(f'Round {rnd.num} ends on {short_fmt(rnd.finish_time)}.')

    @commands.command()
    async def random_swap(self, ctx, user1: UserConverter, candidate1: UserConverter, *other: UserConverter):
        '''
        !random_swap @user @candidate1 [@candidate2...]
        [Admin only] Swaps user's title with random candidate's title
        '''
        candidates = [candidate1] + list(other)
        if user1 in candidates:
            return await ctx.send("Can't swap titles between the same user.")
        user2 = random.choice(candidates)
        title1, title2 = await self.bot.swap(ctx, user1, user2)
        await ctx.send(f'User {user1.mention} got "{title2}". User "{user2.mention}" got "{title1}".')
        await self.bot.sync(ctx)

    @commands.command()
    async def remove_pool(self, ctx, name: str):
        '''
        !remove_pool name
        [Admin only] Removes a specifed pool
        '''
        await self.bot.remove_pool(ctx, name)
        await ctx.send(f'Pool "{name}" has been removed')
        await self.bot.sync(ctx)

    @commands.command()
    async def remove_title(self, ctx, title: str):
        '''
        !remove_title title
        [Admin only] Removes a specified title
        '''
        await self.bot.remove_title(ctx, title)
        await ctx.send(f'Title "{title}" has been removed')
        await self.bot.sync(ctx)

    @commands.command()
    async def remove_user(self, ctx, user: UserConverter):
        '''
        !remove_user @user
        [Admin only] Removes a specified user
        '''
        await self.bot.remove_user(ctx, user)
        await ctx.send(f'User {user.mention} has been removed.')
        await self.bot.sync(ctx)

    @commands.command()
    async def rename_pool(self, ctx, old_name: str, new_name: str):
        '''
        !rename_pool old_name new_name
        [Admin only] Renames pool
        '''
        await self.bot.rename_pool(ctx, old_name, new_name)
        await ctx.send(f'Pool "{old_name}" has been renamed to "{new_name}"')
        await self.bot.sync(ctx)

    @commands.command()
    async def reroll(self, ctx, user: UserConverter, pool: str = 'main'):
        '''
        !reroll @user [pool=main]
        [Admin only] Reroll titles for a user from a specified pool
        '''
        title = await self.bot.reroll(ctx, user, pool)
        await ctx.send(f'User {user.mention} rolled "{title.name}" from "{pool}" pool.')
        await self.bot.sync(ctx)

    @commands.command()
    async def set_title(self, ctx, user: UserConverter, title: str):
        '''
        !set_title @user title
        [Admin only] Sets a new title for a specified user
        '''
        await self.bot.set_title(ctx, user, title)
        await ctx.send(f'Title "{title}" has been assigned to {user.mention}')
        await self.bot.sync(ctx)

    @commands.command()
    async def start_challenge(self, ctx, name: str):
        '''
        !start_challenge name
        [Admin only] Starts a new challenge with a given name
        '''
        await self.bot.start_challenge(ctx, name)
        await ctx.send(f'Challenge "{name}" has been created.')
        await self.bot.sync(ctx)

    @commands.command()
    async def start_round(self, ctx, days: int, pool: str = 'main'):
        '''
        !start_round days [pool='main']
        [Admin only] Starts a new round of a specified length
        '''
        if days < 1:
            return await ctx.send('Invalid number of days.')

        def reveal_roll(titles, max_length):
            msg = ['```fix']
            for p, r in sorted(titles.items()):
                msg.append(f"{p:<{max_length}} {r}")
            msg.append('```')
            return '\n'.join(msg)

        rnd, rolls = await self.bot.start_round(ctx, days, pool)
        max_length = max([len(a) for a in rolls.keys()]) + 2
        roll_info = {p: '???' for p in rolls.keys()}

        msg = reveal_roll(roll_info, max_length)
        sent = await ctx.send(msg)
        await asyncio.sleep(2)

        for i in sorted(rolls.keys()):
            roll_info[i] = rolls[i]
            msg = reveal_roll(roll_info, max_length)
            await sent.edit(content=msg)
            await asyncio.sleep(1)

        await ctx.send(f'Round {rnd.num} ({short_fmt(rnd.start_time)} - {short_fmt(rnd.finish_time)}) starts right now.')
        await self.bot.sync(ctx)

    @commands.command()
    async def swap(self, ctx, user1: UserConverter, user2: UserConverter):
        '''
        !swap @user1 @user2
        [Admin only] Swaps titles between two users
        '''
        title1, title2 = await self.bot.swap(ctx, user1, user2)
        await ctx.send(f'User {user1.mention} got "{title2.name}". User "{user2.mention}" got "{title1.name}".')
        await self.bot.sync(ctx)

    @commands.command()
    async def set_spreadsheet_key(self, ctx, key: str):
        '''
        !set_spreadsheet_key key
        [Admin only] Sets google sheets key
        '''
        await self.bot.set_spreadsheet_key(ctx, key)
        await ctx.send('Done.')

    @commands.command()
    async def set_award(self, ctx, url: str):
        '''
        !set_award url
        [Admin only] Sets an award for current challenge
        '''
        if not is_vaild_url(url):
            raise InvalidUrl()
        await self.bot.set_award(ctx, url)
        await ctx.send('Done.')

    @commands.command()
    async def add_award(self, ctx, user: UserConverter, url: str):
        '''
        !add_award @user url
        [Admin only] Adds an award for a user
        '''
        if not is_vaild_url(url):
            raise InvalidUrl()
        await self.bot.add_award(ctx, user, url)
        await ctx.send('Done.')

    @commands.command()
    async def remove_award(self, ctx, user: UserConverter, url: str):
        '''
        !add_award @user url
        [Admin only] Removes an award from a user
        '''
        if not is_vaild_url(url):
            raise InvalidUrl()
        await self.bot.remove_award(ctx, user, url)
        await ctx.send('Done.')

    @commands.command()
    async def recalc_karma(self, ctx):
        '''
        !recalc_karma
        [Admin only] Recalculates karama for every user in the guild
        '''
        await self.bot.recalc_karma(ctx)
        await ctx.send('Done.')

class User(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def help(self, ctx, cog_name = None):
        '''
        !help [@cog_name=None]
        Prints this message
        '''
        embed = Embed(title="Help", description='', color=0x0000000)

        if cog_name == None:
            embed.add_field(name='Use one of these', value='\u200b', inline=False)
            for cog_name in self.bot.cogs:
                embed.add_field(name=f'!help {cog_name}', value='\u200b', inline=False)
        else:
            if cog_name in self.bot.cogs:
                commands = []
                cog = self.bot.get_cog(cog_name)
                for command in cog.get_commands():
                    if not command.help:
                        continue
                    lines = command.help.split('\n')
                    desc = lines[-1]
                    name = '\n'.join(lines[:-1])
                    commands.append((name, desc))

                for name, desc in sorted(commands):
                    embed.add_field(name=name, value=desc, inline=False)
            else:
                raise InvalidCog()
        await ctx.send(embed=embed)

    @commands.command()
    async def karma(self, ctx):
        '''
        !karma
        Shows karma table
        '''
        table = table_format(map(lambda x: (str(x[0] + 1) + ')', x[1]), enumerate(await self.bot.karma_table(ctx))))
        await ctx.send(f"```markdown\n{ table }```")

    @commands.command()
    async def profile(self, ctx, user: UserConverter = None):
        '''
        !profile [@user=author]
        Displays user's profile
        '''
        if user is None:
            user = ctx.message.author

        avatar_url = str(user.avatar_url)
        user, stats = await self.bot.user_profile(ctx, user)
        e = Embed(title="", description='', color=int('0x' + user.color[1:], 16))
        e.set_author(name=user.name, icon_url=avatar_url)
        e.set_thumbnail(url=avatar_url)
        if stats.num_challenges > 0:
            e.add_field(name="Challenges", value=str(stats.num_challenges), inline=True)
            e.add_field(name="Completed", value=str(stats.num_completed), inline=True)
            if stats.avg_title_score is not None:
                e.add_field(name="Avg. Score of Your Titles", value=f"{stats.avg_title_score:.2f}", inline=False)
            if stats.avg_rate is not None:
                e.add_field(name="Avg. Score You Give", value=f"{stats.avg_rate:.2f}", inline=True)
            if len(stats.most_watched) > 0:
                e.add_field(name='Watched the most', value=table_format(stats.most_watched), inline=False)
            if len(stats.most_sniped) > 0:
                e.add_field(name='Sniped the most', value=table_format(stats.most_sniped), inline=False)
        else:
            e.add_field(name="No Challenges", value='Empty', inline=True)

        e.add_field(name="Karma", value=str(round(stats.karma, 2)), inline=False)
        karma_urls = [
            'https://i.imgur.com/wscUx1m.png',
            'https://i.imgur.com/wscUx1m.png', # <-- two black hearts
            'https://i.imgur.com/oiypoFr.png',
            'https://i.imgur.com/4MOnqxX.png',
            'https://i.imgur.com/UJ8yOJ8.png',
            'https://i.imgur.com/YoGSX3q.png',
            'https://i.imgur.com/DeKg5P5.png',
            'https://i.imgur.com/byY9AfE.png',
            'https://i.imgur.com/XW4kc66.png',
            'https://i.imgur.com/3pPNCGV.png',
        ]
        url_idx = math.floor(stats.karma / 100)
        url_idx = min(url_idx, len(karma_urls))
        e.set_image(url=karma_urls[url_idx])

        if stats.finish_time is not None:
            e.set_footer(text=f'Round ends on: {stats.finish_time}')

        return await ctx.send(embed=e)

    async def set_progress(self, ctx, user, progress):
        p1 = re.match(r'^(\d{1,2})\/(\d{1,2})$', progress) # x/y
        p2 = re.match(r'^\+(\d{1,2})?$', progress) # +x
        p3 = re.match(r'^(\d{1,2})$', progress) # x
        if p1:
            await self.bot.set_progress(ctx, user, int(p1.group(1)), int(p1.group(2)))
        elif p2:
            await self.bot.add_progress(ctx, user, 1 if p2.group(1) is None else int(p2.group(1)))
        elif p3:
            await self.bot.set_progress(ctx, user, int(p3.group(1)))
        else:
            raise BotErr(f'Invalid progress "{progress}".')
    
    @commands.command()
    async def profile2(self, ctx, user: UserConverter = None):
        '''
        !profile2 [@user=author]
        Displays user's profile
        '''
        if user is None:
            user = ctx.message.author

        avatar_url = str(user.avatar_url).replace("webp", "png")
        user, stats = await self.bot.user_profile(ctx, user)
        html_string = generate_profile_html(user, stats, avatar_url)
        pic_name = render_html_from_string(html_string, css_path="./html_profile/styles.css")
        
        await ctx.send(file=File(pic_name))
        os.remove(pic_name)

    @commands.command()
    async def progress(self, ctx, *args):
        '''
        !progress [@user=author] [x/y|x|+x|+]
        Shows/Updates current progress.
        '''

        if len(args) > 2:
            raise InvalidNumArguments()

        user = ctx.message.author
        progress = None
        if len(args) == 1:
            progress = args[0]
        else:
            user = await UserConverter().convert(ctx, args[0])
            progress = args[1]
            require_admin_privilege(ctx)

        await self.set_progress(ctx, user, progress)
        table = map(lambda x: (x[0], x[1] if x[2] is None else f'{x[1]}/{x[2]}'), await self.bot.progress_table(ctx))
        await ctx.send(f'```\n{table_format(table)}```')

    @commands.command()
    async def prog(self, ctx, *args):
        '''
        !prog
        Shortcut for !progress
        '''
        await self.progress(ctx, *args)

    @commands.command()
    async def rate(self, ctx, *args):
        '''
        !rate [@user=author] score
        Rates user's title with a given score
        '''
        if len(args) != 1 and len(args) != 2:
            raise InvalidNumArguments()

        user = ctx.message.author
        score = None
        if len(args) == 1:
            score = args[0]
        else:
            user = await UserConverter().convert(ctx, args[0])
            score = args[1]
            require_admin_privilege(ctx)

        try:
            score = float(score)
        except:
            return await ctx.send(f'Invalid score "{score}".')
        if score < 0.0 or score > 10.0:
            return await ctx.send('Score must be in range from 0 to 10.')

        title = await self.bot.rate(ctx, user, score)
        await ctx.send(f'User {user.mention} gave {score} to "{title.name}".')
        await self.bot.sync(ctx)

    @commands.command()
    async def rename_title(self, ctx, old_name: str, new_name: str):
        '''
        !rename_title old_name new_name
        Renames a title
        '''
        await self.bot.rename_title(ctx, old_name, new_name)
        await ctx.send(f'Title "{old_name}" has been renamed to "{new_name}".')
        await self.bot.sync(ctx)

    @commands.command()
    async def set_color(self, ctx, *args):
        '''
        !set_color [@user=author] color
        Sets a new color(in hex) for a specified user
        '''

        if len(args) == 1:
            user = ctx.message.author
            color = args[0]
        elif len(args) == 2:
            user = await UserConverter().convert(ctx, args[0])
            color = args[1]
            require_admin_privilege(ctx)
        else:
            raise InvalidNumArguments()

        if re.match(r'^#[a-fA-F0-9]{6}$', color) is None:
            return await ctx.send('Invalid color "{}".'.format(color))

        await self.bot.set_color(user, color)
        await ctx.send('Color has been changed.')
        await self.bot.sync(ctx)

    @commands.command()
    async def set_name(self, ctx, *args):
        '''
        !set_name [@user=author] name
        Sets a new name for a specified user
        '''
        user = ctx.message.author
        if len(args) == 1:
            user = ctx.message.author
            name = args[0]
        elif len(args) == 2:
            user = await UserConverter().convert(ctx, args[0])
            name = args[1]
            require_admin_privilege(ctx)
        else:
            raise InvalidNumArguments()

        if len(name) > 32:
            return await ctx.send('Name is too long. Max is 32 characters.')
        if re.match(r'^[0-9a-zа-яA-ZА-Я_\-]+$', name) is None:
            return await ctx.send('Error: Bad symbols in your name.')

        await self.bot.set_name(user, name)
        await ctx.send(f'{user.mention} got "{name}" as a new name.')
        await self.bot.sync(ctx)

    @commands.command()
    async def sync(self, ctx):
        '''
        !sync
        Syncs current challenge with google sheets doc
        '''
        await self.bot.sync(ctx)
        await ctx.send('Done.')

    @commands.command()
    async def sync_all(self, ctx):
        '''
        !sync_all
        Syncs all guild challenges with google sheets doc
        '''
        await self.bot.sync_all(ctx)
        await ctx.send('Done.')

    @commands.command()
    async def karma_graph(self, ctx, *args):
        '''
        !karma_graph [@user=author]
        Shows a karma graph of a user
        '''
        users = [ ctx.message.author ]
        if len(args) > 0:
            users = [ await UserConverter().convert(ctx, a) for a in args ]
        await self.bot.karma_graph(ctx, users)
        # await ctx.send('Done.')