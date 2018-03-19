# This program is free software: you can redistribute it
# and/or modify it under the terms of the GPL licence

import logging

from .service import PyTestService
from .listener import RPReportListener

try:
    # This try/except can go away once we support pytest >= 3.3
    import _pytest.logging
    PYTEST_HAS_LOGGING_PLUGIN = True
except ImportError:
    PYTEST_HAS_LOGGING_PLUGIN = False


def pytest_sessionstart(session):
    if session.config.getoption('--collect-only', default=False) is True:
        return

    PyTestService.init_service(
        project=session.config.getini('rp_project'),
        endpoint=session.config.getini('rp_endpoint'),
        uuid=session.config.getini('rp_uuid'),
        log_batch_size=int(session.config.getini('rp_log_batch_size')),
        ignore_errors=bool(session.config.getini('rp_ignore_errors')),
        ignored_tags=session.config.getini('rp_ignore_tags'),
    )

    if hasattr(session.config, 'workerinput'):
        # if xdist slave then attach to existing launch
        PyTestService.RP.rp_client.launch_id = session.config.option.launch_id
    else:
        PyTestService.start_launch(
            session.config.option.rp_launch,
            tags=session.config.getini('rp_launch_tags'),
            description=session.config.option.rp_launch_description,
        )

        # we need to be sure that launch created to receive launch_id and save it
        PyTestService.RP.queue.join()
        session.config.option.launch_id = PyTestService.RP.rp_client.launch_id


def pytest_sessionfinish(session):
    if session.config.getoption('--collect-only', default=False) is True:
        return

    # FixMe: currently method of RP api takes the string parameter
    # so it is hardcoded

    # finish launch only if it is not a slave
    if not hasattr(session.config, 'workerinput'):
        PyTestService.finish_launch(status='RP_Launch')


def pytest_configure(config):
    if not config.option.rp_launch:
        config.option.rp_launch = config.getini('rp_launch')
    if not config.option.rp_launch_description:
        config.option.rp_launch_description = config.getini('rp_launch_description')

    # set Pytest_Reporter and configure it

    if PYTEST_HAS_LOGGING_PLUGIN:
        # This check can go away once we support pytest >= 3.3
        try:
            config._reporter = RPReportListener(
                _pytest.logging.get_actual_log_level(config, 'rp_log_level')
            )
        except TypeError:
            # No log level set either in INI or CLI
            config._reporter = RPReportListener()
    else:
        config._reporter = RPReportListener()

    if hasattr(config, '_reporter'):
        config.pluginmanager.register(config._reporter)


def pytest_unconfigure(config):
    PyTestService.terminate_service()

    if hasattr(config, '_reporter'):
        reporter = config._reporter
        del config._reporter
        config.pluginmanager.unregister(reporter)
        logging.debug('RP is unconfigured')


def pytest_addoption(parser):
    group = parser.getgroup('reporting')
    group.addoption(
        '--rp-launch',
        action='store',
        dest='rp_launch',
        help='Launch name (overrides rp_launch config option)')
    group.addoption(
        '--rp-launch-description',
        action='store',
        dest='rp_launch_description',
        help='Launch description (overrides rp_launch_description config option)')

    if PYTEST_HAS_LOGGING_PLUGIN:
        group.addoption(
            '--rp-log-level',
            dest='rp_log_level',
            default=logging.NOTSET,
            help='Logging level for automated log records reporting'
        )
        parser.addini(
            'rp_log_level',
            default=logging.NOTSET,
            help='Logging level for automated log records reporting'
        )

    parser.addini(
        'rp_uuid',
        help='UUID')

    parser.addini(
        'rp_endpoint',
        help='Server endpoint')

    parser.addini(
        'rp_project',
        help='Project name')

    parser.addini(
        'rp_launch',
        default='Pytest Launch',
        help='Launch name')

    parser.addini(
        'rp_launch_tags',
        type='args',
        help='Launch tags, i.e Performance Regression')

    parser.addini(
        'rp_launch_description',
        default='',
        help='Launch description')

    parser.addini(
        'rp_log_batch_size',
        default='20',
        help='Size of batch log requests in async mode')

    parser.addini(
        'rp_ignore_errors',
        default=False,
        type='bool',
        help='Ignore Report Portal errors (exit otherwise)')

    parser.addini(
        'rp_ignore_tags',
        type='args',
        help='Ignore specified pytest markers, i.e parametrize')
