import aiosqlite
from datetime import datetime
from cogs import BotErr

class Db:
    def __init__(self, db):
        self.db = db

    async def execute(self, *args):
        return await self.db.execute(*args)

    async def executemany(self, *args):
        return await self.db.executemany(*args)

    async def fetchrow(self, *args):
        async with self.db.execute(*args) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, *args):
        async with self.db.execute(*args) as cursor:
            return await cursor.fetchall()

    async def fetchval(self, *args, **kwargs):
        col = kwargs['col'] if 'col' in kwargs else 0
        async with self.db.execute(*args) as cursor:
            row = await cursor.fetchone()
            return None if row is None else row[col]

    async def commit(self):
        await self.db.commit()

async def fromrow(Class, db, *args):
    row = await db.fetchrow(*args)
    return None if row is None else Class(db, row)

class Cols:
    def __init__(self, *cols):
        self.cols = cols

    def __iter__(self):
        return iter(self.cols)

    def __len__(self):
        return len(self.cols)

    def __str__(self):
        return self.join()

    def join(self, prefix='', sep=', ', suffix=''):
        return sep.join(map(lambda x: prefix + str(x) + suffix, self.cols))

class Relation(object):
    def __init__(self, db, name, all_cols, where_cols, row):
        object.__setattr__(self, 'db', db)
        assert len(all_cols) == len(row)
        object.__setattr__(self, 'cols', { col: val for col, val in zip(all_cols, row) })

        async def update():
            updated_cols = Cols(*list(set(all_cols) - set(where_cols)))
            query = f"UPDATE { name } SET { updated_cols.join(suffix='=?') } WHERE { where_cols.join(sep=' AND ', suffix='=?') }"
            vals = [ self.cols[x] for x in updated_cols ] + [ self.cols[x] for x in where_cols ]
            await db.execute(query, vals)

        async def delete():
            query = f"DELETE FROM { name } WHERE { where_cols.join(sep=' AND ', suffix='=?') }"
            vals = [ self.cols[x] for x in where_cols ]
            await db.execute(query, vals)
            
        object.__setattr__(self, 'update', update)
        object.__setattr__(self, 'delete', delete)

    def check_col(self, col):
        if col not in self.cols:
            raise AttributeError(f'Column "{col}" not found in "{self.__class__.__name__}" relation.')

    def __getattr__(self, attr):
        self.check_col(attr)
        return self.cols[attr]

    def __setattr__(self, attr, val):
        self.check_col(attr)
        self.cols[attr] = val

class Guild(Relation):
    COLS = Cols('id', 'discord_id', 'current_challenge_id', 'spreadsheet_key')

    @staticmethod
    async def fetch_or_insert(db, discord_id):
        g =  await fromrow(Guild, db,
            f'SELECT { Guild.COLS } FROM guild WHERE discord_id = ?', [discord_id])
        if g is None:
            id = (await db.execute('INSERT INTO guild (discord_id) VALUES (?)', [discord_id])).lastrowid
            g = Guild(db, [id, discord_id, None, None])
        return g

    def __init__(self, db, row):
        super().__init__(db, 'guild', Guild.COLS, Cols('id'), row)

    async def fetch_current_challenge(self):
        return await Challenge.fetch_current_challenge(self.db, self.current_challenge_id)

    async def has_challenge(self, name):
        return await self.db.fetchval('SELECT COUNT(1) FROM challenge WHERE guild_id = ? AND name = ?', [self.id, name])

    async def add_challenge(self, name, start_time):
        id = (await self.db.execute('INSERT INTO challenge (guild_id, name, start_time) VALUES (?, ?, ?)',
            [self.id, name, start_time])).lastrowid
        return Challenge(self.db, [id, self.id, name, start_time, None, None])

    async def fetch_users(self):
        rows = await self.db.fetchall(f'''
            SELECT DISTINCT { User.COLS.join(prefix='U.') } FROM user U
            JOIN participant P ON U.id = P.user_id
            JOIN challenge C ON C.id = P.challenge_id
            WHERE C.guild_id = ?''', [self.id])
        return [User(self.db, row) for row in rows]

    async def fetch_challenges(self):
        rows = await self.db.fetchall(f'''
            SELECT { Challenge.COLS.join(prefix='C.') } FROM challenge C
            WHERE C.guild_id = ?
            ORDER BY C.start_time''', [self.id])
        return [Challenge(self.db, row) for row in rows]

