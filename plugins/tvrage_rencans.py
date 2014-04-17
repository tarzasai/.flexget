from __future__ import unicode_literals, division, absolute_import
import logging
import time

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
    
    schema = {'type': 'integer'}
    
    def on_task_input(self, task, config):
        if not config:
            return
        lines = {}
        for i in range(config):
            try:
                page = task.requests.get('http://www.tvrage.com/status_update.php?start=' + str(i-1))
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
                #netw = l[0].text  # CBS
                show = l[1].text  # Undercover Boss
                date = l[2].text  # Mar 13, 2014
                stat = l[3].text  # Renewed for S06
                text = '%s %s' % (show, stat[0].lower() + stat[1:])
                rows = lines.setdefault(date, [])
                if not text in rows:
                    rows.append(text)
        entries = []
        for k in sorted(lines.keys()):
            d = datetime.fromtimestamp(time.mktime(time.strptime(k, "%b %d, %Y")))
            if d.date() < datetime.today().date(): # skip today, or we may lose something
                entry = Entry()
                entry['title'] = entry['url'] = 'TVRage-' + k.replace(',', '').replace(' ', '-')
                entry['tvrsu_date'] = d
                entry['tvrsu_lines'] = sorted(lines[k])
                entries.append(entry)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(TVRageRenCans, 'tvrage_rencans', api_ver=2)