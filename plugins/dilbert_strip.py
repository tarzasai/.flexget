from __future__ import unicode_literals, division, absolute_import
import logging

from requests.exceptions import RequestException

from flexget import plugin
from flexget.event import event
from flexget.utils.soup import get_soup

log = logging.getLogger('dilbert_strip')


class DilbertStrip(object):

    schema = {'type': 'boolean'}

    def on_task_filter(self, task, config):
        if not (config and task.entries):
            return
        for entry in task.entries:
            if entry.rejected or not (entry['url'].startswith('http://dilbert.com') or \
                                      entry['url'].startswith('http://feed.dilbert.com')):
                continue
            try:
                page = task.requests.get(entry['url'])
            except RequestException as err:
                log.error("RequestsException opening entry '%s' link: %s" % (entry['title'], err))
                continue
            soup = get_soup(page.text)
            try:
                # /html/body/div[2]/div[3]/section/div[1]/a/img
                node = soup.find('div', attrs={'class': 'img-comic-container'}).find_all('img')[0]
            except Exception as err:
                log.error('Unable to get image node: %s' % err)
                continue
            if node and node.get('src'):
                entry['strip_url'] = node.get('src')
                entry['strip_title'] = node.get('alt', "no title")
            else:
                log.error('Unable to get image node for "%s"' % entry['title'])


@event('plugin.register')
def register_plugin():
    plugin.register(DilbertStrip, 'dilbert_strip', api_ver=2)
