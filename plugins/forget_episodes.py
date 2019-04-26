from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.components.series.db import remove_series_entity

log = logging.getLogger('forget_episodes')


class ForgetEpisodes(object):
    """
    Forget the given episode for series. Uses series_name and series_id.
    
    Example::

      forget_episodes: yes
    
    """
    
    schema = {'type': 'boolean'}
    
    def on_task_output(self, task, config):
        if not (config and task.accepted):
            return
        for entry in task.accepted:
            if entry.get('series_name') and entry.get('series_id'):
                snm = entry['series_name']
                sid = entry['series_id']
                try:
                    log.info('Removing episode %s references from "%s"' % (sid, snm))
                    remove_series_entity(snm, sid)
                except ValueError as e:
                    log.error('An error occurred: %s' % e)


@event('plugin.register')
def register_plugin():
    plugin.register(ForgetEpisodes, 'forget_episodes', api_ver=2)
