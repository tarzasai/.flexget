from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event
from flexget.plugins.filter.series import Series, forget_series_episode

log = logging.getLogger('set_series_forget')


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
                    self.log.info('Removing episode %s references from "%s"...' % (sid, snm))
                    forget_series_episode(snm, sid)
                except ValueError as e:
                    self.log.error('An error occurred: %s' % e)


@event('plugin.register')
def register_plugin():
    plugin.register(ForgetEpisodes, 'forget_episodes', api_ver=2)
