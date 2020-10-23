import discord
import asyncio
import uuid
import re
import pygsheets
import json
import os
import random
from datetime import datetime, timedelta
from discord import File, User, Member, Embed
from discord.ext import commands
from discord.ext.commands import UserConverter
from challenge import Context, BotErr
from xlsx import DefaultWriter, GoogleSheetsWriter, XlsxExporter
from enum import Enum
import imgkit

bot = commands.Bot(command_prefix='!')
bot.remove_command('help')
ctx = Context(challenges={}, users={})
gsheets_client = None
spreadsheet = None

class Privilege(Enum):
    ADMIN = 0
    USER = 1

def check_cmd_ctx(cmd_ctx, privilege_level = Privilege.ADMIN):
    author = cmd_ctx.message.author
    if type(author) is not Member:
        raise Exception('PMs are not allowed.')

    if privilege_level == Privilege.ADMIN:
        if 'bot commander' not in map(lambda x: x.name.lower(), cmd_ctx.message.author.roles):
            raise BotErr('"Bot Commander" role required.')

def save():
    open('challenges.json', 'w').write(ctx.to_json())

def load():
    global ctx
    try:
        data = json.loads(open('challenges.json', 'r').read())
    except e:
        print(e)
    ctx = Context.from_json(data)

@bot.command()
async def start_challenge(cmd_ctx, name: str):
    '''!start_challenge name\n[Admin only] Starts a new challenge with a given name'''
    try:
        check_cmd_ctx(cmd_ctx)
        ctx.start_challenge(name, cmd_ctx.message.channel.id)
        save()
        await cmd_ctx.send(f'Challenge "{name}" has been created.')
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{start_challenge.help}")

@bot.command()
async def end_challenge(cmd_ctx):
    '''!end_challenge\n[Admin only] Ends current challenge'''
    try:
        check_cmd_ctx(cmd_ctx)
        challenge = ctx.current_challenge
        ctx.end_challenge()
        save()
        await cmd_ctx.send(f'Challenge "{challenge}" has been ended.')
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{end_challenge.help}")

@bot.command()
async def add_pool(cmd_ctx, name: str):
    '''!add_pool pool_name\n[Admin only] Adds a new pool for the challenge'''
    try:
        check_cmd_ctx(cmd_ctx)
        ctx.add_pool(name)
        save()
        await cmd_ctx.send(f'Pool "{name}" has been created.')
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{add_pool.help}")

@bot.command()
async def add_user(cmd_ctx, user: UserConverter):
    '''!add_user @user\n[Admin only] Adds a new user to the challenge'''
    try:
        check_cmd_ctx(cmd_ctx)
        ctx.add_user(user)
        save()
        await cmd_ctx.send(f'User {user.mention} has been added.')
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{add_user.help}")

@bot.command()
async def set_color(cmd_ctx, *args):
    '''!set_color <@user> color\nSets a new color(in hex) for a specified user'''
    try:
        privilege_level = Privilege.USER
        user = cmd_ctx.message.author
        color = '#FFFFFF'
        
        if len(args) == 2:
            user = await UserConverter().convert(cmd_ctx, args[0])
            color = args[1]
            privilege_level = Privilege.ADMIN
        elif len(args) == 1:
            color = args[0]
        else:
            return await cmd_ctx.send(f'Invalid number of arguments({len(args)}). !set_color <user> color')

        check_cmd_ctx(cmd_ctx, privilege_level)
        if re.match(r'^#[a-fA-F0-9]{6}$', color) is None:
            return await cmd_ctx.send(f'Invalid color "{color}".')
        ctx.set_color(user, color)
        save()
        await cmd_ctx.send('Color has been changed.')
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{set_color.help}")

