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
        squeu = self.get_json(config, 'series.watchlist.json')
        sseen = self.get_json(config, 'series.watched.json')
        scoll = self.get_json(config, 'series.collected.json')
        mqueu = self.get_json(config, 'movies.watchlist.json')
        mseen = self.get_json(config, 'movies.watched.json')
        mcoll = self.get_json(config, 'movies.collected.json')
        if not (mqueu or mcoll or mseen or squeu or scoll or sseen):
            return
        for entry in task.entries:
            if 'tvdb_id' in entry:
                sid = str(entry['tvdb_id'])
                entry['uoccin_queued'] = sid in squeu
                if all(field in entry for field in ['series_season', 'series_episode']):
                    sno = str(entry['series_season'])
                    eno = entry['series_episode']
                    entry['uoccin_watched'] = sid in sseen and sno in sseen[sid] and eno in sseen[sid][sno]
                    entry['uoccin_collected'] = ('%s.S%02dE%02d' % (sid, entry['series_season'], eno)) in scoll
                else:
                    entry['uoccin_watched'] = False
                    entry['uoccin_collected'] = False
                entry['uoccin_rating'] = -1  # ???
            elif 'imdb_id' in entry:
                eid = entry['imdb_id']
                entry['uoccin_queued'] = eid in mqueu
                entry['uoccin_collected'] = eid in mcoll
                if eid in mseen:
                    entry['uoccin_watched'] = True
                    entry['uoccin_rating'] = mseen[eid].get('rating', -1)
                else:
                    entry['uoccin_watched'] = False
                    entry['uoccin_rating'] = -1
    
    def get_json(self, config, filename):
        fn = os.path.join(config, filename)
        if os.path.exists(fn):
            with open(fn, 'r') as f:
                return json.load(f)
        return {}


@event('plugin.register')
def register_plugin():
    plugin.register(UoccinLookup, 'uoccin_lookup', api_ver=2)
