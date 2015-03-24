from __future__ import unicode_literals, division, absolute_import
import os

from flexget import plugin
from flexget.event import event
from flexget.utils import json


class UoccinWatched(object):

    schema = { 'type': 'string', 'format': 'path' }
    
    def on_task_output(self, task, config):
        """Add accepted episodes and/or movies to uoccin's watched list"""
        series = {}
        movies = {}
        for entry in task.accepted:
            if all(field in entry for field in ['tvdb_id', 'series_name', 'series_season', 'series_episode']):
                eid = str(entry['tvdb_id'])
                sno = str(entry['series_season'])
                eno = entry['series_episode']
                show = series[eid] if eid in series else {'name': entry['series_name'], 'seasons': {}}
                if not sno in show['seasons']:
                    show['seasons'][sno] = []
                if not eno in show['seasons'][sno]:
                    show['seasons'][sno].append(eno)
            elif all(field in entry for field in ['imdb_id', 'movie_name']):
                movies[entry['imdb_id']] = entry['movie_name']
        if series:
            for eid, show in series.items():
                dest = os.path.join(config, 'series.watched.%s.json' % eid)
                data = {'name': show['name'], 'rating': 5}
                if os.path.exists(dest):
                    with open(dest, 'r') as f:
                        data = json.load(f)
                for season, episodes in show['seasons'].items():
                    lst = data[season] if season in data else []
                    data[season] = list(set(lst + episodes))
                text = json.dumps(data, sort_keys=True, indent=4, separators=(',', ': '))
                with open(dest, 'w') as f:
                    f.write(text)
            self.log.info('Added watched episodes to Uoccin')
        if movies:
            dest = os.path.join(config, 'movies.watched.json')
            data = {}
            if os.path.exists(dest):
                with open(dest, 'r') as f:
                    data = json.load(f)
            n = 0
            for eid, name in movies.items():
                if not eid in data:
                    data[eid] = {'name': name, 'rating': 5}
                    n += 1
            if n > 0:
                text = json.dumps(data, sort_keys=True, indent=4, separators=(',', ': '))
                with open(dest, 'w') as f:
                    f.write(text)
            self.log.info('Added watched movies to Uoccin')


@event('plugin.register')
def register_plugin():
    plugin.register(UoccinWatched, 'uoccin_watched', api_ver=2)