@bot.command()
async def set_name(cmd_ctx, *args):
    '''!set_name <@user> name\nSets a new name for a specified user'''
    try:
        if len(args) > 2:
            await cmd_ctx.send('Wrong nunber of arguments. !set_name <@user> name.')
            return

        privilege_level = Privilege.USER
        user = cmd_ctx.message.author
        name = ''

        if len(args) == 2:
            user = await UserConverter().convert(cmd_ctx, args[0])
            name = args[1]
            privilege_level = Privilege.ADMIN
        elif len(args) == 1:
            name = args[0]

        max_length = 32
        if len(name) > max_length:
            await cmd_ctx.send(f'Name is too long. Max is {max_length} characters.')
            return

        if re.match(r'^[0-9a-zа-яA-ZА-Я_\-]+$', name) is None:
            await cmd_ctx.send('Error: Bad symbols in your name.')
            return

        check_cmd_ctx(cmd_ctx, privilege_level)
        ctx.set_name(user, name)
        save()
        await cmd_ctx.send(f'{user.mention} got "{name}" as a new name.')
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{set_name.help}")
        
@bot.command()
async def sync(cmd_ctx):
    '''!sync\nSyncs with google sheets doc'''
    check_cmd_ctx(cmd_ctx, Privilege.USER)
    XlsxExporter(GoogleSheetsWriter(spreadsheet), ctx).export()
    await cmd_ctx.send('Done.')

async def user_or_none(cmd_ctx, s):
    try:
        return await UserConverter().convert(cmd_ctx, s)
    except:
        return None

@bot.command()
async def add_title(cmd_ctx, *args):
    '''!add_title <@user> title_name\n[Admin only] Adds a title for specified user.'''
    try:
        if len(args) < 2 or len(args) > 4:
            return

        pool = 'main'
        title_url = None
        user = await user_or_none(cmd_ctx, args[0])
        title_name = args[1]

        if user is None:
            if len(args) < 3:
                return
            if len(args) == 4:
                title_url = args[-1]
            pool = args[0]
            title_name = args[2]
            user = await UserConverter().convert(cmd_ctx, args[1])
        elif len(args) == 3:
            pool = args[0]
            title_url = args[-1]

        check_cmd_ctx(cmd_ctx)
        ctx.add_title(pool, user, title_name, title_url)
        save()
        await cmd_ctx.send(f'Title "{title_name}" has been added to "{pool}" pool.')

    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{add_title.help}")

@bot.command()
async def set_title(cmd_ctx, *args):
    '''!set_title <@user> <title_name>\n[Admin only] Sets a new title for a specified user'''
    try:
        if len(args) != 2:
            await cmd_ctx.send('Invalid number of arguments. Usage: !set_title <@user> <"title_name">')
            return

        check_cmd_ctx(cmd_ctx)
        user = await user_or_none(cmd_ctx, args[0])
        title_name = args[1]

        ctx.set_title(user, title_name)
        await cmd_ctx.send(f'Title "{title_name}" has been assigned to {user.mention}')
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{set_title.help}")

@bot.command()
async def start_round(cmd_ctx, *args):
    '''!start_round length\n[Admin only] Starts a new round of a specified length'''
    try:

        def gen_roll_info(titles, max_length):
            msg = ['```fix']
            for p,r in sorted(titles.items()):
                msg.append(f"{p:<{max_length}} {r}")
            msg.append('```')
            return '\n'.join(msg)

        if len(args) < 1:
            cmd_ctx.send(f"Bad arguments.\nUsage:{start_round.help}")
            return
        length = int(args[0])
        
        check_cmd_ctx(cmd_ctx)
        pool = 'main'
        if len(args) == 2:
            pool = args[1]

        rolls = ctx.start_round(timedelta(days=length), pool)
        save()

        max_length = max([ len(a) for a in rolls.keys() ]) + 2
        roll_info = { p: '???' for p in rolls.keys() }

        msg = gen_roll_info(roll_info, max_length)
        sent = await cmd_ctx.send(msg)
        await asyncio.sleep(2)

        for i in sorted(rolls.keys()):
            roll_info[i] = rolls[i].title
            msg = gen_roll_info(roll_info, max_length)
            await sent.edit(content=msg)
            await asyncio.sleep(1)
        
        rounds = ctx.current().rounds
        await cmd_ctx.send(f'Round {len(rounds) - 1} ({rounds[-1].begin}-{rounds[-1].end}) starts right now.')
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{start_round.help}")