class User(Relation):
    COLS = Cols('id', 'discord_id', 'color', 'name')

    @staticmethod
    async def fetch_or_insert(db, discord_id, name):
        u = await fromrow(User, db, f'SELECT { User.COLS } FROM user WHERE discord_id = ?', [discord_id])
        if u is None:
            color = '#FFFFFF'
            id = (await db.execute('INSERT INTO user (discord_id, color, name) VALUES (?, ?, ?)',
                [discord_id, color, name])).lastrowid
            u = User(db, [id, discord_id, color, name, 0.0])
        return u

    async def add_award(self, award_url, time):
        await self.db.execute('INSERT INTO award (user_id, url, time) VALUES(?, ?, ?)', [self.id, award_url, time])

    async def remove_award(self, award_url):
        await self.db.execute('DELETE FROM award WHERE url = ? AND user_id = ?', [award_url, self.id])

    def __init__(self, db, row):
        super().__init__(db, 'user', User.COLS, Cols('id'), row)

class Challenge(Relation):
    COLS = Cols('id', 'guild_id', 'name', 'start_time', 'finish_time', 'award_url')

    @staticmethod
    async def fetch_current_challenge(db, guild_id):
        return await fromrow(Challenge, db, f'SELECT { Challenge.COLS } FROM challenge WHERE id = ?', [guild_id])

    def __init__(self, db, row):
        super().__init__(db, 'challenge', Challenge.COLS, Cols('id'), row)

    async def has_started(self):
        return await self.db.fetchval('''
            SELECT COUNT(1) FROM challenge C
            JOIN round R ON R.challenge_id = C.id
            WHERE C.id = ?''', [self.id])

    async def fetch_last_round(self):
        return await fromrow(Round, self.db, f'''
            SELECT { Round.COLS } FROM round
            WHERE challenge_id = ?
            ORDER BY num DESC
            LIMIT 1''', [self.id])

    async def fetch_rounds(self):
        rows = await self.db.fetchall(f'''
            SELECT { Round.COLS } FROM round
            WHERE challenge_id = ?
            ORDER BY num''', [self.id])
        return [Round(self.db, row) for row in rows]

    async def add_round(self, num, start, finish):
        id = (await self.db.execute('INSERT INTO round (num, challenge_id, start_time, finish_time) VALUES (?, ?, ?, ?)',
            [num, self.id, start, finish])).lastrowid
        return Round(self.db, [id, num, self.id, start, finish, False])

    async def fetch_pool(self, pool_name):
        return await fromrow(Pool, self.db,
            f'SELECT { Pool.COLS } FROM pool WHERE challenge_id = ? AND name = ?', [self.id, pool_name])

    async def fetch_pools(self):
        rows = await self.db.fetchall(f'SELECT { Pool.COLS } FROM pool WHERE challenge_id = ?', [self.id])
        return [Pool(self.db, row) for row in rows]

    async def add_pool(self, pool_name):
        await self.db.execute('INSERT INTO pool (challenge_id, name) VALUES (?, ?)', [self.id, pool_name])

    async def has_pool(self, pool_name):
        return await self.db.fetchval('SELECT COUNT(1) FROM pool WHERE challenge_id = ? AND name = ?', [self.id, pool_name])

    async def has_title(self, title):
        return await self.db.fetchval('''
            SELECT COUNT(1) FROM title T
            JOIN pool P ON P.id = T.pool_id
            WHERE P.challenge_id = ? AND T.name = ?''', [self.id, title])

    async def fetch_title(self, title):
        return await fromrow(Title, self.db, f'''
            SELECT { Title.COLS.join(prefix='T.') } FROM title T
            JOIN pool P ON P.id = T.pool_id
            WHERE P.challenge_id = ? AND T.name = ?''', [self.id, title])

    async def fetch_titles(self):
        rows = await self.db.fetchall(f'''
            SELECT { Title.COLS.join(prefix='T.') } FROM title T
            JOIN pool P ON P.id = T.pool_id
            WHERE P.challenge_id = ?''', [self.id])
        return [Title(self.db, row) for row in rows]

    async def has_participant(self, user_id):
        return await self.db.fetchval(
            'SELECT COUNT(1) FROM participant WHERE challenge_id = ? AND user_id = ?', [self.id, user_id])

    async def fetch_participant(self, user_id):
        return await fromrow(Participant, self.db,
            f'SELECT { Participant.COLS } FROM participant P WHERE challenge_id = ? AND user_id = ?', [self.id, user_id])

    async def fetch_users_participants(self):
        rows = await self.db.fetchall(f'''
            SELECT { User.COLS.join(prefix='U.') }, { Participant.COLS.join(prefix='P.') }
            FROM user U
            JOIN participant P ON U.id = P.user_id
            WHERE P.challenge_id = ?''', [self.id])
        n = len(User.COLS)
        return [(User(self.db, row[:n]), Participant(self.db, row[n:])) for row in rows]

    async def fetch_participants(self):
        rows = await self.db.fetchall(f'SELECT { Participant.COLS } FROM participant WHERE challenge_id = ?', [self.id])
        return [Participant(self.db, row) for row in rows]

    async def add_participant(self, user_id):
        id = (await self.db.execute('INSERT INTO participant (challenge_id, user_id) VALUES (?, ?)',
            [self.id, user_id])).lastrowid
        return Participant(self.db, [id, self.id, user_id, None, None, None])

    async def set_award(self, award_url):
        await self.db.execute('UPDATE challenge SET award_url = ? WHERE id = ?', [award_url, self.id])

