from __future__ import unicode_literals, division, absolute_import
import os

from flexget import plugin
from flexget.event import event
from flexget.utils import json


class UoccinLookup(object):

    schema = { 'type': 'string', 'format': 'path' }
    
    # Run after metainfo_series and thetvdb_lookup
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
            if 'imdb_id' in entry:
                entry['uoccin_collected'] = movcoll and (entry['imdb_id'] in movcoll)
                entry['uoccin_watched'] = movcoll and (entry['imdb_id'] in movseen)
            elif all(field in entry for field in ['tvdb_id', 'series_season', 'series_episode']):
                tvdb_id = str(entry['tvdb_id'])
                season = str(entry['series_season'])
                episode = entry['series_episode'] # it's int in the json array
                entry['uoccin_collected'] = (sercoll is not None and tvdb_id in sercoll and 
                                             season in sercoll[tvdb_id] and episode in sercoll[tvdb_id][season])
                entry['uoccin_watched'] = (serseen is not None and tvdb_id in serseen and 
                                           season in serseen[tvdb_id] and episode in serseen[tvdb_id][season])
    
    def get_json(self, config, filename):
        fn = os.path.join(config, filename)
        if os.path.exists(fn):
            with open(fn, 'r') as fo:
                return json.load(fo)


@event('plugin.register')
def register_plugin():
    plugin.register(UoccinLookup, 'uoccin_lookup', api_ver=2)