@bot.command()
async def end_round(cmd_ctx):
    '''@end_round\nEnds current round'''
    try:
        check_cmd_ctx(cmd_ctx)
        ctx.end_round()
        save()
        rounds = ctx.current().rounds
        await cmd_ctx.send(f'Round {len(rounds) - 1} has been ended.')
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{end_round.help}")

@bot.command()
async def rate(cmd_ctx, *args):
    '''!rate <@user> score\nRates user's title with a given score'''
    try:
        user = cmd_ctx.message.author
        score = 0.0

        if len(args) < 1 or len(args) > 2:
            await cmd_ctx.send(f'Wrong nunber of arguments.\n{rate.help}')
            return

        privilege_level = Privilege.USER

        if len(args) > 1:
            privilege_level = Privilege.ADMIN
            user = await UserConverter().convert(cmd_ctx, args[0])
            score = float(args[1])
        else:
            score = float(args[0])

        if score < 0.0 or score > 10.0:
            await cmd_ctx.send('Score must be in range from 0 to 10')
            return

        check_cmd_ctx(cmd_ctx, privilege_level)
        ctx.rate(user, score)
        save()
        title = ctx.current().last_round().rolls[user.id].title
        await cmd_ctx.send(f'User {user.mention} gave {score} to "{title}".')
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{rate.help}")

@bot.command()
async def reroll(cmd_ctx, *args):
    '''!reroll @user <pool=main>\n[Admin only] Reroll titles for a user from a specified pool'''
    try:
        user = cmd_ctx.message.author
        pool = 'main'

        if len(args) > 2:
            await cmd_ctx.send(f'Wrong nunber of arguments.\n{reroll.help}')
            return

        if len(args) > 0:
            user = await UserConverter().convert(cmd_ctx, args[0])

        if len(args) > 1:
            pool = args[1]

        check_cmd_ctx(cmd_ctx)
        title = ctx.reroll(user, pool)
        save()
        await cmd_ctx.send(f'User {user.mention} rolled "{title}" from "{pool}" pool.')
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{reroll.help}")

@bot.command()
async def random_swap(cmd_ctx, *args):
    '''!random_swap @user @candidate1 <@candidate2...>\n[Admin only] Swaps user's title with random candidate's title'''
    try:
        if len(args) < 2:
            await cmd_ctx.send(f'Wrong nunber of arguments.\n{random_swap.help}')
            return

        if args[0] in args[1:]:
            await cmd_ctx.send("Can't swap titles between the same user.")
            return
        
        user = await UserConverter().convert(cmd_ctx, args[0])
        user2 = await UserConverter().convert(cmd_ctx, random.choice(args[1:]))

        check_cmd_ctx(cmd_ctx)
        title1, title2 = ctx.swap(user, user2)
        save()
        await cmd_ctx.send(f'User {user.mention} got "{title2}". User "{user2.mention}" got {title1}.')
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{random_swap.help}")

@bot.command()
async def swap(cmd_ctx, *args):
    '''!swap @user1 @user2\n[Admin only] Swaps titles between two users'''
    try:
        if len(args) != 2:
            await cmd_ctx.send(f'Wrong nunber of arguments.\n{swap.help}')
            return

        if args[0] == args[1]:
            await cmd_ctx.send("Can't swap titles between the same user.")
            return
        user = await UserConverter().convert(cmd_ctx, args[0])
        user2 = await UserConverter().convert(cmd_ctx, args[1])

        check_cmd_ctx(cmd_ctx)
        title1, title2 = ctx.swap(user, user2)
        save()
        await cmd_ctx.send(f'User {user.mention} got "{title2}". User "{user2.mention}" got {title1}.')
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{swap.help}")

