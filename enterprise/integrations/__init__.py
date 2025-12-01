"""Enterprise integrations package.

This module ensures that all enterprise callback processors are registered
with the discriminated union system used by Pydantic for validation.
"""

# Import all enterprise callback processors to register them
from integrations.slack.slack_v1_callback_processor import SlackV1CallbackProcessor  # noqa: F401

__all__ = [
    'SlackV1CallbackProcessor',
]