class Participant(Relation):
    COLS = Cols('id', 'challenge_id', 'user_id', 'failed_round_id', 'progress_current', 'progress_total')

    @staticmethod
    async def fail_participants(db, round_id, participant_ids):
        await db.executemany('UPDATE participant SET failed_round_id = ? WHERE id = ?',
            map(lambda x: (round_id, x), participant_ids))

    def __init__(self, db, row):
        super().__init__(db, 'participant', Participant.COLS, Cols('id'), row)

    def has_failed(self):
        return self.failed_round_id is not None

class Pool(Relation):
    COLS = Cols('id', 'challenge_id', 'name')

    def __init__(self, db, row):
        super().__init__(db, 'pool', Pool.COLS, Cols('id'), row)

    async def fetch_title(self, name):
        return await fromrow(Title, self.db,
            f'SELECT { Title.COLS } FROM title WHERE challenge_id = ? AND name = ?', [self.id, name])

    async def fetch_titles(self):
        rows = await self.db.fetchall(f'SELECT { Title.COLS } FROM title WHERE pool_id = ?', [self.id])
        return [Title(self.db, row) for row in rows]

    async def fetch_unused_titles(self):
        rows = await self.db.fetchall(
            f'SELECT { Title.COLS } FROM title WHERE pool_id = ? AND is_used = 0', [self.id])
        return [Title(self.db, row) for row in rows]

    async def add_title(self, participant_id, name, url=None, is_used=False):
        id = (await self.db.execute(
            'INSERT INTO title (pool_id, participant_id, name, url, is_used) VALUES (?, ?, ?, ?, ?)',
            [self.id, participant_id, name, url, is_used])).lastrowid
        return Title(self.db, [id, self.id, participant_id, name, url, is_used])

class Title(Relation):
    COLS = Cols('id', 'pool_id', 'participant_id', 'name', 'url', 'is_used')

    def __init__(self, db, row):
        super().__init__(db, 'title', Title.COLS, Cols('id'), row)

