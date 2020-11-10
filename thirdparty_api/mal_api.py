import requests as r
import re

def length_str_to_minutes(s):
    mins = 0
    mins_parsed = re.search(r'(\d+)? min', s, flags=re.DOTALL)
    if mins_parsed:
        mins += int(mins_parsed[1])
    hrs_parsed = re.search(r'(\d+)? hr', s, flags=re.DOTALL)

    if hrs_parsed:
        mins += 60*int(hrs_parsed[1])
    return mins

def calc_complexity(score, num_of_episodes, length):
    MAX_TIME = 26*25 # 26 episodes 25 mins each
    time_spent = num_of_episodes * length
    hardness_to_watch = (max(1, min(9 - score, 8)) - 1) / 7
    complexity = hardness_to_watch * (time_spent / MAX_TIME) * 100
    return int(complexity)

def mal_parser(html):
    name=re.search(r'\<meta property=\"og:title\" content=\"(.*?)\"\>', html)[1]
    score=re.search(r'.*?score\-label.*?\>(\d+?\.\d+?)\<.*?', html)[1]
    num_of_episodes=re.search(r'pisodes\:</span>.*?(\d+).*?\<', html, flags=re.DOTALL)[1]
    length_str=re.search(r'Duration\:</span>.*?\"(.*?)\".*?\<', html, flags=re.DOTALL)[1]
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

