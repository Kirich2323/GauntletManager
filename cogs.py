import asyncio
import uuid
import re
import os
import random
import math
import discord

from discord import File, Embed
from discord.ext import commands
from discord.ext.commands import UserConverter, CommandError
from datetime import timedelta
from html_profile.generator import generate_profile_html
from html_profile.renderer import render_html_from_string
from utils import is_valid_url

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

class GuildAmbiguity(BotErr):
    def __init__(self, guilds):
        super().__init__('Guild ambiguity.')
        self.guilds = guilds

def _is_admin(ctx):
    if type(ctx.message.author) == discord.User: return False
    return 'bot commander' in map(lambda x: x.name.lower(), ctx.message.author.roles)

def _is_in_dm(ctx):
    return ctx.guild == None

def require_admin_privilege(ctx):
    if not _is_admin(ctx):
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
    async def random_swap(self, ctx, user1: UserConverter, *candidates: UserConverter):
        '''
        !random_swap @user @candidate1 [@candidate2...]
        [Admin only] Swaps user's title with random candidate's title
        '''

        candidates = list(candidates)
        if user1 in candidates:
            return await ctx.send("Can't swap titles between the same user.")

        if len(candidates) > 0:
          user2 = random.choice(candidates)
        else:
            user2 = None

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
        self.bot.set_allow_hidden(ctx, 0)

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
        if not is_valid_url(url):
            raise InvalidUrl()
        await self.bot.set_award(ctx, url)
        await ctx.send('Done.')

    @commands.command()
    async def add_award(self, ctx, user: UserConverter, url: str):
        '''
        !add_award @user url
        [Admin only] Adds an award for a user
        '''
        if not is_valid_url(url):
            raise InvalidUrl()
        await self.bot.add_award(ctx, user, url)
        await ctx.send('Done.')

    @commands.command()
    async def remove_award(self, ctx, user: UserConverter, url: str):
        '''
        !add_award @user url
        [Admin only] Removes an award from a user
        '''
        if not is_valid_url(url):
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

    @commands.command()
    async def ban_user(self, ctx, user : UserConverter):
        '''
        !ban_user @user
        Bans user from the challenge
        '''
        await self.bot.ban_user(ctx, user)
        await ctx.send('Done.')

    @commands.command()
    async def unban_user(self, ctx, user : UserConverter):
        '''
        !unban_user @user
        Unbans user from the challenge
        '''
        await self.bot.unban_user(ctx, user)
        await ctx.send('Done.')

    @commands.command()
    async def set_allow_hidden(self, ctx, val: bool):
        '''
        !set_allow_hidden @val
        Sets is_allowed_hidden to @val
        '''
        await self.bot.set_allow_hidden(ctx, val)
        await self.bot.sync(ctx)
        await ctx.send('Done.')

    @commands.command()
    async def refill_title_info(self, ctx):
        '''
        !refill_title_info
        Refills titles info
        '''
        await self.bot.refill_title_info(ctx)
        await ctx.send('Done.')

# ----------------- User Cog ---------------------

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
    async def profile(self, ctx, user: UserConverter = None):
        '''
        !profile [@user=author]
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

    @commands.command()
    async def join(self, ctx):
        '''
        !join
        Join current challenge
        '''
        user = ctx.message.author
        await self.bot.add_user(ctx, user)
        await ctx.send(f'User {user.mention} has been added.')
        await self.bot.sync(ctx)

    @commands.command()
    async def quit(self, ctx):
        '''
        !quit
        Quit current challenge
        '''
        user = ctx.message.author
        await self.bot.remove_user(ctx, user)
        await ctx.send(f'User {user.mention} has been removed.')
        await self.bot.sync(ctx)

    @commands.command()
    async def add_title(self, ctx, *args):
        '''
        !add_title [@user=author] url [title] [pool='main'] [challenge_id]
        Adds a title for specified user
        '''
        try:
            guild_id, args = await self.parse_guild_id(*args)
            params = await self.parse_title_args(ctx, guild_id, *args)
            if _is_in_dm(ctx):
                params['is_hidden'] = True
            is_admin = _is_admin(ctx)

            if params['user'] != ctx.message.author:
                require_admin_privilege(ctx)

            await self.bot.add_title(ctx, params, is_admin)
            await ctx.send(f'Done')
            await self.bot.sync(ctx, guild_id)
        except GuildAmbiguity as e:
            challenges = []
            for g in e.guilds:
                cc = await g.fetch_current_challenge()
                challenges.append(cc)

            challenge_to_id_str = '\n'.join([ f'    {c.name} --> ${c.guild_id}' for c in challenges ])
            await ctx.send(f'Guild ambiguity detected:\n{challenge_to_id_str}\nPlease specify guild_id in your command, for example $1.')

    @commands.command()
    async def remove_title(self, ctx, title: str):
        '''
        !remove_title title
        Removes a specified title
        '''
        is_admin = _is_admin(ctx)
        await self.bot.remove_title(ctx, title, is_admin)
        await ctx.send(f'Title "{title}" has been removed')
        await self.bot.sync(ctx)

    @commands.command()
    async def round_info(self, ctx):
        '''
        !round_info
        Shows round info
        '''
        await self.bot.round_info(ctx)

    @commands.command()
    async def difficulty_user(self, ctx, *args):
        '''
        !difficulty_user [@user=author] [@challenge=None]
        Shows the most difficult titles
        '''

        if len(args) > 0:
            user = await user_or_none(ctx, args[0])
        
        if user == None:
            user = ctx.message.author

        challenge = None   
        if len(args) > 1:
            challenge = args[1]

        table = table_format(map(lambda x: (str(x[0] + 1) + ')', x[1]), enumerate(await self.bot.difficulty_table(ctx, challenge, user))))
        await ctx.send(f"```markdown\n{ table }```")

    @commands.command()
    async def difficulty_all(self, ctx, challenge=None):
        '''
        !difficulty_all [@challenge=None]
        Shows the most difficult titles
        '''
        table = table_format(map(lambda x: (str(x[0] + 1) + ')', x[1]), enumerate(await self.bot.difficulty_table(ctx, challenge))))
        await ctx.send(f"```markdown\n{ table }```")

    async def parse_guild_id(self, *_args):
        args = [ x for x in _args ]
        
        guild_id_prefix = '$'
        for i in range(len(args)):
            if guild_id_prefix in args[i]:
                id = int(args[i][len(guild_id_prefix):])
                args.pop(i)
                return id, args
        return None, args

    async def parse_title_args(self, ctx, guild_id, *_args):
        args = [ x for x in _args ]

        params = {}
        params['user'] = ctx.message.author
        params['pool'] = 'main' # todo: make so default pool isn't main but the first pool in a challenge
        params['guild_id'] = guild_id

        for i, arg in enumerate(args):
            if is_valid_url(arg):
                params['url'] = arg
                args[i] = None
            
            usr = await user_or_none(ctx, arg)
            if usr:
                params['user'] = usr
                args[i] = None
            
            if await self.bot.has_pool(ctx, arg, params['guild_id']):
                params['pool'] = arg
                args[i] = None

        args = [ arg for arg in args if arg != None ]
        if params['url']:
            title_info = self.bot.get_api_title_info(params['url'])
            params['title_name'] = title_info.name
            params['score'] = title_info.score
            params['duration'] = title_info.duration
            params['num_of_episodes'] = title_info.num_of_episodes
            params['difficulty'] = title_info.difficulty            

        if len(args) > 1:
            raise BotErr('Bad argumnets')
        if len(args) == 1:
            params['title_name'] = args[0]
        
        return params