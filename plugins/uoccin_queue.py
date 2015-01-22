from __future__ import unicode_literals, division, absolute_import
import os

from flexget import plugin
from flexget.event import event
from flexget.utils import json


class UoccinQueue(object):

    schema = {
        'type': 'object',
        'properties': {
            'path': {'type': 'string', 'format': 'path'},
            'tags': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1},
            'quality': {'type': 'string', 'format': 'quality_requirements'},
        },
        'required': ['path'],
        'additionalProperties': False
    }
    
    def on_task_output(self, task, config):
        """Add accepted series and/or movies to uoccin's watchlist"""
        series = {}
        movies = {}
        for entry in task.accepted:
            if all(field in entry for field in ['tvdb_id', 'series_name']):
                series[str(entry['tvdb_id'])] = entry['series_name']
            elif all(field in entry for field in ['imdb_id', 'movie_name']):
                movies[entry['imdb_id']] = entry['movie_name']
        if series:
            dest = os.path.join(config['path'], 'series.watchlist.json')
            data = {}
            if os.path.exists(dest):
                with open(dest, 'r') as f:
                    data = json.load(f)
            n = 0
            for tvdb_id, title in series.items():
                if not tvdb_id in data.keys():
                    self.log.verbose('adding series %s (%s) to Uoccin watchlist' % (tvdb_id, title))
                    data[tvdb_id] = { 'name': title }
                    if 'tags' in config:
                        data[tvdb_id]['tags'] = [tag for tag in config['tags']]
                    if 'quality' in config:
                        data[tvdb_id]['quality'] = config['quality']
                    n += 1
            if n > 0:
                text = json.dumps(data, sort_keys=True, indent=4, separators=(',', ': '))
                with open(dest, 'w') as f:
                    f.write(text)
            self.log.info('%d series added to Uoccin watchlist' % n)
        if movies:
            dest = os.path.join(config['path'], 'movies.watchlist.json')
            data = {}
            if os.path.exists(dest):
                with open(dest, 'r') as f:
                    data = json.load(f)
            n = 0
            for imdb_id, title in movies.items():
                if not imdb_id in data.keys():
                    self.log.verbose('adding movie %s (%s) to Uoccin collection' % (imdb_id, title))
                    data[imdb_id] = { 'name': title }
                    if 'tags' in config:
                        data[imdb_id]['tags'] = [tag for tag in config['tags']]
                    if 'quality' in config:
                        data[imdb_id]['quality'] = config['quality']
                    n += 1
            if n > 0:
                text = json.dumps(data, sort_keys=True, indent=4, separators=(',', ': '))
                with open(dest, 'w') as f:
                    f.write(text)
            self.log.info('%d movies added to Uoccin watchlist' % n)


@event('plugin.register')
def register_plugin():
    plugin.register(UoccinQueue, 'uoccin_queue', api_ver=2)