class Round(Relation):
    COLS = Cols('id', 'num', 'challenge_id', 'start_time', 'finish_time', 'is_finished')

    def __init__(self, db, row):
        super().__init__(db, 'round', Round.COLS, Cols('id'), row)

    async def fetch_rolls_watchers_proposers(self):
        rows = await self.db.fetchall(f'''
            SELECT
                { Roll.COLS.join(prefix='R.') },
                { User.COLS.join(prefix='U1.') },
                { User.COLS.join(prefix='U2.') }
            FROM roll R
            JOIN participant P1 ON P1.id = R.participant_id
            JOIN user U1 ON U1.id = P1.user_id

            JOIN title T ON T.id = R.title_id
            JOIN participant P2 ON P2.id = T.participant_id
            JOIN user U2 ON U2.id = P2.user_id

            WHERE R.round_id = ?''', [self.id])
        n1 = len(Roll.COLS)
        n2 = n1 + len(User.COLS)
        return [(Roll(self.db, row[:n1]), User(self.db, row[n1:n2]), User(self.db, row[n2:])) for row in rows]

    async def fetch_roll(self, participant_id):
        return await fromrow(Roll, self.db, 
            f'SELECT { Roll.COLS } FROM roll WHERE round_id = ? AND participant_id = ?', [self.id, participant_id])

    async def fetch_rolls(self):
        rows = await self.db.fetchall(f'SELECT { Roll.COLS } FROM roll WHERE round_id = ?', [self.id])
        return [Roll(self.db, row) for row in rows]

    async def add_roll(self, participant_id, title_id):
        await self.db.execute(
            'INSERT INTO roll (round_id, participant_id, title_id) VALUES (?, ?, ?)', [self.id, participant_id, title_id])

class Roll(Relation):
    COLS = Cols('round_id', 'participant_id', 'title_id', 'score')

    def __init__(self, db, row):
        super().__init__(db, 'roll', Roll.COLS, Cols('round_id', 'participant_id'), row)

    async def fetch_title(self):
        return await fromrow(Title, self.db, f'SELECT { Title.COLS } FROM title WHERE id = ?', [self.title_id])

    async def fetch_participant(self):
        row = await self.db.fetchrow(f'''
            SELECT { User.COLS.join(prefix='U.') }
            FROM roll R
            JOIN participant P ON P.id = R.participant_id
            JOIN user U ON P.user_id = U.id
            WHERE R.round_id = ? AND R.participant_id = ?''', [self.round_id, self.participant_id])
        return User(self.db, row)

    async def fetch_title_author(self):          
        row = await self.db.fetchrow(f'''
            SELECT { User.COLS.join(prefix='U.') }
            FROM roll R
            JOIN title T ON T.id = R.title_id
            JOIN participant P ON P.id = T.participant_id
            JOIN user U ON P.user_id = U.id
            WHERE R.round_id = ? AND R.participant_id = ?''', [self.round_id, self.participant_id])
        return User(self.db, row)

class KarmaHistory(Relation):
    COLS = Cols('user_id', 'karma', 'time')

    def __init__(self, db, row):
        super().__init__(db, 'karma_history', KarmaHistory.COLS, Cols('user_id', 'time'), row)

    @staticmethod
    async def fetch_user_karma(db, user_id):
        rows = await db.fetchall(f'''
            SELECT karma
            FROM karma_history
            WHERE user_id = ?
            ORDER BY time DESC
            LIMIT 1''', [user_id])

        print(rows)
        if rows:
            return rows[-1][0]
        else:
            return None # todo: maybe use constant -> starting_karma

    @staticmethod
    async def clear_user_karma_history(db, user_id):
        await db.execute(f'''
            DELETE FROM karma_history
            WHERE user_id = ?''', [user_id])

    @staticmethod
    async def insert_or_update_karma(db, user_id, karma, time):
        row = await db.fetchrow(f'''
            SELECT { KarmaHistory.COLS }
            FROM karma_history
            WHERE user_id = ? AND time = ?
            ORDER BY time''', [user_id, time])

        if row is None:
            await db.execute('''
                INSERT INTO karma_history
                (user_id, karma, time)
                VALUES(?, ?, ?)''', [user_id, karma, time])
        else:
            karma_history = KarmaHistory(db, row)
            karma_history.karma = karma
            await karma_history.update()

    @staticmethod
    async def fetch_karma_history(db, user_id):
        rows = await db.fetchall(f'''
            SELECT { KarmaHistory.COLS }
            FROM karma_history
            WHERE user_id = ?
            ORDER BY time''', [user_id])

        return [KarmaHistory(db, row) for row in rows]

