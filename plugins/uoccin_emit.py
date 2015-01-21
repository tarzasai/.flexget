from __future__ import unicode_literals, division, absolute_import
import os

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import json


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
        src = os.path.join(config['path'], config['type'] + '.watchlist.json')
        if not os.path.exists(src):
            self.log.warning('Uoccin %s watchlist not found.' % config['type'])
            return
        with open(src, 'r') as f:
            data = json.load(f)
        entries = []
        for eid, itm in data.items():
            if 'tags' in config:
                if not 'tags' in itm:
                    self.log.debug('No tags in watchlist item, skipping %s' % itm['name'])
                    continue
                n = len(set(config['tags']) & set(itm['tags']))
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
            if 'quality' in itm:
                entry['uoccin_quality'] = itm['quality']
            if entry.isvalid():
                entries.append(entry)
            else:
                self.log.debug('Invalid entry created? %s' % entry)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(UoccinEmit, 'uoccin_emit', api_ver=2)
