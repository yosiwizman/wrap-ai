def _get_stored_conversation_metadata():
    from openhands.app_server.app_conversation.sql_app_conversation_info_service import (
        StoredConversationMetadata as _StoredConversationMetadata,
    )
    return _StoredConversationMetadata

# Lazy import to avoid circular dependency
StoredConversationMetadata = None

def __getattr__(name):
    global StoredConversationMetadata
    if name == 'StoredConversationMetadata':
        if StoredConversationMetadata is None:
            StoredConversationMetadata = _get_stored_conversation_metadata()
        return StoredConversationMetadata
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = ['StoredConversationMetadata']
