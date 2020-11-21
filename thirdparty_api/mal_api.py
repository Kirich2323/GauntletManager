import requests as r
import re

def length_str_to_minutes(s):
    mins = 0
    mins_parsed = re.search(r'(\d+?) min', s, flags=re.DOTALL)
    if mins_parsed:
        mins += int(mins_parsed[1])
    hrs_parsed = re.search(r'(\d+?) hr', s, flags=re.DOTALL)

    if hrs_parsed:
        mins += 60*int(hrs_parsed[1])
    return mins

def calc_difficulty(score, duration):
    MAX_TIME = 26*22 # 26 episodes 22 mins each
    hardness_to_watch = (min(13 - score, 9) - 3) / 6
    time = (duration / MAX_TIME)
    difficulty = (0.5 * (hardness_to_watch + time) + 0.25 * hardness_to_watch * time) * 100
    return int(difficulty)

def mal_parser(html):
    name = re.search(r'\<meta property=\"og:title\" content=\"(.*?)\"\>', html)[1]
    score = re.search(r'.*?score\-label.*?\>(\d+?\.\d+?)\<.*?', html)[1]
    num_of_episodes = re.search(r'pisodes\:</span>.*?(\d+).*?\<', html, flags=re.DOTALL)[1]
    length_str = re.search(r'uration\:\</sp.*?(.*?).*?\</div', html, flags=re.DOTALL)[0]
    length = length_str_to_minutes(length_str)
    if length == 0:
        length = 20 # todo: decide if it's ok to do it like that? maybe should handle it differently
    return {'name': name, 'score': float(score), 'num_of_episodes': int(num_of_episodes), 'length' : length}

def get_anime_data(url):
    response = r.get(url)
    if response.status_code == 200:
        html=response.text
        return mal_parser(html)
    else:
        raise "Bad myanimelist api status code recieved"

