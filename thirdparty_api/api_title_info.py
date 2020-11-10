import requests
import re

import thirdparty_api.kinopoisk_api as kinopoisk_api
import thirdparty_api.mal_api as mal_api

class ApiTitleInfo:
    def __init__(self, name, score, length, complexity):
        self.name = name
        self.score = score
        self.length = length
        self.complexity = complexity

    @staticmethod
    def from_url(url, config):
        score = None
        name = None
        print(re.search(r'kinopoisk', url))
        if re.search(r'kinopoisk', url):
            json = kinopoisk_api.get_film_data(url, config['kinopoisk_api_token'])
            name = json['data']['nameEn']
            score = json['rating']['rating']
            length = kinopoisk_api.length_to_minutes(json['data']['filmLength'])
            complexity = kinopoisk_api.calc_complexity(score, length)
            return ApiTitleInfo(name, score, length, complexity)
        elif re.search(r'myanimelist', url):
            data = mal_api.get_anime_data(url)
            name = data['name']
            score = data['score']
            num_of_episodes = data['num_of_episodes']
            length = data['length']
            complexity = mal_api.calc_complexity(score, num_of_episodes, length)
            return ApiTitleInfo(name, score, length, complexity)
        else:
            return None