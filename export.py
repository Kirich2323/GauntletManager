import pygsheets
import asyncio
import re

from pygsheets.exceptions import WorksheetNotFound
from pygsheets.custom_types import HorizontalAlignment
from pygsheets import Cell, DataRange
from pygsheets.utils import format_addr
from db import Challenge

gsheets_client = pygsheets.authorize()

def col2tuple(col):
    try:
        rgb = list(map(lambda x: int(x, 16) / 255.0, re.findall(r'[a-fA-F0-9]{2}', col)))
        return (rgb[0], rgb[1], rgb[2], 0)
    except:
        raise Exception('Invalid color {}.'.format(col))

def update_fgcolor(cell):
    luminosity = (0.2126*cell.color[0] + 0.7152*cell.color[1] + 0.0722*cell.color[2])
    if luminosity >= 0.5:
        cell.set_text_format('foregroundColor', (0, 0, 0, 0))
    else:
        cell.set_text_format('foregroundColor', (1, 1, 1, 0))

def score_col(score):
    if score is None:
        return '#808080'
    elif score < 10.0 / 3.0:
        return '#DD7E6B'
    elif score < 10.0 / 1.5:
        return '#F1C232'
    else:
        return '#6AA84F'

class ColWriter:
    def __init__(self, users_participants):
        self.col = 0
        self.row = 0
        self.users = { p.id: u for u, p in users_participants }
        self.cells = []

    def new_cell(self, value):
        return Cell((self.row + 1, self.col + 1), value)

    def add_cell(self, cell):
        update_fgcolor(cell)
        self.cells.append(cell)
        self.row += 1

    def write_header(self, text):
        cell = self.new_cell(text)
        cell.set_text_format('bold', True)
        cell.color = col2tuple('#C0C0C0')
        cell.horizontal_alignment = HorizontalAlignment.CENTER
        self.add_cell(cell)

    def write_participant(self, participant):
        user = self.users[participant.id]
        cell = self.new_cell(user.name)
        cell.color = col2tuple(user.color)
        self.add_cell(cell)

    def write_score(self, score):
        cell = self.new_cell('-' if score is None else score)
        cell.color = col2tuple(score_col(score))
        cell.horizontal_alignment = HorizontalAlignment.CENTER
        self.add_cell(cell)

    def write_title(self, title, failed=False):
        cell = self.new_cell(title.name)
        if title.url is not None:
            cell.value = f'=HYPERLINK("{ title.url }"; "{ title.name }")'
            cell.set_text_format('underline', False)
        user = self.users[title.participant_id]
        cell.color = col2tuple(user.color)
        if failed:
            cell.set_text_format('strikethrough', True)
            cell.color = col2tuple('#FF0000')
        self.add_cell(cell)

    def write_fail(self):
        cell = self.new_cell('FAILED')
        cell.color = col2tuple('#FF0000')
        cell.horizontal_alignment = HorizontalAlignment.CENTER
        self.add_cell(cell)

    def next_col(self):
        self.col += 1
        self.row = 0

def update_stats(stats, participant, score, num_rounds):
    id = participant.id
    if id not in stats:
        stats[id] = (None, None, None, None)
    if score is None:
        return
    min_, max_, sum_, n = stats[id]
    min_ = score if min_ is None else min(min_, score)
    max_ = score if max_ is None else max(max_, score)
    sum_ = score if sum_ is None else sum_ + score
    n = 1 if n is None else n + 1
    stats[id] = (min_, max_, sum_, n)

def sync_export(worksheet, users_participants, rounds_rolls, pools_titles, all_titles):
    writer = ColWriter(users_participants)
    writer.write_header('Participants')
    sorted_participants = list(map(lambda x: x[1], sorted(users_participants, key=lambda x: x[0].name)))

    for participant in sorted_participants:
        writer.write_participant(participant)
    writer.next_col()

    titles = { t.id: t for t in all_titles }
    stats = {}
    for round, rolls in rounds_rolls:
        roll_by_participant_id = { r.participant_id: r for r in rolls }
        fmt = '%d.%m'
        writer.write_header(f'Round { round.num } ({round.start_time.strftime(fmt)}-{round.finish_time.strftime(fmt)})')
        for participant in sorted_participants:
            if participant.id not in roll_by_participant_id:
                writer.write_fail()
            else:
                title = titles[roll_by_participant_id[participant.id].title_id]
                writer.write_title(title, participant.failed_round_id == round.id)

        writer.next_col()
        writer.write_header('Score')
        for participant in sorted_participants:
            score = roll_by_participant_id[participant.id].score if participant.id in roll_by_participant_id else None
            update_stats(stats, participant, score, len(rounds_rolls))
            writer.write_score(score)
        writer.next_col()

    stats = { k: (v[0], v[1], None if v[2] is None else v[2] / v[3]) for k, v in stats.items() }
    for i, col in enumerate(['Min', 'Max', 'Avg']):
        writer.write_header(col)
        for participant in sorted_participants:
            stat = None if participant.id not in stats else stats[participant.id][i]
            writer.write_score(stat)
        writer.next_col()

    for pool, titles in pools_titles:
        writer.write_header(f'{ pool.name } (unused titles)')
        for title in titles:
            if not title.is_used:
                writer.write_title(title)
        writer.next_col()

    # Cell((0, 0)) clears the entire screen
    worksheet.update_cells([Cell((0, 0))] + writer.cells)
    worksheet.adjust_column_width(1, worksheet.cols)

async def export(spreadsheet_key, challenge):
    spreadsheet = gsheets_client.open_by_key(spreadsheet_key)
    try:
        worksheet = spreadsheet.worksheet_by_title(challenge.name)
    except WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(challenge.name)

    users_participants = await challenge.fetch_users_participants()
    pools = await challenge.fetch_pools()
    pool_titles = [ await pool.fetch_titles() for pool in pools ]
    pools_titles = list(zip(pools, pool_titles))
    all_titles = [ t for pt in pool_titles for t in pt ]
    rounds = await challenge.fetch_rounds()
    rounds_rolls = list(zip(rounds, [ await round.fetch_rolls() for round in rounds ]))

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None,
        sync_export, worksheet, users_participants, rounds_rolls, pools_titles, all_titles)