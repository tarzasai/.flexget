from __future__ import unicode_literals, division, absolute_import
import os

from flexget import plugin
from flexget.event import event
from flexget.utils import json


class UoccinLookup(object):

    schema = { 'type': 'string', 'format': 'path' }
    
    # Run after metainfo_series / thetvdb_lookup / imdb_lookup
    @plugin.priority(100)
    def on_task_metainfo(self, task, config):
        if not task.entries:
            return
        movcoll = self.get_json(config, 'movies.collected.json')
        movseen = self.get_json(config, 'movies.watched.json')
        sercoll = self.get_json(config, 'series.collected.json')
        serseen = self.get_json(config, 'series.watched.json')
        if not (movcoll or movseen or sercoll or serseen):
            return
        for entry in task.entries:
            if all(field in entry for field in ['tvdb_id', 'series_season', 'series_episode']):
                eid = '%s.S%02dE%02d' % (entry['tvdb_id'], entry['series_season'], entry['series_episode'])
                entry['uoccin_collected'] = eid in sercoll
                entry['uoccin_watched'] = eid in serseen
            elif 'imdb_id' in entry:
                eid = entry['imdb_id']
                entry['uoccin_collected'] = eid in movcoll
                entry['uoccin_watched'] = eid in movseen
    
    def get_json(self, config, filename):
        fn = os.path.join(config, filename)
        if os.path.exists(fn):
            with open(fn, 'r') as fo:
                return json.load(fo)
        return {}


@event('plugin.register')
def register_plugin():
    plugin.register(UoccinLookup, 'uoccin_lookup', api_ver=2)
