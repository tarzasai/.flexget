from __future__ import unicode_literals, division, absolute_import
from datetime import datetime
import logging
import os
import re
import shutil

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import json


def load_uoccin_data(path):
    udata = {}
    ufile = os.path.join(path, 'uoccin.json')
    if os.path.exists(ufile):
        try:
            with open(ufile, 'r') as f:
                udata = json.load(f)
        except Exception as err:
            raise plugin.PluginError('error reading %s: %s' % (ufile, err))
    udata.setdefault('movies', {})
    udata.setdefault('series', {})
    return udata


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
            self.log.info('found %d changes in %s' % (len(lines), filename))
            self.changes.extend(lines)
        else:
            self.log.debug('no changes found in %s' % filename)
    
    def process(self):
        self.changes.sort()
        udata = load_uoccin_data(self.folder)
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
                            ser['collected'].pop(sno)
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
                        self.log.debug('deleting unused section: series\%s\watched\%s' % (sid, sno))
                        ser['watched'].pop(sno)
                # cleaning
                if not (ser['watchlist'] or ser['collected'] or ser['watched']):
                    self.log.debug('deleting unused section: series\%s' % sid)
                    udata['series'].pop(sid)
            else:
                self.log.warning('invalid element type "%s"' % typ)
        ufile = os.path.join(self.folder, 'uoccin.json')
        try:
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
                    os.remove(entry['location'])
                else:
                    self.log.debug('skipping %s (not a foreign diff file)' % fn)


class UoccinWriter(object):
    
    out_queue = ''
    my_folder = None
    others_folders = None
    
    def on_task_start(self, task, config):
        UoccinWriter.my_folder = os.path.join(config['path'], 'device.' + config['uuid'])
        if not os.path.exists(UoccinWriter.my_folder):
            os.makedirs(UoccinWriter.my_folder)
        
        ts = int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds() * 1000)
        fn = '%d.%s.diff' % (ts, config['uuid'])
        UoccinWriter.out_queue = os.path.join(UoccinWriter.my_folder, fn)
        
        UoccinWriter.others_folders = []
        for fld in next(os.walk(config['path']))[1]:
            if fld.startswith('device.') and fld != ('device.' + config['uuid']):
                UoccinWriter.others_folders.append(os.path.join(config['path'], fld))
    
    def on_task_exit(self, task, config):
        if os.path.exists(UoccinWriter.out_queue):
            # update the backup file (uoccin.json)
            up = UoccinProcess()
            up.reset(config['path'])
            up.load(UoccinWriter.out_queue)
            up.process()
            # forward the diff file in other devices folders
            for fld in UoccinWriter.others_folders:
                shutil.copy2(UoccinWriter.out_queue, fld)
                self.log.verbose('%s copied in %s' % (UoccinWriter.out_queue, fld))
            # delete the local diff file
            os.remove(UoccinWriter.out_queue)
    
    def append_command(self, target, title, field, value):
        ts = int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds() * 1000)
        line = '%d|%s|%s|%s|%s\n' % (ts, target, title, field, value)
        with open(UoccinWriter.out_queue, 'a') as f:
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


class UoccinEmit(object):

    schema = {
        'type': 'object',
        'properties': {
            'path': {'type': 'string', 'format': 'path'},
            'type': {'type': 'string', 'enum': ['series', 'movies']},
            'tags': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1},
            'check_tags': {'type': 'string', 'enum': ['any', 'all', 'none'], 'default': 'any'},
        },
        'required': ['path', 'type'],
        'additionalProperties': False
    }
    
    def on_task_input(self, task, config):
        """asd"""
        udata = load_uoccin_data(config['path'])
        section = udata['movies'] if config['type'] == 'movies' else udata['series']
        entries = []
        for eid, itm in section.items():
            if not itm['watchlist']:
                continue
            if 'tags' in config:
                n = len(set(config['tags']) & set(itm.get('tags', [])))
                if config['check_tags'] == 'any' and n <= 0:
                    continue
                if config['check_tags'] == 'all' and n != len(config['tags']):
                    continue
                if config['check_tags'] == 'none' and n > 0:
                    continue
            entry = Entry()
            entry['title'] = itm['name']
            if config['type'] == 'movies':
                entry['url'] = 'http://www.imdb.com/title/' + eid
                entry['imdb_id'] = eid
            else:
                entry['url'] = 'http://thetvdb.com/?tab=series&id=' + eid
                entry['tvdb_id'] = eid
            if 'tags' in itm:
                entry['uoccin_tags'] = itm['tags']
            if entry.isvalid():
                entries.append(entry)
            else:
                self.log.debug('Invalid entry created? %s' % entry)
        return entries


class UoccinLookup(object):

    schema = { 'type': 'string', 'format': 'path' }
    
    # Run after metainfo_series / thetvdb_lookup / imdb_lookup
    @plugin.priority(100)
    def on_task_metainfo(self, task, config):
        if not task.entries:
            return
        udata = load_uoccin_data(config)
        movies = udata['movies']
        series = udata['series']
        for entry in task.entries:
            entry['uoccin_watchlist'] = False
            entry['uoccin_collected'] = False
            entry['uoccin_watched'] = False
            entry['uoccin_rating'] = None
            entry['uoccin_tags'] = []
            entry['uoccin_subtitles'] = []
            if 'tvdb_id' in entry:
                ser = series.get(str(entry['tvdb_id']))
                if ser is None:
                    continue
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
            elif 'imdb_id' in entry:
                mov = movies.get(entry['imdb_id'])
                if mov is None:
                    continue
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
    plugin.register(UoccinEmit, 'uoccin_emit', api_ver=2)
    plugin.register(UoccinLookup, 'uoccin_lookup', api_ver=2)
