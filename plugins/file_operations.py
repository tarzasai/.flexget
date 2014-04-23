from __future__ import unicode_literals, division, absolute_import
import os
import shutil
import logging
import time

from flexget import plugin
from flexget.event import event
from flexget.utils.template import RenderError
from flexget.utils.pathscrub import pathscrub
from sqlalchemy.sql.elements import Null


def get_directory_size(directory):
    """
    :param directory: Path
    :return: Size in bytes (recursively)
    """
    dir_size = 0
    for (path, dirs, files) in os.walk(directory):
        for file in files:
            filename = os.path.join(path, file)
            dir_size += os.path.getsize(filename)
    return dir_size


class BaseFileOps(object):
    
    # Defined by subclasses
    log = None
    
    def on_task_output(self, task, config):
        if config is True:
            config = {}
        elif config is False:
            return
        
        sexts = []
        if 'along' in config:
            sexts = [('.' + s).replace('..', '.').lower() for s in config['along']]
        
        for entry in task.accepted:
            if not 'location' in entry:
                self.log.warning('Cannot handle %s because it does not have the field location.' % entry['title'])
                continue
            
            # check location
            src = entry['location']
            try:
                if not os.path.exists(src):
                    raise Exception('does not exists (anymore).')
                if os.path.isdir(src):
                    if not config.get('allow_dir'):
                        raise Exception('is a directory.')
                elif not os.path.isfile(src):
                    raise Exception('is not a file.')
            except Exception as err:
                self.log.warning('Cannot handle %s because location `%s` %s' % (entry['title'], src, err))
                continue
            
            # search for namesakes
            siblings = []
            if not os.path.isdir(src) and os.path.isfile(src) and 'along' in config:
                src_name, src_ext = os.path.splitext(src)
                for ext in sexts:
                    if ext != src_ext.lower() and os.path.exists(src_name + ext):
                        siblings.append(src_name + ext)
            
            # execute action in subclasses
            self.handle_entry(task, config, entry, siblings)
    
    def clean_source(self, task, config, entry):
        min_size = entry.get('clean_source', config.get('clean_source', -1))
        if min_size < 0:
            return
        base_path = os.path.split(entry['location'])[0]
        if not os.path.isdir(base_path):
            self.log.warning('Cannot delete path `%s` because it does not exists (anymore).' % base_path)
            return
        dir_size = get_directory_size(base_path) / 1024 / 1024
        if dir_size >= min_size:
            self.log.info('Path `%s` left because it exceeds safety value set in clean_source option.' % base_path)
            return
        if task.options.test:
            self.log.info('Would delete `%s` and everything under it.' % base_path)
            return
        try:
            shutil.rmtree(base_path)
            self.log.info('Path `%s` has been deleted because was less than clean_source safe value.' % base_path)
        except Exception as err:
            self.log.warning('Unable to delete path `%s`: %s' % (base_path, err))


class DeleteFiles(BaseFileOps):
    """Delete all accepted files."""

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'allow_dir': {'type': 'boolean'},
                    'along': {'type': 'array', 'items': {'type': 'string'}},
                    'clean_source': {'type': 'number'}
                },
                'additionalProperties': False
            }
        ]
    }
    
    log = logging.getLogger('delete_files')
    
    def handle_entry(self, task, config, entry, siblings):
        src = entry['location']
        src_is_dir = os.path.isdir(src)
        
        if task.options.test:
            if src_is_dir:
                self.log.info('Would delete `%s` and all its content.' % src)
            else:
                self.log.info('Would delete `%s`' % src)
                for s in siblings:
                    self.log.info('Would also delete `%s`' % s)
            return
        
        try:
            if src_is_dir:
                shutil.rmtree(src)
                self.log.info('`%s` and all its content has been deleted.' % src)
            else:
                os.remove(src)
                self.log.info('`%s` has been deleted.' % src)
        except Exception as err:
            entry.fail('delete error: %s' % err)
            return
        
        for s in siblings:
            try:
                os.remove(s)
                self.log.info('`%s` has been deleted as well.' % s)
            except Exception as err:
                # the target file has been successfully deleted, we cannot mark the entry as failed anymore. 
                self.log.warning('Unable to delete `%s`: %s' % (s, err))
        
        if not src_is_dir:
            self.clean_source(task, config, entry)