@bot.command()
async def profile(cmd_ctx, *args):
    '''!profile <@user>\nDisplays user's profile'''
    try:
        if len(args) > 1:
            await cmd_ctx.send(f'Wrong nunber of arguments.\n{profile.help}')
            return

        user = cmd_ctx.message.author 

        if len(args) == 1:
            user = await UserConverter().convert(cmd_ctx, args[0])

        check_cmd_ctx(cmd_ctx, Privilege.USER)

        uname = ctx.get_name(user)
        avatar_url = str(user.avatar_url)

        ucolor = ctx.get_color(user)
        border_color = int('0x' + ucolor[1:], 16)
        embedVar = Embed(title="", description='', color=border_color)
        embedVar.set_author(name=uname, icon_url=avatar_url)
        embedVar.set_thumbnail(url=avatar_url)

        challenges_num = ctx.get_challenges_num(user)
        if challenges_num > 0:
            completed_num = ctx.get_completed_num(user)
            embedVar.add_field(name="Challenges", value=str(challenges_num), inline=True)
            embedVar.add_field(name="Completed", value=str(completed_num), inline=True)

            avg_user_title_score = ctx.calc_avg_user_title_score(user)
            avg_score_user_gives = ctx.calc_avg_score_user_gives(user)

            embedVar.add_field(name="Avg. Score of Your Titles", value=f"{avg_user_title_score:.2f}", inline=False)
            embedVar.add_field(name="Avg. Score You Give", value=f"{avg_score_user_gives:.2f}", inline=True)

            most_watched_users = ctx.find_most_watched_users(user)
            most_showed_users = ctx.find_most_showed_users(user)

            if len(most_watched_users) > 0:
                length = max([len(i[0]) for i in most_watched_users]) + 2
                msg = '\n'.join([f'{i[0]:<{length}}{i[1]}' for i in most_watched_users])
                embedVar.add_field(name='Watched the most', value=msg, inline=False)

            if len(most_watched_users) > 0:
                length = max([len(i[0]) for i in most_showed_users]) + 2
                msg = '\n'.join([f'{i[0]:<{length}}{i[1]}' for i in most_showed_users])
                embedVar.add_field(name='Sniped the most', value=msg, inline=False)
        else:
            embedVar.add_field(name="No Challenges", value='Empty', inline=True)

        karma, _ = ctx.calc_karma(user.id)
        embedVar.add_field(name="Karma", value=str(round(karma,2)), inline=False)

        karma_logo_url = 'https://i.imgur.com/wscUx1m.png'

        if karma > 200:
            karma_logo_url = 'https://i.imgur.com/oiypoFr.png'
        if karma > 300:
            karma_logo_url = 'https://i.imgur.com/4MOnqxX.png'
        if karma > 400:
            karma_logo_url = 'https://i.imgur.com/UJ8yOJ8.png'
        if karma > 500:
            karma_logo_url = 'https://i.imgur.com/YoGSX3q.png'
        if karma > 600:
            karma_logo_url = 'https://i.imgur.com/DeKg5P5.png'
        if karma > 700:
            karma_logo_url = 'https://i.imgur.com/byY9AfE.png'
        if karma > 800:
            karma_logo_url = 'https://i.imgur.com/XW4kc66.png'
        if karma > 900:
            karma_logo_url = 'https://i.imgur.com/3pPNCGV.png'

        embedVar.set_image(url=karma_logo_url)

        if ctx.is_in_challenge(user):
            time = ctx.get_end_round_time()
            if time:
                embedVar.set_footer(text=f'Round ends on: {time}')

        await cmd_ctx.send(embed=embedVar)
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{profile.help}")

