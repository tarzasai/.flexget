from __future__ import unicode_literals, division, absolute_import
import os

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event


class GetSeriesLast(object):
    pass


@event('plugin.register')
def register_plugin():
    plugin.register(GetSeriesLast, 'series_last', api_ver=2)
