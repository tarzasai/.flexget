from __future__ import unicode_literals, division, absolute_import
import logging
import time
import re
import string
import random

from datetime import datetime

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.requests import RequestException
from flexget.utils.soup import get_soup

log = logging.getLogger('tvrage_rencans')


class TVRageRenCans(object):
    """
    """
    
    schema = {
        'type': 'object',
        'properties': {
            'pages': {'type': 'integer'},
            'context': {'enum': ['renewed', 'canceled']}
        },
        'required': ['pages', 'context'],
        'additionalProperties': False
    }
    
    def on_task_input(self, task, config):
        if not config:
            return
        entries = []
        check = []
        for i in range(config['pages']):
            try:
                page = task.requests.get('http://www.tvrage.com/status_update.php?show_only=%d&start=%d' % 
                                         (1 if config['context'] == 'renewed' else 2, i-1))
                soup = get_soup(page.text)
                trs = soup.find_all('tr', attrs={'id': 'brow'})
            except RequestException as err:
                raise plugin.PluginError('Error on reading status page/items: %s' % err)
            if not trs:
                raise plugin.PluginError('TVRage status table not found')
            for tr in trs:
                l = [c for c in tr.children if c != '\n']
                '''
                0 <td class="b1"><a href="/networks/US/CBS">CBS</a></td>
                1 <td class="b1" valign="top"><a href="/Undercover_Boss">Undercover Boss</a></td>
                2 <td class="b1" valign="top">Mar 13, 2014</td>
                3 <td class="b2" valign="top">Renewed for S06</td>
                '''
                if len(l) < 4:
                    raise plugin.PluginError('Unknown item structure!')
                netw = l[0].text  # CBS
                text = l[1].text  # Undercover Boss
                date = l[2].text  # Mar 13, 2014
                stat = l[3].text  # Renewed for S06
                try:
                    show = re.sub(r'\s\(\d more eps? listed.*', '', text)
                except:
                    log.warning('Unrecognized text "%s", skipping...' % text)
                    continue
                if show.lower() in check:
                    continue
                try:
                    surl = 'http://www.tvrage.com%s' % l[1].contents[0].attrs['href']
                except:
                    surl = None
                # skip today news
                d = datetime.fromtimestamp(time.mktime(time.strptime(date, "%b %d, %Y")))
                if show and d.date() < datetime.today().date():
                    entry = Entry()
                    entry['title'] = re.sub(r'\s\(\d more eps? listed.*', '', show)
                    entry['series_name'] = entry['title']
                    entry['url'] = 'http://localhost/fake-tvrage-news/%s' % \
                        ''.join([random.choice(string.letters + string.digits) for x in range(1, 30)])
                    entry['tvrage_url'] = surl
                    entry['tvrage_text'] = show
                    entry['tvrage_date'] = d
                    entry['tvrage_status'] = stat
                    entry['tvrage_network'] = netw
                    entries.append(entry)
                    check.append(show.lower())
        return sorted(entries, key=lambda k: k['series_name'])


@event('plugin.register')
def register_plugin():
    plugin.register(TVRageRenCans, 'tvrage_rencans', api_ver=2)