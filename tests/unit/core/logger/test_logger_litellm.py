import importlib
import io
import json
import logging
import logging.config
import os
import sys
from unittest import mock

import litellm
import pytest


@pytest.fixture
def reset_litellm():
    """Reset litellm settings and logger module after each test."""
    yield
    litellm.suppress_debug_info = False
    litellm.set_verbose = False
    # Remove logger module from sys.modules to force reload
    if 'openhands.core.logger' in sys.modules:
        del sys.modules['openhands.core.logger']


def test_litellm_settings_debug_llm_disabled(reset_litellm):
    """Test that litellm settings are properly configured when DEBUG_LLM is disabled."""
    with mock.patch.dict(os.environ, {'DEBUG_LLM': 'false'}):
        import openhands.core.logger  # noqa: F401

        importlib.reload(openhands.core.logger)

        assert litellm.suppress_debug_info is True
        assert litellm.set_verbose is False


def test_litellm_settings_debug_llm_enabled(reset_litellm):
    """Test that litellm settings are properly configured when DEBUG_LLM is enabled and confirmed."""
    with (
        mock.patch.dict(os.environ, {'DEBUG_LLM': 'true'}),
        mock.patch('builtins.input', return_value='y'),
    ):
        import openhands.core.logger  # noqa: F401

        importlib.reload(openhands.core.logger)

        assert litellm.suppress_debug_info is False
        assert litellm.set_verbose is True


def test_litellm_settings_debug_llm_enabled_but_declined(reset_litellm):
    """Test that litellm settings remain disabled when DEBUG_LLM is enabled but user declines."""
    with (
        mock.patch.dict(os.environ, {'DEBUG_LLM': 'true'}),
        mock.patch('builtins.input', return_value='n'),
    ):
        import openhands.core.logger  # noqa: F401

        importlib.reload(openhands.core.logger)

        assert litellm.suppress_debug_info is True
        assert litellm.set_verbose is False


def test_litellm_loggers_suppressed_with_uvicorn_json_config(reset_litellm):
    """
    Test that LiteLLM loggers remain suppressed after applying uvicorn JSON log config.

    This reproduces the bug that was introduced in v0.59.0 where calling
    logging.config.dictConfig() would reset the disabled flag on LiteLLM loggers,
    causing them to propagate to the root logger.

    The fix ensures LiteLLM loggers are explicitly configured in the uvicorn config
    with propagate=False and NullHandler to prevent logs from leaking through.
    """
    # Read the source file directly from disk to verify the fix is present
    # (pytest caches bytecode, so we can't rely on imports or inspect.getsource)
    import pathlib

    # Find the logger.py file path relative to the openhands package
    # __file__ is tests/unit/core/logger/test_logger_litellm.py
    # We need to go up to tests/, then find openhands/core/logger.py
    test_dir = pathlib.Path(__file__).parent  # tests/unit/core/logger
    project_root = test_dir.parent.parent.parent.parent  # workspace/openhands
    logger_file = project_root / 'openhands' / 'core' / 'logger.py'

    # Read the actual source file
    with open(logger_file, 'r') as f:
        source = f.read()

    # Verify that the fix is present in the source code
    litellm_loggers = ['LiteLLM', 'LiteLLM Router', 'LiteLLM Proxy']
    for logger_name in litellm_loggers:
        assert f"'{logger_name}'" in source or f'"{logger_name}"' in source, (
            f'{logger_name} logger configuration should be present in logger.py source'
        )

    assert "'class': 'logging.NullHandler'" in source, (
        'Fix should include NullHandler definition'
    )
    assert "'propagate': False" in source or '"propagate": False' in source, (
        'Fix should set propagate to False'
    )
    assert "litellm_level = 'CRITICAL'" in source, (
        'Fix should set level to CRITICAL when suppressing'
    )


