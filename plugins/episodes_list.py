from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event
from flexget.plugins.filter.series import Series, Episode, SeriesTask

from sqlalchemy import func


class GetEpisodesList(object):
    
    schema = {'type': 'boolean'}
    
    def on_task_input(self, task, config):
        """asd"""
        entries = []
        
        slist = (task.session.query(Series).outerjoin(Series.episodes).outerjoin(Episode.releases).
                 outerjoin(Series.in_tasks).group_by(Series.id).having(func.count(SeriesTask.id) >= 1).
                 order_by(Series.name))
        
        for series in slist:
            
            elist = (task.session.query(Episode).filter(Episode.series_id == series.id).
                     order_by(Episode.season, Episode.number).all())
            
        
        
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(GetEpisodesList, 'episodes_list', api_ver=2)
