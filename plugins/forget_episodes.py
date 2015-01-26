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
                fshow = task.session.query(Series).filter(Series.name == entry['series_name']).first()
                if not fshow:
                    self.log.info('Series "%s" not found, skipping' % (entry['series_name']))
                    continue
                try:
                    forget_series_episode(fshow, entry['series_id'])
                except ValueError as e:
                    self.log.error('An error occurred trying to set forget for %s: %s' % (entry['series_name'], e))
                self.log.info('Removed %s episode references from "%s"' % (entry['series_id'], entry['series_name']))


@event('plugin.register')
def register_plugin():
    plugin.register(ForgetEpisodes, 'forget_episodes', api_ver=2)
