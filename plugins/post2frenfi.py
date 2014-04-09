from __future__ import unicode_literals, division, absolute_import
import logging
import time

from flexget import plugin
from flexget.event import event
from flexget.utils.template import RenderError, render_from_task

log = logging.getLogger('friendfeed')


class Publish2FF(object):
    """
    """
    
    schema = {
        'type': 'object',
        'properties': {
            'app_key': {'type': 'string'},
            'app_secret': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'mode': {'enum': ['posts', 'comments'], 'default': 'posts'},
            'feeds': {'type': 'array', 'items': {'type': 'string'}, 'default': ['me']},
            'text': {'type': 'string', 'default': '{{title}}'},
            'link': {'type': 'string'},
            'image': {'type': 'string'},
            'comment': {'type': 'string'}
        },
        'required': ['app_key', 'app_secret', 'username', 'password'],
        'additionalProperties': False
    }

    def on_task_start(self, task, config):
        try:
            import flexget.plugins.local.friendfeed2
        except ImportError as e:
            log.debug('Error importing FriendFeed API 2.0: %s' % e)
            raise plugin.DependencyError('friendfeed', 'friendfeed', 
                                  'FriendFeed API 2.0 module required. ImportError: %s' % e)
    
    @plugin.priority(0)
    def on_task_output(self, task, config):
        if not task.accepted:
            log.debug('nothing accepted, aborting')
            return
        rooms = [s.encode('utf8').lower() for s in config.get('feeds', [])]
        if task.options.test:
            log.info('Test posting to feed(s): ' + ','.join(rooms))
        else:
            from flexget.plugins.local.friendfeed2 import FriendFeed, fetch_installed_app_access_token
            consumer_token = {'key': config['app_key'], 'secret': config['app_secret']}
            access_token = fetch_installed_app_access_token(consumer_token, config['username'], config['password'])
            ff = FriendFeed(oauth_consumer_token=consumer_token, oauth_access_token=access_token)
        if config['mode'] == 'posts':
            for entry in task.accepted:
                try:
                    fftext = entry.render(config['text'])
                    fflink = entry.render(config['link']) if 'link' in config else None
                    ffcomm = entry.render(config['comment']) if 'comment' in config else None
                    ffpict = entry.render(config['image']) if 'image' in config else None
                except RenderError as e:
                    log.error('Error rendering data: %s' % e)
                if task.options.test:
                    log.info('Test run for entry ' + entry['title'])
                    log.info('- Text would be: ' + fftext)
                    if fflink:
                        log.info('- Link would be: ' + fflink)
                    if ffpict:
                        log.info('- Image would be: ' + ffpict)
                    if ffcomm:
                        log.info('- Comment would be: ' + ffcomm)
                else:
                    try:
                        res = ff.post_entry(fftext, link=fflink, comment=ffcomm, 
                                            to=','.join(rooms), image_url=ffpict)
                        log.info('Published id: %s' % res['id'])
                    except Exception as err:
                        log.info('post_entry() failed with %s' % str(err))
        else:
            if not config.get('comment'):
                raise plugin.PluginError('"comment" option is required when "mode"=="comments".')
            try:
                fftext = render_from_task(config['text'], task)
                fflink = render_from_task(config['link'], task) if 'link' in config else None
                ffpict = render_from_task(config['image'], task) if 'image' in config else None
            except RenderError as e:
                log.error('Error rendering data: %s' % e)
            if task.options.test:
                log.info('Test run for task.')
                log.info('- Text would be: ' + fftext)
                if fflink:
                    log.info('- Link would be: ' + fflink)
                if ffpict:
                    log.info('- Image would be: ' + ffpict)
            else:
                res = ff.post_entry(fftext, link=fflink, to=','.join(rooms), image_url=ffpict)
                log.info('Published id: %s' % res['id'])
            for entry in task.accepted:
                try:
                    ffcomm = entry.render(config['comment'])
                except RenderError as e:
                    log.error('Error rendering data: %s' % e)
                if task.options.test:
                    log.info('- Comment would be: ' + ffcomm)
                else:
                    try:
                        time.sleep(1)
                        rcm = ff.post_comment(res['id'], ffcomm)
                        log.verbose('Published comment id: %s' % rcm['id'])
                    except Exception as err:
                        log.info('post_comment() failed with %s' % str(err))


@event('plugin.register')
def register_plugin():
    plugin.register(Publish2FF, 'friendfeed', api_ver=2)