class UserStats:
    @staticmethod
    async def fetch(db, user_id, guild_id):
        row = await db.fetchrow('''
            SELECT COUNT(*), COALESCE(SUM(CASE WHEN P.failed_round_id IS NULL AND C.finish_time is NOT NULL THEN 1 ELSE 0 END),0) FROM challenge C
            JOIN participant P ON P.challenge_id = C.id
            WHERE P.user_id = ?''', [user_id])
        num_challenges,num_completed = row

        avg_rate = await db.fetchval('''
            SELECT AVG(R.score) FROM roll R
            JOIN participant P ON P.id = R.participant_id
            WHERE P.user_id = ? AND R.score IS NOT NULL''', [user_id])

        avg_title_score = await db.fetchval('''
            SELECT AVG(R.score) FROM roll R
            JOIN title T ON T.id = R.title_id
            JOIN participant P ON P.id = T.participant_id
            WHERE P.user_id = ? AND R.score IS NOT NULL''', [user_id])

        most_watched = await db.fetchall('''
            SELECT U.name, COUNT(U.id) AS count FROM roll R
            JOIN participant P1 ON P1.id = R.participant_id

            JOIN title T ON T.id = R.title_id
            JOIN participant P2 ON P2.id = T.participant_id
            JOIN user U ON U.id = P2.user_id

            WHERE P1.user_id = ?
            GROUP BY U.id
            ORDER BY count DESC LIMIT 6''', [user_id])

        most_sniped = await db.fetchall('''
            SELECT U.name, COUNT(U.id) AS count FROM roll R
            JOIN participant P1 ON P1.id = R.participant_id
            JOIN user U ON U.id = P1.user_id

            JOIN title T ON T.id = R.title_id
            JOIN participant P2 ON P2.id = T.participant_id

            WHERE P2.user_id = ?
            GROUP BY U.id
            ORDER BY count DESC LIMIT 6''', [user_id])

        awards = await db.fetchall('''
            SELECT * FROM (
                SELECT C.award_url url, C.finish_time time FROM challenge C
                JOIN participant P ON P.challenge_id = C.id
                WHERE P.user_id = ? AND C.guild_id = ?
                    AND P.failed_round_id IS NULL AND C.award_url IS NOT NULL
                UNION
                SELECT A.url url, A.time time from award A
                JOIN user U ON A.user_id = U.id
                WHERE A.user_id = ?
            )
            ORDER BY time''', [user_id, guild_id, user_id])
        awards = [x[0] for x in awards]

        karma = await KarmaHistory.fetch_user_karma(db, user_id)

        finish_time = None
        challenge = await Challenge.fetch_current_challenge(db, guild_id)
        if challenge is not None:
            last_round = await challenge.fetch_last_round()
            participant = await challenge.fetch_participant(user_id)
            if last_round is not None and participant is not None and not participant.has_failed and not last_round.is_finished:
                finish_time = last_round.finish_time

        return UserStats(num_challenges,
                         num_completed,
                         avg_rate,
                         avg_title_score,
                         most_watched,
                         most_sniped,
                         finish_time,
                         karma,
                         awards)

    def __init__(self,
                 num_challenges,
                 num_completed,
                 avg_rate,
                 avg_title_score,
                 most_watched,
                 most_sniped,
                 finish_time,
                 karma,
                 awards):
        self.num_challenges = num_challenges
        self.num_completed = num_completed
        self.avg_rate = avg_rate
        self.avg_title_score = avg_title_score
        self.most_watched = most_watched
        self.most_sniped = most_sniped
        self.finish_time = finish_time
        self.karma = karma
        self.awards = awards