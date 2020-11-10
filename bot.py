import cogs
import os
import traceback
import random
import asyncio
import aiosqlite
import sqlite3
import json
import matplotlib.pyplot as plt

from discord import File
from discord.ext import commands
from datetime import datetime, timedelta
from cogs import BotErr
from db import Db, Guild, Challenge, Pool, User, Participant, Title, Roll, KarmaHistory, UserStats
from export import export
from thirdparty_api.api_title_info import ApiTitleInfo
from utils import gen_fname

class State:
    @staticmethod
    async def fetch(bot, ctx, allow_started=False):
        guild = await Guild.fetch_or_insert(bot.db, ctx.message.guild.id)
        cc = await guild.fetch_current_challenge()
        BotErr.raise_if(cc is None, 'Create a new challenge first.')
        BotErr.raise_if(cc is not None and not allow_started and await cc.has_started(),
            'Cannot add/delete user/title/pool after a challenge has started.')
        return State(bot, guild, cc)

    def __init__(self, bot, guild, cc):
        self.bot = bot
        self.guild = guild
        self.cc = cc

    async def fetch_user(self, user):
        return await User.fetch_or_insert(self.bot.db, user.id, user.name)

    async def fetch_participant(self, user):
        u = await self.fetch_user(user)
        p = await self.cc.fetch_participant(u.id)
        BotErr.raise_if(p is None, f'User {user.mention} is not participating in this challenge.')
        BotErr.raise_if(p.has_failed(), f'User {user.mention} has failed this challenge.')
        return p

    async def has_participant(self, user):
        u = await self.fetch_user(user)
        return await self.cc.has_participant(u.id)

    async def fetch_pool(self, name):
        p = await self.cc.fetch_pool(name)
        BotErr.raise_if(p is None, f'Pool "{name}" does not exist.')
        return p

    async def fetch_title(self, name):
        t = await self.cc.fetch_title(name)
        BotErr.raise_if(t is None, f'Title "{name}" does not exist.')
        return t

    async def fetch_titles(self):
        t = await self.cc.fetch_titles()
        # BotErr.raise_if(t is None, f'fetch_titles')
        return t

    async def fetch_last_round(self, allow_past_deadline=False):
        lr = await self.cc.fetch_last_round()
        BotErr.raise_if(lr is None, 'Create a new round first.')
        BotErr.raise_if(lr is not None and (lr.is_finished
            or not allow_past_deadline and datetime.now() > lr.finish_time), 'Round has ended.')
        return lr

