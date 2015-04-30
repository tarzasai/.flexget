from __future__ import unicode_literals, division, absolute_import
from datetime import datetime
import logging
import os
import re

from flexget import plugin
from flexget.event import event
from flexget.utils import json


class UoccinProcess(object):
    
    def __init__(self):
        self.reset(None)
    
    def reset(self, folder):
        self.log = logging.getLogger('uoccin_process')
        self.folder = folder
        self.changes = []
    
    def load(self, filename):
        with open(filename, 'r') as f:
            lines = f.read().splitlines()
        if lines:
            lines = [l for l in lines if not l.startswith(';')] # just for debug
        if lines:
            self.log.info('found %d changes in %s' % (len(lines), filename))
            self.changes.extend(lines)
        else:
            self.log.debug('no changes found in %s' % filename)
    
    def process(self):
        self.changes.sort()
        
        udata = {}
        ufile = os.path.join(self.folder, 'uoccin.json')
        if os.path.exists(ufile):
            try:
                self.log.verbose('loading file %s' % ufile)
                with open(ufile, 'r') as f:
                    udata = json.load(f)
            except Exception as err:
                self.log.debug('error reading %s: %s' % (ufile, err))
                raise plugin.PluginError('error reading %s: %s' % (ufile, err))
        udata.setdefault('movies', {})
        udata.setdefault('series', {})
        
        for line in self.changes:
            tmp = line.split('|')
            typ = tmp[1]
            tid = tmp[2]
            fld = tmp[3]
            val = tmp[4]
            self.log.verbose('processing: type=%s, target=%s, field=%s, value=%s' % (typ, tid, fld, val))
            
            if typ == 'movie':
                # default
                mov = udata['movies'].setdefault(tid, 
                    {'name':'N/A', 'watchlist':False, 'collected':False, 'watched':False})
                # setting
                if fld == 'watchlist':
                    mov['watchlist'] = val == 'true'
                elif fld == 'collected':
                    mov['collected'] = val == 'true'
                elif fld == 'watched':
                    mov['watched'] = val == 'true'
                elif fld == 'tags':
                    mov['tags'] = re.split(',\s*', val)
                elif fld == 'subtitles':
                    mov['subtitles'] = re.split(',\s*', val)
                elif fld == 'rating':
                    mov['rating'] = int(val)
                # cleaning
                if not (mov['watchlist'] or mov['collected'] or mov['watched']):
                    self.log.verbose('deleting unused section: movies\%s' % tid)
                    udata['movies'].pop(tid)
                
            elif typ == 'series':
                tmp = tid.split('.')
                sid = tmp[0]
                sno = tmp[1] if len(tmp) > 2 else None
                eno = tmp[2] if len(tmp) > 2 else None
                # default
                ser = udata['series'].setdefault(sid, 
                    {'name':'N/A', 'watchlist':False, 'collected':{}, 'watched':{}})
                # setting
                if fld == 'watchlist':
                    ser['watchlist'] = val == 'true'
                elif fld == 'tags':
                    ser['tags'] = re.split(',\s*', val)
                elif fld == 'rating':
                    ser['rating'] = int(val)
                elif sno is None or eno is None:
                    self.log.warning('invalid line "%s": season and episode numbers are required' % line)
                elif fld == 'collected':
                    season = ser['collected'].setdefault(sno, {})
                    if val == 'true':
                        season.setdefault(eno, [])
                    elif eno in season:
                        season.pop(eno)
                        if not season:
                            self.log.verbose('deleting unused section: series\%s\collected\%s' % (sid, sno))
                            ser['collected'].pop(season)
                elif fld == 'subtitles':
                    ser['collected'].setdefault(sno, {})[eno] = re.split(',\s*', val)
                elif fld == 'watched':
                    season = ser['watched'].setdefault(sno, [])
                    if val == 'true':
                        season = ser['watched'][sno] = list(set(season) | set([int(eno)]))
                    elif eno in season:
                        season.remove(int(eno))
                    season.sort()
                    if not season:
                        self.log.verbose('deleting unused section: series\%s\watched\%s' % (sid, sno))
                        ser['watched'].pop(season)
                # cleaning
                if not (ser['watchlist'] or ser['collected'] or ser['watched']):
                    self.log.verbose('deleting unused section: series\%s' % sid)
                    udata['series'].pop(sid)
                
            else:
                self.log.warning('invalid element type "%s"' % typ)
        
        try:
            self.log.verbose('saving file %s' % ufile)
            text = json.dumps(udata, sort_keys=True, indent=4, separators=(',', ': '))
            with open(ufile, 'w') as f:
                f.write(text)
        except Exception as err:
            self.log.debug('error writing %s: %s' % (ufile, err))
            raise plugin.PluginError('error writing %s: %s' % (ufile, err))


