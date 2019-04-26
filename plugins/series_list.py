from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.components.series.db import Series


log = logging.getLogger('extratorrent')


class GetSeriesList(object):
    
    schema = {"type": "boolean"}
    
    def on_task_input(self, task, config):
        """asd"""
        slist = task.session.query(Series).order_by(Series.name).all()
        entries = []
        for series in slist:
            entry = Entry()
            entry['title'] = series.name
            entry['url'] = 'http://localhost/mock/%s' % hash(entry['title'])
            if entry.isvalid():
                entries.append(entry)
            else:
                log.debug('Invalid entry created? %s' % entry)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(GetSeriesList, 'series_list', api_ver=2)
