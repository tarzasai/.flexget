from __future__ import unicode_literals, division, absolute_import
import os
import logging
import shutil

from flexget import plugin
from flexget.event import event

log = logging.getLogger('fix_subtitles')


class FixSubs(object):
    """
    """
    
    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1}
        ]
    }
    
    def on_task_exit(self, task, config):
        exts = ['.it.srt', '.ita.srt']
        if isinstance(config, list):
            exts = [('.' + s).replace('..', '.') for s in config]
        elif isinstance(config, bool) and not config:
            return
        for entry in task.accepted:
            if not ('location' in entry and os.path.exists(entry['location'])):
                continue
            fn = os.path.splitext(entry['location'])[0]
            for ext in exts:
                sub = fn + ext
                if not os.path.exists(sub):
                    continue
                try:
                    with open(sub, 'r') as f:
                        bak = txt = f.read()
                    txt = txt.replace('ŕ', 'à').replace('č', 'è').replace('ě', 'ì').replace('ň', 'ò').replace('ů', 'ù')
                    if txt != bak:
                        bak = sub + '.bak'
                        if os.path.exists(bak):
                            raise plugin.PluginWarning('backup already exists')
                        shutil.copy(sub, bak)
                        with open(sub, 'w') as f:
                            f.write(txt)
                        log.info('Subtitles file fixed: ' + sub)
                except Exception as err:
                    log.error('Error on file %s: %s' % (sub, err.args[0]))


@event('plugin.register')
def register_plugin():
    plugin.register(FixSubs, 'fix_subtitles', api_ver=2)