class TransformingOps(BaseFileOps):
    
    # Defined by subclasses
    move = None
    
    def handle_entry(self, task, config, entry, siblings):
        src = entry['location']
        src_is_dir = os.path.isdir(src)
        filepath, filename = os.path.split(src)
        
        # get proper value in order of: entry, config, above split
        dst_path = entry.get('path', config.get('to', filepath))
        dst_path = os.path.expanduser(dst_path)
        
        if entry.get('filename') and entry['filename'] != filename:
            # entry specifies different filename than what was split from the path
            # since some inputs fill in filename it must be different in order to be used
            dst_filename = entry['filename']
        elif 'filename' in config:
            # use from configuration if given
            dst_filename = config['filename']
        else:
            # just use original filename
            dst_filename = filename
        
        try:
            dst_path = entry.render(dst_path)
        except RenderError as err:
            self.log.warning('Path value replacement `%s` failed for %s: %s' % (dst_path, entry['title'], err))
            return
        try:
            dst_filename = entry.render(dst_filename)
        except RenderError as err:
            self.log.warning('Filename value replacement `%s` failed for %s: %s' % (dst_filename, entry['title'], err))
            return
        
        # Clean invalid characters with pathscrub plugin
        dst_path, dst_filename = pathscrub(dst_path), pathscrub(dst_filename, filename=True)
        
        # Join path and filename
        dst = os.path.join(dst_path, dst_filename)
        if dst == entry['location']:
            self.log.warning('Cannot handle %s because source and destination are the same.' % entry['title'])
            return
        
        if not os.path.exists(dst_path):
            if task.options.test:
                self.log.info('Would create `%s`' % dst_path)
            else:
                self.log.info('Creating destination directory `%s`' % dst_path)
                os.makedirs(dst_path)
        if not os.path.isdir(dst_path) and not task.options.test:
            self.log.warning('Cannot handle %s because destination `%s` is not a directory' % (entry['title'], dst_path))
            return
        
        src_name, src_ext = os.path.splitext(src)
        
        # unpack_safety
        if config.get('unpack_safety', entry.get('unpack_safety', True)):
            count = 0
            while True:
                if count > 60 * 30:
                    entry.fail('The task has been waiting unpacking for 30 minutes')
                    return
                size = os.path.getsize(src)
                time.sleep(1)
                new_size = os.path.getsize(src)
                if size != new_size:
                    if not count % 10:
                        self.log.verbose('File `%s` is possibly being unpacked, waiting ...' % filename)
                else:
                    break
                count += 1
        
        # Check dst contains src_ext
        dst_filename, dst_ext = os.path.splitext(dst)
        if dst_ext != src_ext:
            self.log.verbose('Adding extension `%s` to dst `%s`' % (src_ext, dst))
            dst += src_ext
        
        funct_name = 'move' if self.move else 'copy'
        funct_done = 'moved' if self.move else 'copied'
        move_or_copy = getattr(shutil, funct_name)
        
        if task.options.test:
            self.log.info('Would %s `%s` to `%s`' % (funct_name, src, dst))
            for s in siblings:
                # we cannot rely on splitext for extensions here (subtitles may have the language code)
                d = dst_filename + s[len(src_name):]
                self.log.info('Would also %s `%s` to `%s`' % (funct_name, s, d))
        else:
            try:
                move_or_copy(src, dst)
                self.log.info('`%s` has been %s to `%s`' % (src, funct_done, dst))
            except Exception as err:
                entry.fail('%s error: %s' % (funct_name, err))
                return
            
            for s in siblings:
                # we cannot rely on splitext for extensions here (subtitles may have the language code)
                d = dst_filename + s[len(src_name):]
                try:
                    move_or_copy(s, d)
                    self.log.info('`%s` has been %s to `%s` as well.' % (s, funct_done, d))
                except Exception as err:
                    # the target file has been successfully handled, we cannot mark the entry as failed anymore.
                    self.log.warning('Unable to %s `%s` to `%s`: %s' % (funct_name, s, d, err))
        
        entry['output'] = dst
        
        if self.move and not src_is_dir:
            self.clean_source(task, config, entry)


class CopyFiles(TransformingOps):
    """Copy all accepted files."""

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'to': {'type': 'string', 'format': 'path'},
                    'filename': {'type': 'string'},
                    'allow_dir': {'type': 'boolean'},
                    'unpack_safety': {'type': 'boolean'},
                    'along': {'type': 'array', 'items': {'type': 'string'}}
                },
                'additionalProperties': False
            }
        ]
    }
    
    move = False
    log = logging.getLogger('copy_files')


class MoveFiles(TransformingOps):
    """Move all accepted files."""

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'to': {'type': 'string', 'format': 'path'},
                    'filename': {'type': 'string'},
                    'allow_dir': {'type': 'boolean'},
                    'unpack_safety': {'type': 'boolean'},
                    'along': {'type': 'array', 'items': {'type': 'string'}},
                    'clean_source': {'type': 'number'}
                },
                'additionalProperties': False
            }
        ]
    }
    
    move = True
    log = logging.getLogger('move_files')


@event('plugin.register')
def register_plugin():
    plugin.register(DeleteFiles, 'delete_files', api_ver=2)
    plugin.register(CopyFiles, 'copy_files', api_ver=2)
    plugin.register(MoveFiles, 'move_files', api_ver=2)
