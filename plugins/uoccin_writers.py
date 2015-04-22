from __future__ import unicode_literals, division, absolute_import
from datetime import datetime
import logging
import uuid
import os

from flexget import plugin
from flexget.event import event
from flexget.utils import json


class UoccinWriter(object):
    
    uoccin_queue_out = ''
    
    def on_task_start(self, task, config):
        UoccinWriter.uoccin_queue_out = 'dump.%s.%s' % (datetime.now().strftime('%Y%m%d%H%M%S'), str(uuid.uuid1()))
    
    def append_command(self, path, target, title, field, value):
        ts = int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds() * 1000)
        line = '%d|%s|%s|%s|%s' % (ts, target, title, field, value)
        with open(os.path.join(path, UoccinWriter.uoccin_queue_out), 'a') as f:
            f.writeline(line)


class UoccinCollection(UoccinWriter):

    schema = { 'type': 'string', 'format': 'path' }
    
    # Defined by subclasses
    acquire = None
    
    def on_task_output(self, task, config):
        """Add accepted episodes and/or movies to uoccin's collection"""
        for entry in task.accepted:
            if all(field in entry for field in ['tvdb_id', 'series_season', 'series_episode']):
                eid = '%s.%d.%d' % (entry['tvdb_id'], entry['series_season'], entry['series_episode'])
                self.append_command(config, 'series', eid, 'collected', str(self.acquire).lower())
                if self.acquire and 'subtitles' in entry:
                    self.append_command(config, 'series', eid, 'subtitles', entry['subtitles'])
            elif all(field in entry for field in ['imdb_id', 'movie_name']):
                self.append_command(config, 'movie', entry['imdb_id'], 'collected', str(self.acquire).lower())
                if self.acquire and 'subtitles' in entry:
                    self.append_command(config, 'movie', entry['imdb_id'], 'subtitles', entry['subtitles'])


class UoccinAcquire(UoccinCollection):
    """Add/update all accepted elements in your uoccin collection."""
    acquire = True


class UoccinForget(UoccinCollection):
    """Remove all accepted elements from your uoccin collection."""
    acquire = False


class UoccinWatched(UoccinWriter):

    schema = { 'type': 'string', 'format': 'path' }
    
    def on_task_output(self, task, config):
        """Add accepted episodes and/or movies to uoccin's watched list"""
        for entry in task.accepted:
            if all(field in entry for field in ['tvdb_id', 'series_name', 'series_season', 'series_episode']):
                eid = '%s.%d.%d' % (entry['tvdb_id'], entry['series_season'], entry['series_episode'])
                self.append_command(config, 'series', eid, 'watched', 'true')
            elif all(field in entry for field in ['imdb_id', 'movie_name']):
                self.append_command(config, 'movie', entry['imdb_id'], 'watched', 'true')


class UoccinWatchlist(UoccinWriter):
    
    # Defined by subclasses
    remove = None
    
    def on_task_output(self, task, config):
        """Add accepted series and/or movies to uoccin's watchlist"""
        for entry in task.accepted:
            if all(field in entry for field in ['tvdb_id', 'series_name']):
                self.append_command(config, 'series', entry['tvdb_id'], 'watchlist', str(not self.remove).lower())
            elif all(field in entry for field in ['imdb_id', 'movie_name']):
                self.append_command(config, 'movie', entry['imdb_id'], 'watchlist', str(not self.remove).lower())
            # tags!


class UoccinQueue(UoccinWatchlist):
    """Add all accepted series/movies to Uoccin watchlist."""
    schema = {
        'type': 'object',
        'properties': {
            'path': {'type': 'string', 'format': 'path'},
            'tags': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1},
        },
        'required': ['path'],
        'additionalProperties': False
    }
    remove = False


class UoccinUnqueue(UoccinWatchlist):
    """Remove all accepted elements from Uoccin watchlist."""
    schema = { 'type': 'string', 'format': 'path' }
    remove = True


'''
@event('plugin.register')
def register_plugin():
    plugin.register(UoccinQueue, 'uoccin_queue', api_ver=2)
    plugin.register(UoccinUnqueue, 'uoccin_unqueue', api_ver=2)
    plugin.register(UoccinAcquire, 'uoccin_acquire', api_ver=2)
    plugin.register(UoccinForget, 'uoccin_forget', api_ver=2)
    plugin.register(UoccinWatched, 'uoccin_watched', api_ver=2)
'''
