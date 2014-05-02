from __future__ import unicode_literals, division, absolute_import
from datetime import datetime
import contextlib
import logging
import mmap
import xml.etree.ElementTree as ET

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry

log = logging.getLogger('winevents')


class WindowsEvents(object):
    """
    Provide Windows 7 events entries as input.
    Produced entries will have the events log id as title and url, plus these fields:
    - provider
    - short_name
    - event_time
    - event_id
    - event_text
    
    Example (complete task)::

      test_monitor:
        winevents:
          filename: c:\windows\sysnative\winevt\logs\Application.evtx
          providers:
            - APC UPS Service:
                short: UPS
                events:
                  - 61455: test description
            - Network something:
                events:
                  - 673
                  - 345: whatever
        accept_all: yes
        notify_xmpp:
          sender: somejid@domain
          password: somepassword
          recipient: anotherjid@anotherdomain
    """
    
    schema = {
        'type': 'object',
        'properties': {
            'filename': {'type': 'string', 'format': 'filename'},
            'providers': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'short': {'type': 'string'},
                        'events': {
                            'type': 'array',
                            'items': {
                                'type': 'object',
                                'additionalProperties': {'type': 'string'}
                            },
                            'minItems': 1
                        },
                    },
                    'additionalProperties': {'required': ['events']}
                },
                'minItems': 1
            }
        },
        'required': ['filename', 'providers'],
        'additionalProperties': False
    }

    def on_task_start(self, task, config):
        try:
            import Evtx
        except ImportError as e:
            log.debug('Error importing Evtx: %s' % e)
            raise plugin.DependencyError('winevents', 'python-evtx',
                'Evtx module required. ImportError: %s' % e)
    
    def on_task_input(self, task, config):
        from Evtx.Evtx import FileHeader
        from Evtx.Views import evtx_file_xml_view
        entries = []
        t1 = datetime.now()
        ntot = 0
        nerr = 0
        # WARNING: to open an active Windows eventlog files (i.e. those in the
        # %SystemRoot%\System32\Winevt\Logs\ path) Flexget will need to run as 
        # Administrator, otherwise open() will raise a "permission denied"
        # error. Exported logs can be accessed without special permissions.
        try:
            f = open(config['filename'], 'r')
        except Exception as err:
            log.error(str(err))
            return
        try:
            with contextlib.closing(mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)) as buf:
                fh = FileHeader(buf, 0x0)
                for xml, record in evtx_file_xml_view(fh):
                    ntot += 1
                    # some cleaning: namespaces here only makes accessing 
                    # nodes more difficult, while EventData content sometimes 
                    # fails ElementTree parsing (and it's useless too).
                    xml = xml.replace(' xmlns="http://schemas.microsoft.com/win/2004/08/events/event"', '')
                    if '<EventData>' in xml:
                        i1 = xml.index('<EventData>')-1
                        i2 = xml.index('</EventData>')+12
                        xml = xml[:i1] + xml[i2:]
                    try:
                        node = ET.fromstring(xml).find('System')
                    except:
                        nerr += 1  # malformed XML? lets skip this one...
                        continue
                    xprn = node.find('Provider').attrib['Name']
                    for prov in config['providers']:
                        cprn = prov.keys()[0]
                        if cprn == xprn:
                            erid = node.find('EventRecordID').text
                            xeid = int(node.find('EventID').text)
                            text = None
                            for e in prov[cprn]['events']:
                                ceid = e if type(e) is int else e.keys()[0]
                                if ceid == xeid:
                                    try:
                                        text = e[ceid]
                                    except:
                                        text = 'Undefined'
                            if text:
                                entry = Entry()
                                entry['title'] = entry['url'] = erid
                                entry['provider'] = cprn
                                entry['short_name'] = prov[cprn]['short'] if 'short' in prov[cprn] else cprn
                                entry['event_id'] = xeid
                                entry['event_text'] = text
                                entry['event_time'] = datetime.strptime(node.find('TimeCreated').attrib['SystemTime'], '%Y-%m-%d %H:%M:%S')
                                entries.append(entry)
                            break
        finally:
            f.close()
        t2 = datetime.now()
        res = 'Parsed %d events in %d seconds' % (ntot, (t2-t1).seconds)
        if nerr:
            res += (' (%d skipped for xml issues)' % nerr)
        log.verbose(res)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(WindowsEvents, 'winevents', api_ver=2)
