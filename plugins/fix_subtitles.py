from __future__ import unicode_literals, division, absolute_import
import os
import logging
import shutil

from flexget import plugin
from flexget.event import event
from fileinput import filename

log = logging.getLogger('fix_subtitles')


DEFAULT_EXTS = ['srt', 'it.srt']

class FixSubtitles(object):
    """
    """
    
    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {'type': 'array', 'items': {'type': 'string'}, 'default': DEFAULT_EXTS}
        ]
    }

    def on_task_exit(self, task, config):
        exts = DEFAULT_EXTS
        if isinstance(config, list):
            exts = config
        elif isinstance(config, bool) and not config:
            return
        for entry in task.accepted:
            if 'location' in entry:
                fn = os.path.splitext(entry['location'])[0]
                for ext in exts:
                    self.check_file(os.path.join(fn, ext))
    
    def check_file(self, filename):
        if not os.path.exists(filename):
            return
        try:
            with open(filename, 'r') as f:
                txt = f.read()
            if 'ç' in txt:
                res = txt.replace('ç', 'à').replace('ç', 'è').replace('ç', 'ì').replace('ç', 'ò').replace('ç', 'ù')
                bak = filename + '.bak'
                if os.path.exists(bak):
                    raise plugin.PluginWarning('backup already exists')
                shutil.copy(filename, bak)
                with open(filename, 'w') as f:
                    f.write(res)
                log.info('Subtitles file fixed: ' + filename)
        except Exception as err:
            log.error('Error on file %s: %s' % (filename, err))


@event('plugin.register')
def register_plugin():
    plugin.register(FixSubtitles, 'fix_subtitles', api_ver=2)