class Bot(commands.Bot):
    def __init__(self, db, config):
        super().__init__(command_prefix='!')
        self.remove_command('help')
        self.add_cog(cogs.Admin(self))
        self.add_cog(cogs.User(self))
        self.db = db
        self.config = config

    async def on_command_error(self, ctx, e):
        cmd = self.get_command(ctx.message.content.lstrip()[1:])
        help = '' if cmd is None else cmd.help
        if isinstance(e, commands.CommandInvokeError):
            if isinstance(e.original, BotErr):
                await ctx.send(f'{e.original}\nUsage:\n{help}')
            else:
                print('Traceback:')
                traceback.print_tb(e.original.__traceback__)
                print(f'{e.original.__class__.__name__}: {e.original}')
        else:
            await ctx.send(f'{e}\nUsage:\n{help}')

    def get_api_title_info(self, url):
        return ApiTitleInfo.from_url(url, self.config)

    async def current_titles(self, ctx):
        state = await State.fetch(self, ctx, allow_started=True)
        return await state.fetch_titles()

    async def start_challenge(self, ctx, name):
        guild = await Guild.fetch_or_insert(self.db, ctx.message.guild.id)
        if guild.current_challenge_id is not None:
            raise BotErr(f'Finish "{(await guild.fetch_current_challenge()).name}" challenge first.')
        BotErr.raise_if(await guild.has_challenge(name), f'Challenge "{name}" already exists.')
        challenge = await guild.add_challenge(name, datetime.now())
        await challenge.add_pool('main')
        guild.current_challenge_id = challenge.id
        await guild.update()
        await self.db.commit()

    async def end_challenge(self, ctx):
        state = await State.fetch(self, ctx, allow_started=True)
        lr = await state.cc.fetch_last_round()
        if lr is not None and not lr.is_finished:
            await self._end_round(lr)
        state.cc.finish_time = datetime.now()
        await state.cc.update()
        state.guild.current_challenge_id = None
        await state.guild.update()
        await self.db.commit()
        return state.cc

    async def add_pool(self, ctx, name):
        state = await State.fetch(self, ctx)
        BotErr.raise_if(await state.cc.has_pool(name), f'Pool "{name}" already exists.')
        await state.cc.add_pool(name)
        await self.db.commit()

    async def remove_pool(self, ctx, name):
        state = await State.fetch(self, ctx)
        await (await state.fetch_pool(name)).delete()
        await self.db.commit()

    async def rename_pool(self, ctx, old_name, new_name):
        state = await State.fetch(self, ctx, allow_started=True)
        BotErr.raise_if(await state.cc.has_pool(new_name), f'Pool "{new_name}" already exists.')
        pool = await state.fetch_pool(old_name)
        pool.name = new_name
        await pool.update()
        await self.db.commit()

    async def add_user(self, ctx, user):
        state = await State.fetch(self, ctx)
        BotErr.raise_if(await state.has_participant(user),
            f'User {user.mention} is already participating in this challenge.')
        user = await state.fetch_user(user)
        await state.cc.add_participant(user.id)
        await self.db.commit()

    async def remove_user(self, ctx, user):
        state = await State.fetch(self, ctx, allow_started=True)
        participant = await state.fetch_participant(user)
        last_round = await state.cc.fetch_last_round()
        if last_round is not None:
            participant.failed_round_id = last_round.id
            await participant.update()
        else:
            await participant.delete()
        await self.db.commit()

    async def add_title(self, ctx, pool, user, name, url):
        state = await State.fetch(self, ctx)
        BotErr.raise_if(await state.cc.has_title(name), f'Title "{name}" already exists.')
        participant = await state.fetch_participant(user)
        pool = await state.fetch_pool(pool)
        await pool.add_title(participant.id, name, url)
        await self.db.commit()

    async def remove_title(self, ctx, name):
        state = await State.fetch(self, ctx)
        title = await state.fetch_title(name)
        BotErr.raise_if(title.is_used, "Cannot delete title that's already been used.")
        await title.delete()
        await self.db.commit()

    async def rename_title(self, ctx, old_name, new_name):
        state = await State.fetch(self, ctx)
        BotErr.raise_if(await state.cc.has_title(new_name), f'Title "{new_name}" already exists.')
        title = await state.fetch_title(old_name)
        title.name = new_name
        await title.update()
        await self.db.commit()

    async def start_round(self, ctx, days, pool):
        state = await State.fetch(self, ctx, allow_started=True)
        last_round = await state.cc.fetch_last_round()
        if last_round is not None and not last_round.is_finished:
            raise BotErr(f'Finish round {last_round.num} first.')

        pool = await state.fetch_pool(pool)
        users_participants = await state.cc.fetch_users_participants()
        users = { up[0].id: up[0] for up in users_participants }
        participants = [up[1] for up in filter(lambda up: not up[1].has_failed(), users_participants)]
        BotErr.raise_if(len(participants) == 0, 'Not enough participants to start a round.')
        titles = await pool.fetch_unused_titles()
        BotErr.raise_if(len(titles) < len(participants), f'Not enough titles in "{pool}" pool.')

        num = last_round.num + 1 if last_round is not None else 0
        start = datetime.now()
        new_round = await state.cc.add_round(num, start, start + timedelta(days=days))

        rand_titles = [ titles.pop(random.randrange(len(titles))) for _ in range(len(participants)) ]
        for participant, title in zip(participants, rand_titles):
            await new_round.add_roll(participant.id, title.id)
            participant.progress_current = None
            participant.progress_total = None
            title.is_used = True
            await participant.update()
            await title.update()

        await self.db.commit()
        return new_round, { users[p.user_id].name: t.name for p, t in zip(participants, rand_titles) }

    async def calc_karma(self, round):
        if not round.is_finished:
            return
        starting_karma = 0

        rolls = await round.fetch_rolls()
        time = round.finish_time
        for roll in rolls:
            proposer = await roll.fetch_title_author()
            watcher = await roll.fetch_participant()

            score = roll.score
            if score is not None and watcher.id != proposer.id:
                proposer_karma = await KarmaHistory.fetch_user_karma(self.db, proposer.id)
                d_karma = score

                if not proposer_karma:
                    proposer_karma = starting_karma + d_karma
                else:
                    proposer_karma += d_karma
                await KarmaHistory.insert_or_update_karma(self.db, proposer.id, proposer_karma, time)

                watcher_karma = await KarmaHistory.fetch_user_karma(self.db, watcher.id)
                d_karma = score if score < 5 else 5 + (score - 5) * 0.25

                if not watcher_karma:
                    watcher_karma = starting_karma + d_karma
                else:
                    watcher_karma += d_karma
                await KarmaHistory.insert_or_update_karma(self.db, watcher.id, watcher_karma, time)

    # def calculate_karma_diff
    
    async def recalc_karma(self, ctx):
        guild = await Guild.fetch_or_insert(self.db, ctx.message.guild.id)
        users = await guild.fetch_users()
        for u in users:
            await KarmaHistory.clear_user_karma_history(self.db, u.id)

        challenges = await guild.fetch_challenges()
        for c in challenges:
            rounds = await c.fetch_rounds()
            for r in rounds:
                await self.calc_karma(r)
        
        await self.db.commit()

    async def _end_round(self, last_round):
        rwp = await last_round.fetch_rolls_watchers_proposers()
        failed_participants = map(lambda x: x[0].participant_id, filter(lambda x: x[0].score is None, rwp))
        await Participant.fail_participants(self.db, last_round.id, failed_participants)
        last_round.is_finished = True
        await last_round.update()

        await self.calc_karma(last_round)

    async def end_round(self, ctx):
        state = await State.fetch(self, ctx, allow_started=True)
        last_round = await state.fetch_last_round(allow_past_deadline=True)
        await self._end_round(last_round)
        await self.db.commit()
        return last_round

    async def extend_round(self, ctx, days):
        state = await State.fetch(self, ctx, allow_started=True)
        last_round = await state.fetch_last_round(allow_past_deadline=True)
        last_round.finish_time += timedelta(days=days)
        await last_round.update()
        await self.db.commit()
        return last_round

    async def rate(self, ctx, user, score):
        state = await State.fetch(self, ctx, allow_started=True)
        last_round = await state.fetch_last_round()
        participant = await state.fetch_participant(user)
        roll = await last_round.fetch_roll(participant.id)
        roll.score = score
        await roll.update()
        await self.db.commit()
        return await roll.fetch_title()

    async def swap(self, ctx, user1, user2):
        state = await State.fetch(self, ctx, allow_started=True)
        last_round = await state.fetch_last_round()
        participant1 = await state.fetch_participant(user1)
        participant2 = await state.fetch_participant(user2)
        roll1 = await last_round.fetch_roll(participant1.id)
        roll2 = await last_round.fetch_roll(participant2.id)
        tmp = roll1.title_id
        roll1.title_id = roll2.title_id
        roll2.title_id = tmp
        await roll1.update()
        await roll2.update()
        await self.db.commit()
        return await roll2.fetch_title(), await roll1.fetch_title()

    async def _set_title(self, roll, new_title):
        BotErr.raise_if(new_title.is_used, f'Title "{new_title.name}" is already used.')
        old_title = await roll.fetch_title()
        old_title.is_used = False
        roll.title_id = new_title.id
        new_title.is_used = True
        await old_title.update()
        await roll.update()
        await new_title.update()

    async def reroll(self, ctx, user, pool):
        state = await State.fetch(self, ctx, allow_started=True)
        last_round = await state.fetch_last_round()
        participant = await state.fetch_participant(user)
        roll = await last_round.fetch_roll(participant.id)
        pool = await state.fetch_pool(pool)
        titles = await pool.fetch_unused_titles()
        BotErr.raise_if(len(titles) == 0, f'Not enough titles in "{pool}" pool.')
        new_title = random.choice(titles)
        await self._set_title(roll, new_title)
        await self.db.commit()
        return new_title

    async def set_title(self, ctx, user, title):
        state = await State.fetch(self, ctx, allow_started=True)
        last_round = await state.fetch_last_round()
        participant = await state.fetch_participant(user)
        roll = await last_round.fetch_roll(participant.id)
        new_title = await state.fetch_title(title)
        await self._set_title(roll, new_title)
        await self.db.commit()

    async def karma_table(self, ctx):
        guild = await Guild.fetch_or_insert(self.db, ctx.message.guild.id)
        users = [ (user, await KarmaHistory.fetch_user_karma(self.db, user.id)) for user in await guild.fetch_users() ]
        users = sorted(users, key=lambda x: x[1], reverse=True)
        return [(u[0].name, '{:.1f}'.format(u[1])) for u in users]

    async def user_profile(self, ctx, user):
        guild = await Guild.fetch_or_insert(self.db, ctx.message.guild.id)
        user = await User.fetch_or_insert(self.db, user.id, user.name)
        return user, await UserStats.fetch(self.db, user.id, guild.id)

    async def set_name(self, user, name):
        u = await User.fetch_or_insert(self.db, user.id, user.name)
        u.name = name
        await u.update()
        await self.db.commit()

    async def set_color(self, user, color):
        u = await User.fetch_or_insert(self.db, user.id, user.name)
        u.color = color
        await u.update()
        await self.db.commit()

    async def set_progress(self, ctx, user, prog_current, prog_total=None):
        state = await State.fetch(self, ctx, allow_started=True)
        participant = await state.fetch_participant(user)
        participant.progress_current = prog_current
        participant.progress_total = prog_total
        await participant.update()
        await self.db.commit()

    async def add_progress(self, ctx, user, num):
        state = await State.fetch(self, ctx, allow_started=True)
        participant = await state.fetch_participant(user)
        participant.progress_current += num      
        await participant.update()
        await self.db.commit()    

    async def progress_table(self, ctx):
        state = await State.fetch(self, ctx, allow_started=True)
        users_participants = sorted(await state.cc.fetch_users_participants(), key=lambda up: up[0].name)
        return [(up[0].name, up[1].progress_current, up[1].progress_total) for up in users_participants]

    async def set_spreadsheet_key(self, ctx, key):
        guild = await Guild.fetch_or_insert(self.db, ctx.message.guild.id)
        guild.spreadsheet_key = key
        await guild.update()
        await self.db.commit()

    async def sync(self, ctx):
        state = await State.fetch(self, ctx, allow_started=True)
        BotErr.raise_if(state.guild.spreadsheet_key is None, 'Spreadsheet key is not set.')
        await export(state.guild.spreadsheet_key, state.cc)

    async def sync_all(self, ctx):
        guild = await Guild.fetch_or_insert(self.db, ctx.message.guild.id)  # todo: move logic?
        challenges = await guild.fetch_challenges()
        BotErr.raise_if(guild.spreadsheet_key is None, 'Spreadsheet key is not set.') # todo: maybe its bad to have single
                                                                                            # spreadsheet_key per guild, maybe
                                                                                            # we need to store it in challange column
        for c in challenges:
            await export(guild.spreadsheet_key, c)

    async def set_award(self, ctx, url):
        state = await State.fetch(self, ctx, allow_started=True)
        await state.cc.set_award(url)

    async def add_award(self, ctx, user, url):
        state = await State.fetch(self, ctx, allow_started=True)
        user = await state.fetch_user(user)
        await user.add_award(url, datetime.now())

    async def remove_award(self, ctx, user, url):
        state = await State.fetch(self, ctx, allow_started=True)
        user = await state.fetch_user(user)
        await user.remove_award(url)

    async def karma_graph(self, ctx, users):
        state = await State.fetch(self, ctx, allow_started=True)
        fig = plt.figure()
        plt.xticks(rotation=30)
        for user in users:
            user = await state.fetch_user(user)
            history = await KarmaHistory.fetch_karma_history(self.db, user.id)
            if len(history) == 0:
                ctx.send(f'{user.name} has no karma history')
                return

            times = [ entry.time for entry in history ]
            karmas = [ entry.karma for entry in history ]
            plt.plot(times, karmas, label = user.name)
         
        plt.legend()
        pic_name = gen_fname('.png')
        fig.savefig(pic_name, dpi=900, marker='.')
        await ctx.send(file=File(pic_name))
        os.remove(pic_name)
        
async def main():
    config = json.loads(open("config.json", 'rb').read())
    token = config["discord_token"]
    path = 'challenges.db'
    init_db = not os.path.isfile(path)
    async with aiosqlite.connect(path, detect_types=sqlite3.PARSE_DECLTYPES) as connection:
        if init_db:
            await connection.executescript(open('init.sql', 'r').read())
            await connection.commit()

        bot = Bot(Db(connection), config)
        try:
            await bot.start(token)
        finally:
            await bot.logout()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception:
        pass