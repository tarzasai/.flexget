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
            self.log.info('found %d changes in %s' % (len(lines), filename))
            self.changes.extend(lines)
        else:
            self.log.debug('no changes found in %s' % filename)
    
    def process(self):
        self.changes.sort()
        
        mw = 'movies.watchlist.json'
        mc = 'movies.collected.json'
        ms = 'movies.watched.json'
        sw = 'series.watchlist.json'
        sc = 'series.collected.json'
        ss = 'series.watched.json'
        
        udata = {mw:{}, mc:{}, ms:{}, sw:{}, sc:{}, ss:{}}
        modif = {mw:False, mc:False, ms:False, sw:False, sc:False, ss:False}
        
        for k in udata.keys():
            try:
                with open(os.path.join(self.folder, k), 'r') as f:
                    udata[k] = json.load(f)
            except Exception as err:
                self.log.info('error reading file "%s": %s' % (k, err))
                udata[k] = {}
        
        for line in self.changes:
            tmp = line.split('|')
            typ = tmp[1]
            tid = tmp[2]
            fld = tmp[3]
            val = tmp[4]
            
            if typ == 'movie':
                if fld == 'watchlist':
                    wlst = val == 'true'
                    if wlst and not udata[mw].has_key(tid):
                        udata[mw][tid] = {'name':'N/A', 'tags':[]}
                        modif[mw] = True
                    elif not wlst and udata[mw].has_key(tid):
                        udata[mw].pop(tid)
                        modif[mw] = True
                elif fld == 'tags':
                    if udata[mw].has_key(tid):
                        udata[mw][tid]['tags'] = val
                        modif[mw] = True
                elif fld == 'collected':
                    coll = val == 'true'
                    if coll and not udata[mc].has_key(tid):
                        udata[mc][tid] = []
                        modif[mc] = True
                    elif not coll and udata[mc].has_key(tid):
                        udata[mc].pop(tid)
                        modif[mc] = True
                elif fld == 'subtitles':
                    if udata[mc].has_key(tid):
                        udata[mc][tid] = re.split(',\s*', val)
                        modif[mc] = True
                elif fld == 'watched':
                    seen = val == 'true'
                    if seen and not udata[ms].has_key(tid):
                        udata[ms][tid] = {'name':'N/A', 'rating':5}
                        modif[ms] = True
                    elif not seen and udata[ms].has_key(tid):
                        udata[ms].pop(tid)
                        modif[ms] = True
                elif fld == 'rating':
                    if udata[ms].has_key(tid):
                        udata[ms][tid]['rating'] = int(val)
                        modif[ms] = True
                
            elif typ == 'series':
                tmp = tid.split('.')
                tvdb_id = tmp[0]
                season = tmp[1] if len(tmp) > 1 else None
                episode = tmp[2] if len(tmp) > 2 else None
                if fld == 'watchlist':
                    wlst = val == 'true'
                    if wlst and not udata[sw].has_key(tvdb_id):
                        udata[sw][tvdb_id] = {'name':'N/A', 'tags':[]}
                        modif[sw] = True
                    elif not wlst and udata[sw].has_key(tvdb_id):
                        udata[sw].pop(tvdb_id)
                        modif[sw] = True
                elif fld == 'tags':
                    if udata[sw].has_key(tvdb_id):
                        udata[sw][tvdb_id]['tags'] = val
                        modif[sw] = True
                elif fld == 'rating':
                    if udata[sw].has_key(tvdb_id):
                        udata[sw][tvdb_id]['rating'] = int(val)
                        modif[sw] = True
                elif season is None or episode is None:
                    self.log.info('invalid line "%s": season and episode numbers are required' % line)
                elif fld == 'collected':
                    eid = '%s.S%02dE%02d' % (tvdb_id, int(season), int(episode))
                    coll = val == 'true'
                    if coll and not udata[sc].has_key(eid):
                        udata[sc][eid] = []
                        modif[sc] = True
                    elif not coll and udata[sc].has_key(eid):
                        udata[sc].pop(eid)
                        modif[sc] = True
                elif fld == 'subtitles':
                    eid = '%s.S%02dE%02d' % (tvdb_id, int(season), int(episode))
                    if udata[sc].has_key(eid):
                        udata[sc][eid] = re.split(',\s*', val)
                        modif[sc] = True
                elif fld == 'watched':
                    if val == 'true':
                        if not udata[ss].has_key(tvdb_id):
                            udata[ss][tvdb_id] = {'name':'N/A'}
                            modif[ss] = True
                        if not udata[ss][tvdb_id].has_key(season):
                            udata[ss][tvdb_id][season] = []
                            modif[ss] = True
                        if not episode in udata[ss][tvdb_id][season]:
                            udata[ss][tvdb_id][season].append(episode)
                            udata[ss][tvdb_id][season].sort()
                            modif[ss] = True
                    elif udata[ss].has_key(tvdb_id):
                        if udata[ss][tvdb_id].has_key(season):
                            if episode in udata[ss][tvdb_id][season]:
                                udata[ss][tvdb_id][season].remove(episode)
                                modif[ss] = True
                            if not udata[ss][tvdb_id][season]:
                                udata[ss][tvdb_id].pop(season)
                                modif[ss] = True
                        if len(udata[ss][tvdb_id].keys()) < 2 and 'name' in udata[ss][tvdb_id].keys():
                            udata[ss].pop(tvdb_id)
                            modif[ss] = True
        
        for k in udata.keys():
            if modif[k]:
                try:
                    text = json.dumps(udata[k], sort_keys=True, indent=4, separators=(',', ': '))
                    with open(os.path.join(self.folder, k), 'w') as f:
                        f.write(text)
                except Exception as err:
                    self.log.info('error writing file "%s": %s' % (k, err))


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
                if fn.startswith('diff.') and not fn.endswith(config['uuid']):
                    UoccinReader.processor.load(entry['location'])
                else:
                    self.log.debug('skipping %s (not a foreign diff file)' % fn)


@event('plugin.register')
def register_plugin():
    plugin.register(UoccinReader, 'uoccin_reader', api_ver=2)
