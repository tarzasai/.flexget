from __future__ import unicode_literals, division, absolute_import
from datetime import datetime
import os

from flexget import plugin
from flexget.event import event
from flexget.plugins.local.uoccin_reader import UoccinProcess


class UoccinWriter(object):
    
    uoccin_queue_out = ''
    
    def on_task_start(self, task, config):
        ts = int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds() * 1000)
        fn = 'diff.%d.%s' % (ts, config['uuid'])
        UoccinWriter.uoccin_queue_out = os.path.join(config['path'], fn)

    def on_task_exit(self, task, config):
        if os.path.exists(UoccinWriter.uoccin_queue_out):
            up = UoccinProcess()
            up.reset(config['path'])
            up.load(UoccinWriter.uoccin_queue_out)
            up.process()
    
    def append_command(self, target, title, field, value):
        ts = int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds() * 1000)
        line = '%d|%s|%s|%s|%s\n' % (ts, target, title, field, value)
        with open(UoccinWriter.uoccin_queue_out, 'a') as f:
            f.write(line)


class UoccinWatchlist(UoccinWriter):
    
    # Defined by subclasses
    set_true = None
    
    def on_task_output(self, task, config):
        """Add accepted series and/or movies to uoccin's watchlist"""
        for entry in task.accepted:
            tid = None
            typ = None
            if entry.get('tvdb_id'):
                tid = entry['tvdb_id']
                typ = 'series'
            elif entry.get('imdb_id'):
                tid = entry['imdb_id']
                typ = 'movie'
            if tid is None:
                continue
            self.append_command(typ, tid, 'watchlist', str(self.set_true).lower())
            if self.set_true:
                self.append_command(typ, tid, 'tags', ",".join(config['tags']))


class UoccinWlstAdd(UoccinWatchlist):
    """Add all accepted series/movies to Uoccin watchlist."""
    schema = {
        'type': 'object',
        'properties': {
            'uuid': {'type': 'string'},
            'path': {'type': 'string', 'format': 'path'},
            'tags': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1},
        },
        'required': ['uuid', 'path'],
        'additionalProperties': False
    }
    set_true = True


class UoccinWlstDel(UoccinWatchlist):
    """Remove all accepted elements from Uoccin watchlist."""
    schema = {
        'type': 'object',
        'properties': {
            'uuid': {'type': 'string'},
            'path': {'type': 'string', 'format': 'path'},
        },
        'required': ['uuid', 'path'],
        'additionalProperties': False
    }
    set_true = False


class UoccinCollection(UoccinWriter):

    schema = {
        'type': 'object',
        'properties': {
            'uuid': {'type': 'string'},
            'path': {'type': 'string', 'format': 'path'},
        },
        'required': ['uuid', 'path'],
        'additionalProperties': False
    }
    
    # Defined by subclasses
    set_true = None
    
    def on_task_output(self, task, config):
        """Add accepted episodes and/or movies to uoccin's collection"""
        for entry in task.accepted:
            tid = None
            typ = None
            if all(field in entry for field in ['tvdb_id', 'series_season', 'series_episode']):
                tid = '%s.%d.%d' % (entry['tvdb_id'], entry['series_season'], entry['series_episode'])
                typ = 'series'
            elif entry.get('imdb_id'):
                tid = entry['imdb_id']
                typ = 'movie'
            if tid is None:
                continue
            self.append_command(typ, tid, 'collected', str(self.set_true).lower())
            if self.set_true and 'subtitles' in entry:
                self.append_command(typ, tid, 'subtitles', ",".join(config['subtitles']))


class UoccinCollAdd(UoccinCollection):
    """Add/update all accepted elements in uoccin collection."""
    set_true = True


class UoccinCollDel(UoccinCollection):
    """Remove all accepted elements from uoccin collection."""
    set_true = False


class UoccinWatched(UoccinWriter):

    schema = {
        'type': 'object',
        'properties': {
            'uuid': {'type': 'string'},
            'path': {'type': 'string', 'format': 'path'},
        },
        'required': ['uuid', 'path'],
        'additionalProperties': False
    }
    
    # Defined by subclasses
    set_true = None
    
    def on_task_output(self, task, config):
        """Add accepted episodes and/or movies to uoccin's watched list"""
        for entry in task.accepted:
            tid = None
            typ = None
            if all(field in entry for field in ['tvdb_id', 'series_season', 'series_episode']):
                tid = '%s.%d.%d' % (entry['tvdb_id'], entry['series_season'], entry['series_episode'])
                typ = 'series'
            elif entry.get('imdb_id'):
                tid = entry['imdb_id']
                typ = 'movie'
            if tid is None:
                continue
            self.append_command(typ, tid, 'watched', str(self.set_true).lower())


class UoccinSeenAdd(UoccinWatched):
    """Set all accepted elements as watched."""
    set_true = True


class UoccinSeenDel(UoccinWatched):
    """Set all accepted elements as not watched."""
    set_true = False


@event('plugin.register')
def register_plugin():
    plugin.register(UoccinWlstAdd, 'uoccin_watchlist_add', api_ver=2)
    plugin.register(UoccinWlstDel, 'uoccin_watchlist_remove', api_ver=2)
    plugin.register(UoccinCollAdd, 'uoccin_collection_add', api_ver=2)
    plugin.register(UoccinCollDel, 'uoccin_collection_remove', api_ver=2)
    plugin.register(UoccinSeenAdd, 'uoccin_watched_true', api_ver=2)
    plugin.register(UoccinSeenDel, 'uoccin_watched_false', api_ver=2)
