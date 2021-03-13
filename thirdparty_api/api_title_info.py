import requests
import re

import thirdparty_api.kinopoisk_api as kinopoisk_api
import thirdparty_api.mal_api as mal_api

class ApiTitleInfo:
    def __init__(self, name, score, duration, num_of_episodes, difficulty):
        self.name = name
        self.score = score
        self.duration = duration
        self.difficulty = difficulty
        self.num_of_episodes = num_of_episodes

    @staticmethod
    def from_url(url, config):
        score = None
        name = None
        try:
            if re.search(r'kinopoisk', url):
                json = kinopoisk_api.get_film_data(url, config['kinopoisk_api_token'])
                name = json['data']['nameRu']
                if not name:
                    name = json['data']['nameEn']
                score = json['rating']['rating']
                duration = kinopoisk_api.length_to_minutes(json['data']['filmLength'])
                difficulty = kinopoisk_api.calc_difficulty(score, duration)
                # type_ = json['rating']['type']
                #num_of_episodes = 1 if type_.lower() == 'film' else 10 #todo: calc number of episodes from api 
                num_of_episodes = 1
                return ApiTitleInfo(name, score, duration, num_of_episodes, difficulty) 
            elif re.search(r'myanimelist', url):
                data = mal_api.get_anime_data(url)
                name = data['name']
                score = data['score']
                num_of_episodes = data['num_of_episodes']
                duration = data['length'] * num_of_episodes
                difficulty = mal_api.calc_difficulty(score, duration)
                return ApiTitleInfo(name, score, duration, num_of_episodes, difficulty)
            else:
                return None
        except Exception as e:
            print(e)