def generate_html(params):
    html=f'''
<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="UTF-8">
        <link rel='stylesheet' href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css'>
        <script>
            window.addEventListener('load', function () {'{'}
                window.status = 'loaded'
            {'}'});
        </script>
    </head>

    <body>        
        <div class="center">
            <div class="card">
            <div class="additional" style="background-color: #{hex(0xf000000+params['color'])[3:]}">
                <div class="user-card">
                <!-- <div class="level center">
                    Level 13
                </div> -->
                <div class="points center">
                    Karma: {params['karma']}
                </div>

                <img src="{params['avatar_url']}" width="110" height="110" class="center" alt="">

                </div>
            </div>
            
            <div class="general">
                <div class="more-info">
                    <h1>{params['name']}</h1>
                    <div class="coords">
                        <span>work in progress...</span>
                    </div>
                    <div class="coords">
                        <!-- <span>Position/Role</span>
                        <span>City, Country</span> -->
                    </div>
                    
                    <div class="stats">
                        <div>
                        <div class="title">Completed</div>
                        <i class="fa fa-trophy"></i>
                        <div class="value">{params['challenges_completed']}</div>
                        </div>
                        <!-- <div>
                        <div class="title">Matches</div>
                        <i class="fa fa-gamepad"></i>
                        <div class="value">27</div>
                        </div> -->
                        <div>
                        <div class="title">Avg. Score</div>
                        <i class="fa fa-wheelchair-alt" aria-hidden="true"></i>
                        <div class="value">{params['avg_score']}</div>
                        </div>
                        <div>
                        <div class="title">Karma</div>
                        <img src="{params['karma_url']}" style="width:36px; height:36px" alt="bebe">
                        <div class="value" style="margin-top: -13px;">{params['karma']}</div>
                        </div>
                    </div>
                    </div>
            </div>
            </div>
        </div>
    </body>
  </html>
'''
    return html

def render_html(html, out):
    options = {
    "enable-local-file-access": None,
    "height": 500,
    "width": 900,
    "disable-smart-width": None,
    "quiet": None,
    "window-status": 'loaded',
    "quality": 100,
    "zoom": 2,
    }
    imgkit.from_string(html, out, options=options, css='styles.css')

@bot.command()
async def profile2(cmd_ctx, *args):
    '''!profile2 <@user>\nDisplays user's profile'''
    try:
        if len(args) > 1:
            await cmd_ctx.send(f'Wrong number of arguments.\n{profile.help}')
            return

        user = cmd_ctx.message.author 

        if len(args) == 1:
            user = await UserConverter().convert(cmd_ctx, args[0])

        check_cmd_ctx(cmd_ctx, Privilege.USER)

        uname = ctx.get_name(user)
        avatar_url = str(user.avatar_url).replace("webp", "png")

        ucolor = ctx.get_color(user)
        border_color = int('0x' + ucolor[1:], 16)
        #border_color = hex(border_color)

        challenges_num = ctx.get_challenges_num(user)
        completed_num = 0
        if challenges_num > 0:
            completed_num = ctx.get_completed_num(user)

            avg_user_title_score = ctx.calc_avg_user_title_score(user)
            avg_score_user_gives = ctx.calc_avg_score_user_gives(user)

            most_watched_users = ctx.find_most_watched_users(user)
            most_showed_users = ctx.find_most_showed_users(user)

        karma, _ = ctx.calc_karma(user.id)

        karma_logo_url = 'https://i.imgur.com/wscUx1m.png'
        if karma > 200:
            karma_logo_url = 'https://i.imgur.com/oiypoFr.png'
        if karma > 300:
            karma_logo_url = 'https://i.imgur.com/4MOnqxX.png'
        if karma > 400:
            karma_logo_url = 'https://i.imgur.com/UJ8yOJ8.png'
        if karma > 500:
            karma_logo_url = 'https://i.imgur.com/YoGSX3q.png'
        if karma > 600:
            karma_logo_url = 'https://i.imgur.com/DeKg5P5.png'
        if karma > 700:
            karma_logo_url = 'https://i.imgur.com/byY9AfE.png'
        if karma > 800:
            karma_logo_url = 'https://i.imgur.com/XW4kc66.png'
        if karma > 900:
            karma_logo_url = 'https://i.imgur.com/3pPNCGV.png'
        
        html_params = {
            "name": uname,
            "karma": round(karma,1),
            "challenges_completed": completed_num,
            "avatar_url": avatar_url,
            "avg_score": round(avg_score_user_gives,2),
            "color": border_color,
            "karma_url": karma_logo_url,
        }
        html_string = generate_html(html_params)
        render_html(html_string, 'tmp_image.jpg')
        await cmd_ctx.send(file=discord.File('tmp_image.jpg'))
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{profile.help}")

