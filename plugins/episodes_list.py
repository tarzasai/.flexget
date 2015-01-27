from __future__ import unicode_literals, division, absolute_import

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.plugins.filter.series import Series, Episode, SeriesTask, normalize_series_name

from sqlalchemy import func


class GetEpisodesList(object):
    
    schema = {
        "oneOf": [
            {"type": "boolean"},
            {"type": "string"}
        ]
    }
    
    def on_task_input(self, task, config):
        """asd"""
        slist = task.session.query(Series)
        if isinstance(config, basestring):
            name = normalize_series_name(config)
            slist = slist.filter(Series._name_normalized.contains(name))
        slist = (slist.outerjoin(Series.episodes).outerjoin(Episode.releases).outerjoin(Series.in_tasks).
                 # group_by(Series.id).having(func.count(SeriesTask.id) < 1).order_by(Series.name).all())
                 # group_by(Series.id).having(func.count(SeriesTask.id) >= 1).order_by(Series.name).all())
                 order_by(Series.name).all())
        entries = []
        for series in slist:
            elist = (task.session.query(Episode).filter(Episode.series_id == series.id).
                     order_by(Episode.season, Episode.number).all())
            for episode in elist:
                self.log.debug('Found episode %s for series "%s"' % (episode.identifier, series.name))
                entry = Entry()
                entry['title'] = '%s %s' % (series.name, episode.identifier)
                entry['url'] = 'http://localhost/mock/%s' % hash(entry['title'])
                if entry.isvalid():
                    entries.append(entry)
                else:
                    self.log.debug('Invalid entry created? %s' % entry)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(GetEpisodesList, 'episodes_list', api_ver=2)
