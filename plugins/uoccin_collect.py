from __future__ import unicode_literals, division, absolute_import
import os

from flexget import plugin
from flexget.event import event
from flexget.utils import json


class UoccinCollect(object):

    schema = { 'type': 'string', 'format': 'path' }
    
    def on_task_output(self, task, config):
        """Add accepted episodes and/or movies to uoccin's collection"""
        
        found = {'movies': [], 'series': {}}
        for entry in task.accepted:
            if 'imdb_id' in entry:
                found['movies'].append(entry['imdb_id'])
            elif all(field in entry for field in ['tvdb_id', 'series_season', 'series_episode']):
                tvdb_id = str(entry['tvdb_id'])
                season = str(entry['series_season'])
                episode = entry['series_episode'] # it's int in the json array
                if not tvdb_id in found['series']:
                    found['series'][tvdb_id] = {}
                if not season in found['series'][tvdb_id]:
                    found['series'][tvdb_id][season] = []
                found['series'][tvdb_id][season].append(episode)
        
        if (found['movies']):
            mj = []
            dst = os.path.join(config, 'movies.collected.json')
            if os.path.exists(dst):
                with open(dst, 'r') as mf:
                    mj = json.load(mf)
            n = 0
            for imdb_id in found['movies']:
                if not imdb_id in mj:
                    self.log.verbose('adding movie %s to Uoccin collection' % imdb_id)
                    mj.append(imdb_id)
                    n += 1
            if n > 0:
                with open(dst, 'w') as mf:
                    json.dump(mj, mf)
            self.log.info('%d movies added to Uoccin collection' % n)
        
        if (found['series']):
            sj = {}
            dst = os.path.join(config, 'series.collected.json')
            if os.path.exists(dst):
                with open(dst, 'r') as sf:
                    sj = json.load(sf)
            n = 0
            for tvdb_id in found['series']:
                if not tvdb_id in sj:
                    sj[tvdb_id] = {}
                for season in found['series'][tvdb_id]:
                    if not season in sj[tvdb_id]:
                        sj[tvdb_id][season] = []
                    for episode in found['series'][tvdb_id][season]:
                        if not episode in sj[tvdb_id][season]:
                            self.log.verbose('adding series %s, episode S%02dE%02d to Uoccin collection' % 
                                (tvdb_id, season, episode))
                            sj[tvdb_id][season].append(episode)
                            n += 1
                    sj[tvdb_id][season].sort()
            if n > 0:
                with open(dst, 'w') as sf:
                    json.dump(sj, sf)
            self.log.info('%d episodes added to Uoccin collection' % n)


@event('plugin.register')
def register_plugin():
    plugin.register(UoccinCollect, 'uoccin_collect', api_ver=2)