@bot.command()
async def karma(cmd_ctx):
    '''!karma\nShows karma table'''
    try:
        check_cmd_ctx(cmd_ctx, Privilege.USER)

        users = ctx.users.items()
        user_karma = []
        for user_id, user_info in users:
            karma,diff = ctx.calc_karma(user_id)
            user_karma.append((karma, diff, user_info.name))
        user_karma.sort()

        max_nickname_length = 0
        msg = ['```']
        for i,uk in enumerate(user_karma[::-1]):
            max_nickname_length = max(max_nickname_length, len(uk[2]))

        max_nickname_length+=2
        for i,uk in enumerate(user_karma[::-1]):
            diff = f"({'+'if uk[1]>0 else ''}{round(uk[1],2)})" if uk[1] else ""
            msg.append(f"{str(i+1)+')':<3} {uk[2]:<{max_nickname_length}}{uk[0]:.1f} {diff}")
        msg.append('```')
        msg = "\n".join(msg)

        await cmd_ctx.send(msg)

    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{karma.help}")

@bot.command()
async def progress(cmd_ctx, *args):
    '''!progress <@user> [<x/y> or <x> or +<x>]\nShows/Updates current progress.'''
    try:
        if len(args) > 2:
            await cmd_ctx.send(f'Wrong number of arguments. {progress.help}')
            return
        
        user = cmd_ctx.message.author
        privilate_level = Privilege.USER
        command_index_offset = 0
        if len(args) > 1:
            user = await UserConverter().convert(cmd_ctx, args[0]) 
            privilate_level = Privilege.ADMIN
            command_index_offset += 1
        
        check_cmd_ctx(cmd_ctx, privilate_level)
        if len(args) > 0:
            prog = args[command_index_offset]
            if len(prog) > 5:
                return await cmd_ctx.send(f'Invalid progress "{prog}".')

            if re.match(r'^[0-9]+?\/[0-9]+?$', prog):
                ctx.set_progress(user, prog)
            else:
                p = ctx.get_progress(user)
                if p and p.find('/') >= 0:
                    current, total = p.split("/")
                else:
                    return await cmd_ctx.send(f'Bad current progress "{p}".')
                
                if re.match(r'^[0-9]+?$', prog):
                    ctx.set_progress(user, '/'.join([prog, total]))
                elif re.match(r'^\+([0-9]*?)$', prog):
                    offset = re.match(r'^\+([0-9]*?)$', prog).group(1)
                    if not offset:
                        offset = 1
                    else:
                        offset = int(offset)
                    ctx.set_progress(user, '/'.join([str(int(current) + offset), total]))
                else:
                    return await cmd_ctx.send(f'Invalid progress "{prog}".')
        all_progress = ctx.get_all_progress()

        msg = ['```']
        max_length = max([ len(participant) for participant in all_progress.keys()])+2
        for participant, prog in sorted(all_progress.items()):
            if prog is None:
                prog = "None"        
            msg.append(f'{participant:<{max_length}} {prog}')
    
        msg.append('```')
        msg = '\n'.join(msg)

        await cmd_ctx.send(msg)
        save() #todo: maybe move it somewhere when it doesn't proc everytime it shows the progress
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{progress.help}")

@bot.command()
async def prog(cmd_ctx, *args):
    '''!prog\nShortcut for !progress'''
    await progress(cmd_ctx, *args)

@bot.command()
async def rename_title(cmd_ctx, old_title: str, new_title: str):
    '''!rename_title old_name new_name\nRenames a title'''
    try:
        check_cmd_ctx(cmd_ctx)
        ctx.rename_title(old_title, new_title)
        save()
        await cmd_ctx.send(f'Title {old_title} has been renamed to {new_title}.')
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{rename_title.help}")

