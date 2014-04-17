from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('no_cache')


class NoInputCache(object):

    schema = {'type': 'boolean'}
    
    enable_on_exit = False

    @plugin.priority(255)
    def on_task_start(self, task, config):
        if config:
            self.enable_on_exit = not task.options.nocache
            task.options.nocache = True
            log.verbose('Input cache disabled')

    @plugin.priority(-255)
    def on_task_exit(self, task, config):
        if config and self.enable_on_exit:
            task.options.nocache = False
            log.verbose('Input cache re-enabled')


@event('plugin.register')
def register_plugin():
    plugin.register(NoInputCache, 'no_cache', api_ver=2)