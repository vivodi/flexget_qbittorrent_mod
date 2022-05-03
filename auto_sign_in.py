from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import loguru
from flexget import log
from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import manager
from loguru import logger

from .ptsites import executor
from .ptsites.utils.details_report import DetailsReport


class PluginAutoSignIn:
    schema = {
        'type': 'object',
        'properties': {
            'user-agent': {'type': 'string'},
            'max_workers': {'type': 'integer'},
            'get_messages': {'type': 'boolean', 'default': True},
            'get_details': {'type': 'boolean', 'default': True},
            'aipocr': {
                'type': 'object',
                'properties': {
                    'app_id': {'type': 'string'},
                    'api_key': {'type': 'string'},
                    'secret_key': {'type': 'string'}
                },
                'additionalProperties': False
            },
            'sites': {
                'type': 'object',
                'properties': executor.build_sign_in_schema()
            }
        },
        'additionalProperties': False
    }

    def prepare_config(self, config):
        config.setdefault('user-agent', '')
        config.setdefault('command_executor', '')
        config.setdefault('max_workers', {})
        config.setdefault('aipocr', {})
        config.setdefault('sites', {})
        return config

    def on_task_input(self, task, config):
        config = self.prepare_config(config)
        sites = config.get('sites')

        entries = []

        for site_name, site_configs in sites.items():
            if not isinstance(site_configs, list):
                site_configs = [site_configs]
            for sub_site_config in site_configs:
                entry = Entry(
                    title='{} {}'.format(site_name, datetime.now().date()),
                    url=''
                )
                entry['site_name'] = site_name
                entry['class_name'] = site_name
                entry['site_config'] = sub_site_config
                entry['result'] = ''
                entry['messages'] = ''
                entry['details'] = ''
                executor.build_sign_in_entry(entry, config)
                entries.append(entry)
        return entries

    def on_task_output(self, task, config):
        max_workers = config.get('max_workers', 1)
        date_now = str(datetime.now().date())
        for entry in task.all_entries:
            if date_now not in entry['title']:
                entry.reject('{} out of date!'.format(entry['title']))
        handlers = logger._core.handlers.values()
        logger._core.handlers = {}
        executor.thread_log = {}
        with ThreadPoolExecutor(max_workers=max_workers) as threadExecutor:
            for entry in task.accepted:
                threadExecutor.submit(executor.sign_in_wrapper, entry, config)
        for e in executor.thread_log.values():
            for handler in handlers:
                if isinstance(handler._sink, loguru._file_sink.FileSink):
                    for msg in e[0]:
                        handler._sink.write(msg)
                if not isinstance(handler._sink, loguru._file_sink.FileSink):
                    for msg in e[1]:
                        handler._sink.write(msg)
        logger.remove()
        log._logging_started = False
        log.initialize()
        manager._init_logging()
        if config.get('get_details', True):
            DetailsReport().build(task)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginAutoSignIn, 'auto_sign_in', api_ver=2)