@bot.command()
async def remove_user(cmd_ctx, user: UserConverter):
    '''!remove_user user\n[Admin only] Removes a specified user'''
    try:
        check_cmd_ctx(cmd_ctx)
        ctx.remove_user(user)
        save()
        await cmd_ctx.send(f'User {user.mention} has been removed.')
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{remove_user.help}")

@bot.command()
async def remove_title(cmd_ctx, title: str):
    '''!remove_titles tilte\n[Admin only] Removes a specified title'''
    try:
        check_cmd_ctx(cmd_ctx)
        ctx.remove_title(title)
        save()
        await cmd_ctx.send(f'Title "{title}" has been removed')
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{remove_title.help}")

@bot.command()
async def remove_pool(cmd_ctx, pool: str):
    '''!remove_pool pool\n[Admin only] Removes a specifed pool'''
    try:
        check_cmd_ctx(cmd_ctx)
        ctx.remove_pool(pool)
        save()
        await cmd_ctx.send(f'Pool "{pool}" has been removed')
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{remove_pool.help}")

@bot.command()
async def rename_pool(cmd_ctx, pool: str, new_name: str):
    '''!rename_pool pool new_name\n[Admin only] Rename pool as a new_name'''
    try:
        check_cmd_ctx(cmd_ctx)
        ctx.rename_pool(pool, new_name)
        save()
        await cmd_ctx.send(f'Pool "{pool}" has been renamed to "{new_name}"')
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{rename_pool.help}")

@bot.command()
async def extend_round(cmd_ctx, days: int):
    '''!extend_round days\n[Admin only] Extends the current round by N days'''
    try:
        check_cmd_ctx(cmd_ctx)
        ctx.extend_round(timedelta(days=days))
        save()
        rounds = ctx.current().rounds
        await cmd_ctx.send(f'Round {len(rounds) - 1} ends at {rounds[-1].end}.')
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{extend_round.help}")

@bot.command()
async def create_poll(cmd_ctx):
    '''!create_poll\n[Admin only] Creates a poll of all titles to vote for which ones people have seen'''
    try:
        check_cmd_ctx(cmd_ctx)

        titles = ctx.get_current_titles()
        for title in titles:
            msg = await cmd_ctx.send(title)
            await msg.add_reaction("👀")
    except BotErr as e:
        await cmd_ctx.send(f"{e}\nUsage:\n{create_poll.help}")

@bot.command()
async def export(cmd_ctx, ext: str):
    '''!export <json/xlsx>\nExports data'''

    check_cmd_ctx(cmd_ctx)
    fname = str(uuid.uuid4())
    if ext == 'xlsx':
        fname += '.xlsx'
        XlsxExporter(DefaultWriter(fname), ctx).export()
    elif ext == 'json':
        fname += '.json'
        open(fname, 'w').write(ctx.to_json())
    else:
        return await cmd_ctx.send(f'Unknown format "{ext}" (use xlsx or json).')

    await cmd_ctx.send(file=File(fname))
    os.remove(fname)

@bot.command()
async def help(cmd_ctx):
    '''!help\nPrints this message'''

    embed = Embed(title="Help", description='', color=0x0000000)
    commands=[]
    for command in bot.commands:
        if not command.help:
            continue

        (name, desc) = command.help.split('\n')
        commands.append((name, desc))
        
    for name, desc in sorted(commands):
        embed.add_field(name=name, value=desc, inline=False)
    
    await cmd_ctx.send(embed=embed)

async def check_deadline():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            challenge = ctx.current()
            rnd = challenge.last_round()
            if datetime.now() >= rnd.parse_end():
                await _end_round(bot.get_channel(challenge.channel_id))
        except:
            pass
        await asyncio.sleep(10)

if __name__ == '__main__':
    try:
        load()
    except Exception as e:
        print(str(e))

    gsheets_client = pygsheets.authorize('client_secret.json')
    spreadsheet = gsheets_client.open_by_key(open('sheets_key.txt').read())
    bot.loop.create_task(check_deadline())
    bot.run(open('discord_token.txt').read())
