import importlib
import pathlib
import pkgutil
import threading
from collections import deque

from flexget import log
from flexget import plugin
from flexget.entry import Entry
from flexget.manager import manager
from loguru import logger

from .schema.site_base import SiteBase


class ThreadFilter:
    def __init__(self, thread_id):
        self.thread_id = thread_id

    def __call__(self, record):
        return record.get('thread').id == self.thread_id


def fail_with_prefix(self, reason):
    self.fail(f"{self.get('prefix')}=> {reason}")


Entry.fail_with_prefix = fail_with_prefix
thread_log = None


def build_sign_in_schema():
    module = None
    sites_schema = {}
    try:
        for module in pkgutil.iter_modules(path=[f'{pathlib.PurePath(__file__).parent}/sites']):
            site_class = get_site_class(module.name)
            sites_schema.update(site_class.build_sign_in_schema())
    except AttributeError as e:
        raise plugin.PluginError(f"site: {module.name}, error: {e}")
    return sites_schema


def build_reseed_schema():
    module = None
    sites_schema = {}
    try:
        for module in pkgutil.iter_modules(path=[f'{pathlib.PurePath(__file__).parent}/sites']):
            site_class = get_site_class(module.name)
            sites_schema.update(site_class.build_reseed_schema())
    except AttributeError as e:
        raise plugin.PluginError(f"site: {module.name}, error: {e}")
    return sites_schema


def build_sign_in_entry(entry, config):
    try:
        site_class = get_site_class(entry['class_name'])
        site_class.build_sign_in_entry(entry, config)
    except AttributeError as e:
        raise plugin.PluginError(f"site: {entry['site_name']}, error: {e}")


def sign_in_wrapper(entry, config):
    thread_id = threading.get_ident()
    if thread_id not in thread_log:
        thread_log[thread_id] = (deque(), deque())
        thread_filter = ThreadFilter(thread_id)
        logger.add(lambda message: thread_log[thread_id][0].append(message), level=manager.options.loglevel,
                   filter=thread_filter, format=log.LOG_FORMAT)
        logger.add(lambda message: thread_log[thread_id][1].append(message), level=manager.options.loglevel,
                   colorize=True, filter=thread_filter, format=log.LOG_FORMAT)
    try:
        sign_in(entry, config)
    except Exception as e:
        logger.exception(e)
        entry.fail_with_prefix('Exception: ' + str(e))


def sign_in(entry, config):
    try:
        site_class = get_site_class(entry['class_name'])
    except AttributeError as e:
        raise plugin.PluginError(f"site: {entry['class_name']}, error: {e}")

    site_object = site_class()
    entry['prefix'] = 'Sign_in'
    site_object.sign_in(entry, config)
    if entry.failed:
        return
    if entry['result']:
        logger.info(f"{entry['title']} {entry['result']}".strip())

    if config.get('get_messages', True):
        entry['prefix'] = 'Messages'
        site_object.get_message(entry, config)
        if entry.failed:
            return
        if entry['messages']:
            logger.info(f"site_name: {entry['site_name']}, messages: {entry['messages']}")

    if config.get('get_details', True):
        entry['prefix'] = 'Details'
        site_object.get_details(entry, config)
        if entry.failed:
            return
        if entry['details']:
            logger.info(f"site_name: {entry['site_name']}, details: {entry['details']}")
    clean_entry_attr(entry)


def clean_entry_attr(entry):
    for attr in ['base_content', 'prefix']:
        if hasattr(entry, attr):
            del entry[attr]


def build_reseed_entry(entry, config, site, passkey, torrent_id):
    try:
        site_class = get_site_class(entry['class_name'])
        site_class.build_reseed_entry(entry, config, site, passkey, torrent_id)
    except AttributeError:
        SiteBase.build_reseed_entry(entry, config, site, passkey, torrent_id)


def get_site_class(class_name):
    site_module = importlib.import_module(f'flexget.plugins.ptsites.sites.{class_name.lower()}')
    site_class = getattr(site_module, 'MainClass')
    return site_class
