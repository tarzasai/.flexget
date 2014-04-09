from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry

log = logging.getLogger('getffcomms')


class GetFFComments(object):
    """
    """
    
    schema = {
        'type': 'object',
        'properties': {
            'app_key': {'type': 'string'},
            'app_secret': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'posts': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1}
        },
        'required': ['app_key', 'app_secret', 'username', 'password', 'posts'],
        'additionalProperties': False
    }
    
    def on_task_start(self, task, config):
        try:
            import flexget.plugins.local.friendfeed2
        except ImportError as e:
            log.debug('Error importing FriendFeed API 2.0: %s' % e)
            raise plugin.DependencyError('friendfeed', 'friendfeed', 
                                  'FriendFeed API 2.0 module required. ImportError: %s' % e)
    
    def on_task_input(self, task, config):
        from flexget.plugins.local.friendfeed2 import FriendFeed, fetch_installed_app_access_token
        consumer_token = {'key': config['app_key'], 'secret': config['app_secret']}
        access_token = fetch_installed_app_access_token(consumer_token, config['username'], config['password'])
        ff = FriendFeed(oauth_consumer_token=consumer_token, oauth_access_token=access_token)
        try:
            feed = ff.fetch('/entry', id=','.join(config['posts']), raw=1, maxcomments=10000, maxlikes=0)
        except Exception as err:
            raise plugin.PluginError('Fetch() failed: %s' % err)
        if not feed or not feed.get('entries', []):
            raise plugin.PluginError('No posts data returned!')
        entries = []
        for post in feed['entries']:
            title = post['rawBody']
            title = (title[:47] + '...') if len(title) > 47 else title
            if not post.get('comments', []):
                log.verbose('No comments found on entry "%s"' % title)
                continue
            log.verbose('Emitting comments for entry "%s"...' % title)
            for comm in post['comments']:
                entry = Entry()
                entry['title'] = entry['url'] = comm['id']
                entry['post_url'] = post['url']
                entry['post_title'] = title
                entry['post_author'] = post['from']['name']
                entry['comment_body'] = comm['rawBody']
                entry['comment_author'] = comm['from']['name']
                entries.append(entry)
        log.verbose('Found %d comment(s) on %d post(s).' % (len(entries), len(feed['entries'])))
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(GetFFComments, 'getffcomms', api_ver=2)