from __future__ import unicode_literals, division, absolute_import
import os

from flexget import plugin
from flexget.event import event
from flexget.utils import json


class UoccinCollect(object):

    schema = { 'type': 'string', 'format': 'path' }
    
    def on_task_output(self, task, config):
        """Add accepted episodes and/or movies to uoccin's collection"""
        movies = []
        series = {}
        for entry in task.accepted:
            if 'imdb_id' in entry:
                movies.append(entry['imdb_id'])
            elif all(field in entry for field in ['tvdb_id', 'series_season', 'series_episode']):
                tvdb_id = str(entry['tvdb_id'])
                season = str(entry['series_season'])
                episode = entry['series_episode'] # it's int in the json array
                if not tvdb_id in series:
                    series[tvdb_id] = {}
                if not season in series[tvdb_id]:
                    series[tvdb_id][season] = []
                series[tvdb_id][season].append(episode)
        if movies:
            dest = os.path.join(config, 'movies.collected.json')
            data = []
            if os.path.exists(dest):
                with open(dest, 'r') as f:
                    data = json.load(f)
            n = 0
            for imdb_id in movies:
                if not imdb_id in data:
                    self.log.verbose('adding movie %s to Uoccin collection' % imdb_id)
                    data.append(imdb_id)
                    n += 1
            if n > 0:
                with open(dest, 'w') as f:
                    json.dump(data, f)
            self.log.info('%d movies added to Uoccin collection' % n)
        if series:
            dest = os.path.join(config, 'series.collected.json')
            data = {}
            if os.path.exists(dest):
                with open(dest, 'r') as f:
                    data = json.load(f)
            n = 0
            for tvdb_id in series:
                if not tvdb_id in data:
                    data[tvdb_id] = {}
                for season in series[tvdb_id]:
                    if not season in data[tvdb_id]:
                        data[tvdb_id][season] = []
                    for episode in series[tvdb_id][season]:
                        if not episode in data[tvdb_id][season]:
                            self.log.verbose('adding series %s, episode S%02dE%02d to Uoccin collection' % 
                                (tvdb_id, season, episode))
                            data[tvdb_id][season].append(episode)
                            n += 1
                    data[tvdb_id][season].sort()
            if n > 0:
                with open(dest, 'w') as f:
                    json.dump(data, f)
            self.log.info('%d episodes added to Uoccin collection' % n)


@event('plugin.register')
def register_plugin():
    plugin.register(UoccinCollect, 'uoccin_collect', api_ver=2)