def test_litellm_no_stderr_output_after_dictconfig():
    """Test that LiteLLM loggers don't output to stderr after dictConfig is applied."""
    from litellm._logging import verbose_logger

    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'null': {
                'class': 'logging.NullHandler',
            },
        },
        'loggers': {
            'LiteLLM': {
                'handlers': ['null'],
                'level': 'CRITICAL',
                'propagate': False,
            },
            'LiteLLM Router': {
                'handlers': ['null'],
                'level': 'CRITICAL',
                'propagate': False,
            },
            'LiteLLM Proxy': {
                'handlers': ['null'],
                'level': 'CRITICAL',
                'propagate': False,
            },
        },
    }

    logging.config.dictConfig(config)

    assert verbose_logger.handlers, 'Logger should have handlers (NullHandler)'
    assert isinstance(verbose_logger.handlers[0], logging.NullHandler)
    assert verbose_logger.propagate is False

    old_stderr = sys.stderr
    sys.stderr = io.StringIO()

    try:
        verbose_logger.debug('DEBUG message')
        verbose_logger.info('INFO message')
        verbose_logger.warning('WARNING message')
        verbose_logger.error('ERROR message')
        verbose_logger.critical('CRITICAL message')

        stderr_output = sys.stderr.getvalue()
    finally:
        sys.stderr = old_stderr

    assert stderr_output == '', (
        f'No output should go to stderr, but got: {stderr_output!r}'
    )


def test_litellm_json_output_when_enabled():
    """Test that LiteLLM logs are output as JSON when configured with JSON handler."""
    from litellm._logging import verbose_logger
    from pythonjsonlogger.jsonlogger import JsonFormatter

    capture_stream = io.StringIO()
    handler = logging.StreamHandler(capture_stream)
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        JsonFormatter('%(message)s %(levelname)s %(name)s %(asctime)s')
    )

    verbose_logger.handlers.clear()
    verbose_logger.addHandler(handler)
    verbose_logger.setLevel(logging.INFO)
    verbose_logger.propagate = False

    old_stderr = sys.stderr
    sys.stderr = io.StringIO()

    try:
        test_message = 'LiteLLM completion() model= test-model; provider = test'
        verbose_logger.info(test_message)

        stdout_output = capture_stream.getvalue()
        stderr_output = sys.stderr.getvalue()
    finally:
        sys.stderr = old_stderr

    assert stderr_output == '', (
        f'No output should go to stderr, but got: {stderr_output!r}'
    )
    assert stdout_output, 'Output should be captured'

    try:
        log_entry = json.loads(stdout_output.strip())
    except json.JSONDecodeError as e:
        pytest.fail(
            f'Output should be valid JSON, but got: {stdout_output!r}, error: {e}'
        )

    assert log_entry.get('message') == test_message
    assert log_entry.get('levelname') == 'INFO'
    assert log_entry.get('name') == 'LiteLLM'


def test_get_uvicorn_json_log_config_litellm_suppressed():
    """Test that LiteLLM loggers use NullHandler when LOG_JSON=false."""
    with mock.patch.dict(os.environ, {'LOG_JSON': 'false'}, clear=False):
        import openhands.core.logger

        importlib.reload(openhands.core.logger)
        config = openhands.core.logger.get_uvicorn_json_log_config()

    assert 'LiteLLM' in config['loggers']
    assert config['loggers']['LiteLLM']['handlers'] == ['null']
    assert config['loggers']['LiteLLM']['level'] == 'CRITICAL'
    assert config['loggers']['LiteLLM']['propagate'] is False
    assert 'null' in config['handlers']
    assert config['handlers']['null']['class'] == 'logging.NullHandler'


def test_get_uvicorn_json_log_config_litellm_json_enabled():
    """Test that LiteLLM loggers use JSON handler to stdout when LOG_JSON=true."""
    with mock.patch.dict(os.environ, {'LOG_JSON': 'true'}, clear=False):
        import openhands.core.logger

        importlib.reload(openhands.core.logger)
        config = openhands.core.logger.get_uvicorn_json_log_config()

    assert 'LiteLLM' in config['loggers']
    assert config['loggers']['LiteLLM']['handlers'] == ['litellm_json']
    assert config['loggers']['LiteLLM']['level'] == 'INFO'
    assert config['loggers']['LiteLLM']['propagate'] is False
    assert 'litellm_json' in config['handlers']
    assert config['handlers']['litellm_json']['stream'] == 'ext://sys.stdout'
    assert config['handlers']['litellm_json']['formatter'] == 'json'
