from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import collections
import logging
import os
import sys
import tempfile

from flexget import plugin
from flexget.event import event

log = logging.getLogger('subtitles')

try:
    from subliminal.extensions import provider_manager
    PROVIDERS = provider_manager.names()
except ImportError:
    PROVIDERS = [
        'opensubtitles',
        'thesubdb',
        'podnapisi',
        'addic7ed',
        'tvsubtitles'
    ]

AUTHENTICATION_SCHEMA = dict((provider, {'type': 'object'}) for provider in PROVIDERS)


class PluginSubliminal(object):
    """
    Search and download subtitles using Subliminal by Antoine Bertin
    (https://pypi.python.org/pypi/subliminal).

    Example (complete task)::

      subs:
        find:
          path:
            - d:\media\incoming
          regexp: '.*\.(avi|mkv|mp4)$'
          recursive: yes
        accept_all: yes
        subliminal:
          languages:
            - ita
          alternatives:
            - eng
          exact_match: no
          providers: addic7ed, opensubtitles
          single: no
          directory: /disk/subtitles
          hearing_impaired: yes
          authentication:
            addic7ed:
              username: myuser
              passsword: mypassword
    """

    schema = {
        'type': 'object',
        'properties': {
            'languages': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1},
            'alternatives': {'type': 'array', 'items': {'type': 'string'}},
            'exact_match': {'type': 'boolean', 'default': True},
            'providers': {'type': 'array', 'items': {'type': 'string', 'enum': PROVIDERS}},
            'single': {'type': 'boolean', 'default': True},
            'directory': {'type:': 'string'},
            'hearing_impaired': {'type': 'boolean', 'default': False},
            'authentication': {'type': 'object', 'properties': AUTHENTICATION_SCHEMA},
        },
        'required': ['languages'],
        'additionalProperties': False
    }

    def on_task_start(self, task, config):
        if list(sys.version_info) < [2, 7]:
            raise plugin.DependencyError('subliminal', 'Python 2.7', 'Subliminal plugin requires python 2.7.')
        try:
            import babelfish
        except ImportError as e:
            log.debug('Error importing Babelfish: %s', e)
            raise plugin.DependencyError('subliminal', 'babelfish', 'Babelfish module required. ImportError: %s' % e)
        try:
            import subliminal
        except ImportError as e:
            log.debug('Error importing Subliminal: %s', e)
            raise plugin.DependencyError('subliminal', 'subliminal', 'Subliminal module required. ImportError: %s' % e)

    def on_task_output(self, task, config):
        """
        Configuration::
            subliminal:
                languages: List of languages (as IETF codes) in order of preference. At least one is required.
                alternatives: List of second-choice languages; subs will be downloaded but entries rejected.
                exact_match: Use file hash only to search for subs, otherwise Subliminal will try to guess by filename.
                providers: List of providers from where to download subtitles.
                single: Download subtitles in single mode (no language code added to subtitle filename).
                directory: Path to directory where to save the subtitles, default is next to the video.
                hearing_impaired: Prefer subtitles for the hearing impaired when available
                authentication: >
                  Dictionary of configuration options for different providers.
                  Keys correspond to provider names, and values are dictionaries, usually specifying `username` and
                  `password`.
        """
        if not task.accepted:
            log.debug('nothing accepted, aborting')
            return
        from babelfish import Language
        from dogpile.cache.exception import RegionAlreadyConfigured
        import subliminal
        from subliminal.cli import MutexLock
        from subliminal.score import episode_scores, movie_scores
        try:
            cachefile = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'subliminal', 'subliminal', 'Cache', 'subliminal.dbm')
            subliminal.region.configure('dogpile.cache.dbm', arguments={'filename': cachefile, 'lock_factory': MutexLock,})
        except RegionAlreadyConfigured:
            pass

        # Let subliminal be more verbose if our logger is set to DEBUG
        if log.isEnabledFor(logging.DEBUG):
            logging.getLogger("subliminal").setLevel(logging.INFO)
        else:
            logging.getLogger("subliminal").setLevel(logging.CRITICAL)

        logging.getLogger("dogpile").setLevel(logging.CRITICAL)
        logging.getLogger("enzyme").setLevel(logging.WARNING)
        try:
            languages = set([Language.fromietf(s) for s in config.get('languages', [])])
            alternative_languages = set([Language.fromietf(s) for s in config.get('alternatives', [])])
        except ValueError as e:
            raise plugin.PluginError(e)
        # keep all downloaded subtitles and save to disk when done (no need to write every time)
        downloaded_subtitles = collections.defaultdict(list)
        providers_list = config.get('providers', None)
        provider_configs = config.get('authentication', None)
        # test if only one language was provided, if so we will download in single mode
        # (aka no language code added to subtitle filename)
        # unless we are forced not to by configuration
        # if we pass 'yes' for single in configuration but choose more than one language
        # we ignore the configuration and add the language code to the
        # potentially downloaded files
        single_mode = config.get('single', '') and len(languages | alternative_languages) <= 1
        hearing_impaired = config.get('hearing_impaired', False)

        with subliminal.core.ProviderPool(providers=providers_list, provider_configs=provider_configs) as provider_pool:
            for entry in task.accepted:
                if 'location' not in entry:
                    log.warning('Cannot act on entries that do not represent a local file.')
                    continue
                if not os.path.exists(entry['location']):
                    entry.fail('file not found: %s' % entry['location'])
                    continue
                if '$RECYCLE.BIN' in entry['location']:  # ignore deleted files in Windows shares
                    continue

                try:
                    video = subliminal.scan_video(entry['location'])
                    
                    # use metadata refiner to get mkv metadata
                    subliminal.core.refine(video, episode_refiners=('metadata',), movie_refiners=('metadata',))
                    video.subtitle_languages |= set(subliminal.core.search_external_subtitles(entry['location']).values())
                    
                    primary_languages = set(entry.get('subtitle_languages', [])) or languages
                    if primary_languages.issubset(video.subtitle_languages) or (single_mode and video.subtitle_languages):
                        log.debug('All preferred languages already exist for "%s"', entry['title'])
                        continue  # subs for preferred language(s) already exists
                    
                    if isinstance(video, subliminal.Episode):
                        title = video.series
                        hash_scores = episode_scores['hash']
                    else:
                        title = video.title
                        hash_scores = movie_scores['hash']
                    log.debug('Name computed for %s was %s', entry['location'], title)
                    msc = hash_scores if config['exact_match'] else 0
                    
                    ####################################################################################################
                    
                    all_languages = primary_languages | alternative_languages
                    subtitles_list = provider_pool.list_subtitles(video, all_languages - video.subtitle_languages)
                    subtitles = provider_pool.download_best_subtitles(subtitles_list, video, all_languages,
                                                                      min_score=msc, hearing_impaired=hearing_impaired)
                    if subtitles:
                        downloaded_subtitles[video].extend(subtitles)
                        downloaded_languages = set([Language.fromietf(str(l.language)) for l in subtitles])
                        if len(downloaded_languages & primary_languages):
                            log.info('Subtitles found for %s', entry['location'])
                        else:
                            log.info('subtitles found for a second-choice language.')
                        video.subtitle_languages |= downloaded_languages
                        entry['subtitles'] = [l.alpha3 for l in video.subtitle_languages]
                    else:
                        log.verbose('cannot find any subtitles for now.')

                    '''
                    subtitles_list = provider_pool.list_subtitles(video, primary_languages - video.subtitle_languages)
                    subtitles = provider_pool.download_best_subtitles(subtitles_list, video, primary_languages,
                                                                      min_score=msc, hearing_impaired=hearing_impaired)
                    if subtitles:
                        downloaded_subtitles[video].extend(subtitles)
                        log.info('Subtitles found for %s', entry['location'])
                    else:
                        # only try to download for alternatives that aren't already downloaded
                        subtitles_list = provider_pool.list_subtitles(video, alternative_languages - video.subtitle_languages)
                        subtitles = provider_pool.download_best_subtitles(subtitles_list, video,
                                                                          alternative_languages, min_score=msc,
                                                                          hearing_impaired=hearing_impaired)
                        if subtitles:
                            downloaded_subtitles[video].extend(subtitles)
                            log.info('subtitles found for a second-choice language.')
                        else:
                            log.verbose('cannot find any subtitles for now.')
                            
                    if subtitles:
                        downloaded_languages = set([Language.fromietf(str(l.language)) for l in subtitles])
                        entry['subtitles'] = [l.alpha3 for l in video.subtitle_languages]
                        for l in downloaded_subtitles[video]:
                            code = Language.fromietf(unicode(l.language)).alpha3
                            if not code in entry['subtitles']:
                                entry['subtitles'].append(code)
                    '''
                    ####################################################################################################
                                    
                except ValueError as e:
                    log.error('subliminal error: %s', e)
                    entry.fail()

        if downloaded_subtitles:
            if task.options.test:
                log.verbose('Test mode. Found subtitles:')
            # save subtitles to disk
            for video, subtitle in downloaded_subtitles.items():
                if subtitle:
                    _directory = config.get('directory')
                    if _directory:
                        _directory = os.path.expanduser(_directory)
                    if task.options.test:
                        log.verbose('     FOUND LANGUAGES %s for %s', [str(l.language) for l in subtitle], video.name)
                        continue
                    subliminal.save_subtitles(video, subtitle, single=single_mode, directory=_directory)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSubliminal, 'mysubliminal', api_ver=2)
