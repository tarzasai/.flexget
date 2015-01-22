from __future__ import unicode_literals, division, absolute_import
import os

from flexget import plugin
from flexget.event import event
from flexget.utils import json


class UoccinCollection(object):

    schema = { 'type': 'string', 'format': 'path' }
    
    # Defined by subclasses
    acquire = None
    
    def on_task_output(self, task, config):
        """Add accepted episodes and/or movies to uoccin's collection"""
        series = {}
        movies = {}
        for entry in task.accepted:
            if all(field in entry for field in ['tvdb_id', 'series_season', 'series_episode']):
                eid = '%s.S%02dE%02d' % (entry['tvdb_id'], entry['series_season'], entry['series_episode'])
                if not eid in series: # we can have more than one (different release/quality)
                    series[eid] = {'name': entry.get('tvdb_series_name', entry['series_name'])}
                if self.acquire and 'subtitles' in entry:
                    subs = series[eid]['subtitles'] if 'subtitles' in series[eid] else []
                    series[eid]['subtitles'] = list(set(subs + entry['subtitles']))
            elif all(field in entry for field in ['imdb_id', 'movie_name']):
                eid = entry['imdb_id']
                if not eid in movies: # we can have more than one (different release/quality)
                    movies[eid] = {'name': entry.get('imdb_name', entry['movie_name'])}
                if self.acquire and 'subtitles' in entry:
                    subs = movies[eid]['subtitles'] if 'subtitles' in movies[eid] else []
                    movies[eid]['subtitles'] = list(set(subs + entry['subtitles']))
        if series:
            dest = os.path.join(config, 'series.collected.json')
            data = {}
            if os.path.exists(dest):
                with open(dest, 'r') as f:
                    data = json.load(f)
            for eid in series:
                if self.acquire:
                    self.log.verbose('adding/updating episode %s to Uoccin collection' % eid)
                    data[eid] = series[eid]
                else:
                    self.log.verbose('removing episode %s from Uoccin collection' % eid)
                    data.pop(eid)
            text = json.dumps(data, sort_keys=True, indent=4, separators=(',', ': '))
            with open(dest, 'w') as f:
                f.write(text)
            self.log.info('Uoccin episodes collection updated')
        if movies:
            dest = os.path.join(config, 'movies.collected.json')
            data = {}
            if os.path.exists(dest):
                with open(dest, 'r') as f:
                    data = json.load(f)
            for eid in movies:
                if self.acquire:
                    self.log.verbose('adding/updating movie %s to Uoccin collection' % eid)
                    data[eid] = movies[eid]
                else:
                    self.log.verbose('removing movie %s from Uoccin collection' % eid)
                    data.pop(eid)
            text = json.dumps(data, sort_keys=True, indent=4, separators=(',', ': '))
            with open(dest, 'w') as f:
                f.write(text)
            self.log.info('Uoccin movies collection updated')


class UoccinAcquire(UoccinCollection):
    """Add/update all accepted elements in your uoccin collection."""
    acquire = True


class UoccinForget(UoccinCollection):
    """Remove all accepted elements from your uoccin collection."""
    acquire = False


@event('plugin.register')
def register_plugin():
    plugin.register(UoccinAcquire, 'uoccin_acquire', api_ver=2)
    plugin.register(UoccinForget, 'uoccin_forget', api_ver=2)
