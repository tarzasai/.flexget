from __future__ import unicode_literals, division, absolute_import
import os
import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('require_file')


class RequireFile(object):
    """
    """
    
    schema = {'type': 'boolean'}
    
    def on_task_filter(self, task, config):
        if not config:
            return
        for entry in task.accepted:
            if not 'location' in entry or not os.path.exists(entry['location']):
                entry.reject('file not found "%s"' % entry.get('location', 'Undefined'))


@event('plugin.register')
def register_plugin():
    plugin.register(RequireFile, 'require_file', api_ver=2)