class UoccinReader(object):
    
    schema = {
        'type': 'object',
        'properties': {
            'uuid': {'type': 'string'},
            'path': {'type': 'string', 'format': 'path'},
        },
        'required': ['uuid', 'path'],
        'additionalProperties': False
    }
    
    processor = UoccinProcess()
    
    def on_task_start(self, task, config):
        UoccinReader.processor.reset(config['path'])

    def on_task_exit(self, task, config):
        UoccinReader.processor.process()
    
    def on_task_output(self, task, config):
        for entry in task.accepted:
            if entry.get('location'):
                fn = os.path.basename(entry['location'])
                if fn.endswith('.diff') and not (config['uuid'] in fn):
                    UoccinReader.processor.load(entry['location'])
                else:
                    self.log.debug('skipping %s (not a foreign diff file)' % fn)


class UoccinWriter(object):
    
    uoccin_queue_out = ''
    
    def on_task_start(self, task, config):
        ts = int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds() * 1000)
        fn = '%d.%s.diff' % (ts, config['uuid'])
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
                self.append_command(typ, tid, 'subtitles', ",".join(entry['subtitles']))


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


class UoccinLookup(object):

    schema = { 'type': 'string', 'format': 'path' }
    
    # Run after metainfo_series / thetvdb_lookup / imdb_lookup
    @plugin.priority(100)
    def on_task_metainfo(self, task, config):
        if not task.entries:
            return
        udata = {}
        ufile = os.path.join(config, 'uoccin.json')
        if os.path.exists(ufile):
            try:
                self.log.verbose('loading file %s' % ufile)
                with open(ufile, 'r') as f:
                    udata = json.load(f)
            except Exception as err:
                self.log.debug('error reading %s: %s' % (ufile, err))
                raise plugin.PluginError('error reading %s: %s' % (ufile, err))
        movies = udata.setdefault('movies', {})
        series = udata.setdefault('series', {})
        if not (movies or series):
            return
        for entry in task.entries:
            entry['uoccin_watchlist'] = False
            entry['uoccin_collected'] = False
            entry['uoccin_watched'] = False
            entry['uoccin_rating'] = None
            entry['uoccin_tags'] = []
            entry['uoccin_subtitles'] = []
            if 'tvdb_id' in entry and series:
                ser = series.setdefault(str(entry['tvdb_id']), {})
                entry['uoccin_watchlist'] = ser.get('watchlist', False)
                entry['uoccin_rating'] = ser.get('rating')
                entry['uoccin_tags'] = ser.get('tags', [])
                if all(field in entry for field in ['series_season', 'series_episode']):
                    season = str(entry['series_season'])
                    episode = entry['series_episode']
                    edata = ser.get('collected', {}).get(season, {}).get(str(episode))
                    entry['uoccin_collected'] = isinstance(edata, list)
                    entry['uoccin_subtitles'] = edata if entry['uoccin_collected'] else []
                    entry['uoccin_watched'] = episode in ser.get('watched', {}).get(season, [])
            elif 'imdb_id' in entry and movies:
                mov = movies.setdefault(str(entry['imdb_id']), {})
                entry['uoccin_watchlist'] = mov.get('watchlist', False)
                entry['uoccin_collected'] = mov.get('collected', False)
                entry['uoccin_watched'] = mov.get('watched', False)
                entry['uoccin_rating'] = mov.get('rating')
                entry['uoccin_tags'] = mov.get('tags', [])
                entry['uoccin_subtitles'] = mov.get('tags', [])


@event('plugin.register')
def register_plugin():
    plugin.register(UoccinReader, 'uoccin_reader', api_ver=2)
    plugin.register(UoccinWlstAdd, 'uoccin_watchlist_add', api_ver=2)
    plugin.register(UoccinWlstDel, 'uoccin_watchlist_remove', api_ver=2)
    plugin.register(UoccinCollAdd, 'uoccin_collection_add', api_ver=2)
    plugin.register(UoccinCollDel, 'uoccin_collection_remove', api_ver=2)
    plugin.register(UoccinSeenAdd, 'uoccin_watched_true', api_ver=2)
    plugin.register(UoccinSeenDel, 'uoccin_watched_false', api_ver=2)
    # plugin.register(UoccinLookup, 'uoccin_lookup', api_ver=2)
