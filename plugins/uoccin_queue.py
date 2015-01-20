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
            'quality': {'type': 'string', 'format': 'quality_requirements'},
        },
        'required': ['path'],
        'additionalProperties': False
    }
    
    def on_task_output(self, task, config):
        """Add accepted series and/or movies to uoccin's watchlist"""
        
        found = {'movies': {}, 'series': {}}
        for entry in task.accepted:
            if 'imdb_id' in entry:
                found['movies'][entry['imdb_id']] = entry['movie_name']
            elif 'tvdb_id' in entry:
                found['series'][entry['tvdb_id']] = entry['series_name']
        
        if (found['movies']):
            mj = {}
            dst = os.path.join(config, 'movies.watchlist.json')
            if os.path.exists(dst):
                with open(dst, 'r') as mf:
                    mj = json.load(mf)
            n = 0
            for imdb_id in found['movies'].keys():
                if not imdb_id in mj:
                    self.log.verbose('adding movie %s (%s) to Uoccin collection' % (imdb_id, ))
                    mj[imdb_id] = { 'name': found['movies'][imdb_id] }
                    if 'quality' in config:
                        mj[imdb_id]['quality'] = config['quality']
                    n += 1
            if n > 0:
                with open(dst, 'w') as mf:
                    json.dump(mj, mf)
            self.log.info('%d movies added to Uoccin watchlist' % n)
        
        if (found['series']):
            mj = {}
            dst = os.path.join(config, 'series.watchlist.json')
            if os.path.exists(dst):
                with open(dst, 'r') as mf:
                    mj = json.load(mf)
            n = 0
            for tvdb_id in found['series'].keys():
                if not tvdb_id in mj:
                    self.log.verbose('adding series %s to Uoccin watchlist' % tvdb_id)
                    mj[tvdb_id] = config['quality'] if 'quality' in config else None
                    n += 1
            if n > 0:
                with open(dst, 'w') as mf:
                    json.dump(mj, mf)
            self.log.info('%d series added to Uoccin watchlist' % n)


@event('plugin.register')
def register_plugin():
    plugin.register(UoccinQueue, 'uoccin_queue', api_ver=2)
