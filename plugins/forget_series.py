from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event
from flexget.plugins.filter.series import remove_series

log = logging.getLogger('set_series_forget')


class ForgetSeries(object):
    """
    Forget the given episode for series. Uses series_name and series_id.
    
    Example::

      forget_series: yes
    
    """
    
    schema = {'type': 'boolean'}
    
    def on_task_output(self, task, config):
        if not (config and task.accepted):
            return
        for entry in task.accepted:
            s = entry['title']
            try:
                self.log.info('Removing series "%s"' % s)
                remove_series(s)
            except ValueError as e:
                self.log.error(e)


@event('plugin.register')
def register_plugin():
    plugin.register(ForgetSeries, 'forget_series', api_ver=2)
