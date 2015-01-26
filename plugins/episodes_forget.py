from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event
from flexget.plugins.filter.series import Series, forget_series_episode, get_latest_episode

log = logging.getLogger('set_series_forget')


class ForgetEpisodes(object):
    """
    Forget the given episode for series. Uses series_name and series_id.
    
    Example::

      forget_episodes: single
    
    """
    
    schema = {'type': 'string', 'enum': ['single', 'from'], 'default': 'single'}
    
    def on_task_output(self, task, config):
        if not task.accepted:
            return
        for entry in task.accepted:
            if not (entry.get('series_name') and entry.get('series_id')):
                continue
            if config == 'single':
                try:
                    forget_series_episode(entry['series_name'], entry['series_id'])
                except ValueError as e:
                    self.log.error('An error occurred trying to forget for %s: %s' % (entry['series_name'], e))
                self.log.info('Removed %s episode references from "%s"' % (entry['series_id'], entry['series_name']))
            else:
                fshow = task.session.query(Series).filter(Series.name == entry['series_name']).first()
                '''
                if not fshow:
                    self.log.info('Series %s not found, skipping' % entry['series_name'])
                    continue
                known = get_latest_episode(fshow)
                if not known:
                    self.log.info('Series %s last episode not found, skipping' % entry['series_name'])
                    continue
                
                real_season = entry['series_season']
                real_episode = entry['series_episode']
                
                del_list = []
                
                if known.season > real_season:
                    
                    for n in range(known.season, real_season, -1):
                        
                
                
                if known.season > real_season or (known.season == real_season and known.episode > real_episode):
                    
                    
                
                
                fepid = 'S%02dE%02d' % (known.season, known.episode)
                '''


@event('plugin.register')
def register_plugin():
    plugin.register(ForgetEpisodes, 'forget_episodes', api_ver=2)
