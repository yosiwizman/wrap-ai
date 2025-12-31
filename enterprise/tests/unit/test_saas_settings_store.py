from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr
from server.constants import get_default_litellm_model

from openhands.core.config.openhands_config import OpenHandsConfig
from openhands.server.settings import Settings

# Mock the database module before importing
with patch('storage.database.engine'), patch('storage.database.a_engine'):
    from server.constants import (
        LITE_LLM_API_URL,
    )
    from storage.saas_settings_store import SaasSettingsStore
    from storage.user_settings import UserSettings


@pytest.fixture
def mock_github_user():
    with patch(
        'server.auth.token_manager.TokenManager.get_user_info_from_user_id',
        AsyncMock(return_value={'attributes': {'github_id': ['12345']}}),
    ) as mock_github:
        yield mock_github


@pytest.fixture
def mock_config():
    config = MagicMock(spec=OpenHandsConfig)
    config.jwt_secret = SecretStr('test_secret')
    config.file_store = 'google_cloud'
    config.file_store_path = 'bucket'
    return config


@pytest.fixture
def settings_store(session_maker, mock_config):
    store = SaasSettingsStore(
        '5594c7b6-f959-4b81-92e9-b09c206f5081', session_maker, mock_config
    )

    # Patch the load method to read from UserSettings table directly (for testing)
    async def patched_load():
        with store.session_maker() as session:
            user_settings = (
                session.query(UserSettings)
                .filter(UserSettings.keycloak_user_id == store.user_id)
                .first()
            )
            if not user_settings:
                # Return default settings
                return Settings(
                    llm_api_key=SecretStr('test_api_key'),
                    llm_base_url='http://test.url',
                    agent='CodeActAgent',
                    language='en',
                )

            # Decrypt and convert to Settings
            kwargs = {}
            for column in UserSettings.__table__.columns:
                if column.name != 'keycloak_user_id':
                    value = getattr(user_settings, column.name, None)
                    if value is not None:
                        kwargs[column.name] = value

            store._decrypt_kwargs(kwargs)
            settings = Settings(**kwargs)
            settings.email = 'test@example.com'
            settings.email_verified = True
            return settings

    # Patch the store method to write to UserSettings table directly (for testing)
    async def patched_store(item):
        if item:
            # Make a copy of the item without email and email_verified
            item_dict = item.model_dump(context={'expose_secrets': True})
            if 'email' in item_dict:
                del item_dict['email']
            if 'email_verified' in item_dict:
                del item_dict['email_verified']
            if 'secrets_store' in item_dict:
                del item_dict['secrets_store']

            # Continue with the original implementation
            with store.session_maker() as session:
                existing = None
                if item_dict:
                    store._encrypt_kwargs(item_dict)
                    query = session.query(UserSettings).filter(
                        UserSettings.keycloak_user_id == store.user_id
                    )

                    # First check if we have an existing entry in the new table
                    existing = query.first()

                if existing:
                    # Update existing entry
                    for key, value in item_dict.items():
                        if key in existing.__class__.__table__.columns:
                            setattr(existing, key, value)
                    session.merge(existing)
                else:
                    item_dict['keycloak_user_id'] = store.user_id
                    settings = UserSettings(**item_dict)
                    session.add(settings)
                session.commit()

    # Replace the methods with our patched versions
    store.store = patched_store
    store.load = patched_load
    return store


@pytest.mark.asyncio
async def test_store_and_load_keycloak_user(settings_store):
    # Set a UUID-like Keycloak user ID
    settings_store.user_id = '550e8400-e29b-41d4-a716-446655440000'
    settings = Settings(
        llm_api_key=SecretStr('secret_key'),
        llm_base_url=LITE_LLM_API_URL,
        agent='smith',
        email='test@example.com',
        email_verified=True,
    )

    await settings_store.store(settings)

    # Load and verify settings
    loaded_settings = await settings_store.load()
    assert loaded_settings is not None
    assert loaded_settings.llm_api_key.get_secret_value() == 'secret_key'
    assert loaded_settings.agent == 'smith'

    # Verify it was stored in user_settings table with keycloak_user_id
    with settings_store.session_maker() as session:
        stored = (
            session.query(UserSettings)
            .filter(
                UserSettings.keycloak_user_id == '550e8400-e29b-41d4-a716-446655440000'
            )
            .first()
        )
        assert stored is not None
        assert stored.agent == 'smith'


@pytest.mark.asyncio
async def test_load_returns_default_when_not_found(settings_store, session_maker):
    file_store = MagicMock()
    file_store.read.side_effect = FileNotFoundError()

    with (
        patch('storage.saas_settings_store.session_maker', session_maker),
    ):
        loaded_settings = await settings_store.load()
        assert loaded_settings is not None
        assert loaded_settings.language == 'en'
        assert loaded_settings.agent == 'CodeActAgent'
        assert loaded_settings.llm_api_key.get_secret_value() == 'test_api_key'
        assert loaded_settings.llm_base_url == 'http://test.url'


@pytest.mark.asyncio
async def test_encryption(settings_store):
    settings_store.user_id = '5594c7b6-f959-4b81-92e9-b09c206f5081'  # GitHub user ID
    settings = Settings(
        llm_api_key=SecretStr('secret_key'),
        agent='smith',
        llm_base_url=LITE_LLM_API_URL,
        email='test@example.com',
        email_verified=True,
    )
    await settings_store.store(settings)
    with settings_store.session_maker() as session:
        stored = (
            session.query(UserSettings)
            .filter(
                UserSettings.keycloak_user_id == '5594c7b6-f959-4b81-92e9-b09c206f5081'
            )
            .first()
        )
        # The stored key should be encrypted
        assert stored.llm_api_key != 'secret_key'
        # But we should be able to decrypt it when loading
        loaded_settings = await settings_store.load()
        assert loaded_settings.llm_api_key.get_secret_value() == 'secret_key'


@pytest.mark.asyncio
async def test_update_settings_with_litellm_default_preserves_custom_model(
    settings_store, mock_litellm_api, session_maker
):
    # Arrange: User has a custom LLM model set
    custom_model = 'anthropic/claude-3-5-sonnet-20241022'
    settings = Settings(llm_model=custom_model)

    with (
        patch(
            'server.auth.token_manager.TokenManager.get_user_info_from_user_id',
            AsyncMock(return_value={'email': 'user@example.com'}),
        ),
        patch('storage.saas_settings_store.session_maker', session_maker),
    ):
        # Act: Update settings with LiteLLM defaults
        updated_settings = await settings_store.update_settings_with_litellm_default(
            settings
        )

    # Assert: Custom model is preserved
    assert updated_settings is not None
    assert updated_settings.llm_model == custom_model
    assert updated_settings.agent == 'CodeActAgent'
    assert updated_settings.llm_api_key is not None

    # Assert: LiteLLM metadata contains user's custom model
    call_args = mock_litellm_api.return_value.__aenter__.return_value.post.call_args[1]
    assert call_args['json']['metadata']['model'] == custom_model


@pytest.mark.asyncio
async def test_update_settings_with_litellm_default_uses_default_when_no_model(
    settings_store, mock_litellm_api, session_maker
):
    # Arrange: User has no model set (new user scenario)
    settings = Settings()

    with (
        patch(
            'server.auth.token_manager.TokenManager.get_user_info_from_user_id',
            AsyncMock(return_value={'email': 'newuser@example.com'}),
        ),
        patch('storage.saas_settings_store.session_maker', session_maker),
    ):
        # Act: Update settings with LiteLLM defaults
        updated_settings = await settings_store.update_settings_with_litellm_default(
            settings
        )

    # Assert: Default model is assigned
    assert updated_settings is not None
    expected_default = get_default_litellm_model()
    assert updated_settings.llm_model == expected_default
    assert updated_settings.agent == 'CodeActAgent'

    # Assert: LiteLLM metadata contains default model
    call_args = mock_litellm_api.return_value.__aenter__.return_value.post.call_args[1]
    assert call_args['json']['metadata']['model'] == expected_default


@pytest.mark.asyncio
async def test_update_settings_with_litellm_default_handles_empty_string_model(
    settings_store, mock_litellm_api, session_maker
):
    # Arrange: User has empty string as model (edge case)
    settings = Settings(llm_model='')

    with (
        patch(
            'server.auth.token_manager.TokenManager.get_user_info_from_user_id',
            AsyncMock(return_value={'email': 'user@example.com'}),
        ),
        patch('storage.saas_settings_store.session_maker', session_maker),
    ):
        # Act: Update settings with LiteLLM defaults
        updated_settings = await settings_store.update_settings_with_litellm_default(
            settings
        )

    # Assert: Default model is used (empty string treated as no model)
    assert updated_settings is not None
    expected_default = get_default_litellm_model()
    assert updated_settings.llm_model == expected_default


@pytest.mark.asyncio
async def test_update_settings_with_litellm_default_handles_whitespace_model(
    settings_store, mock_litellm_api, session_maker
):
    # Arrange: User has whitespace-only model (edge case)
    settings = Settings(llm_model='   ')

    with (
        patch(
            'server.auth.token_manager.TokenManager.get_user_info_from_user_id',
            AsyncMock(return_value={'email': 'user@example.com'}),
        ),
        patch('storage.saas_settings_store.session_maker', session_maker),
    ):
        # Act: Update settings with LiteLLM defaults
        updated_settings = await settings_store.update_settings_with_litellm_default(
            settings
        )

    # Assert: Default model is used (whitespace treated as no model)
    assert updated_settings is not None
    expected_default = get_default_litellm_model()
    assert updated_settings.llm_model == expected_default


@pytest.mark.asyncio
async def test_update_settings_with_litellm_default_preserves_custom_api_key(
    settings_store, mock_litellm_api, session_maker
):
    # Arrange: User has a custom API key and custom model (so has_custom=True)
    custom_api_key = 'sk-custom-user-api-key-12345'
    custom_model = 'gpt-4'
    settings = Settings(llm_model=custom_model, llm_api_key=SecretStr(custom_api_key))

    with (
        patch(
            'server.auth.token_manager.TokenManager.get_user_info_from_user_id',
            AsyncMock(return_value={'email': 'user@example.com'}),
        ),
        patch('storage.saas_settings_store.session_maker', session_maker),
    ):
        # Act: Update settings with LiteLLM defaults
        updated_settings = await settings_store.update_settings_with_litellm_default(
            settings
        )

    # Assert: Custom API key is preserved when user has custom settings
    assert updated_settings is not None
    assert updated_settings.llm_api_key.get_secret_value() == custom_api_key
    assert updated_settings.llm_api_key.get_secret_value() != 'test_api_key'


@pytest.mark.asyncio
async def test_update_settings_with_litellm_default_preserves_custom_base_url(
    settings_store, mock_litellm_api, session_maker
):
    # Arrange: User has a custom base URL
    custom_base_url = 'https://api.custom-llm-provider.com/v1'
    settings = Settings(llm_base_url=custom_base_url)

    with (
        patch(
            'server.auth.token_manager.TokenManager.get_user_info_from_user_id',
            AsyncMock(return_value={'email': 'user@example.com'}),
        ),
        patch('storage.saas_settings_store.session_maker', session_maker),
    ):
        # Act: Update settings with LiteLLM defaults
        updated_settings = await settings_store.update_settings_with_litellm_default(
            settings
        )

    # Assert: Custom base URL is preserved
    assert updated_settings is not None
    assert updated_settings.llm_base_url == custom_base_url
    assert updated_settings.llm_base_url != LITE_LLM_API_URL


@pytest.mark.asyncio
async def test_update_settings_with_litellm_default_preserves_custom_api_key_and_base_url(
    settings_store, mock_litellm_api, session_maker
):
    # Arrange: User has both custom API key and base URL
    custom_api_key = 'sk-custom-user-api-key-67890'
    custom_base_url = 'https://api.another-llm-provider.com/v1'
    custom_model = 'openai/gpt-4'
    settings = Settings(
        llm_model=custom_model,
        llm_api_key=SecretStr(custom_api_key),
        llm_base_url=custom_base_url,
    )

    with (
        patch(
            'server.auth.token_manager.TokenManager.get_user_info_from_user_id',
            AsyncMock(return_value={'email': 'user@example.com'}),
        ),
        patch('storage.saas_settings_store.session_maker', session_maker),
    ):
        # Act: Update settings with LiteLLM defaults
        updated_settings = await settings_store.update_settings_with_litellm_default(
            settings
        )

    # Assert: All custom settings are preserved
    assert updated_settings is not None
    assert updated_settings.llm_model == custom_model
    assert updated_settings.llm_api_key.get_secret_value() == custom_api_key
    assert updated_settings.llm_base_url == custom_base_url


@pytest.mark.asyncio
async def test_update_settings_with_litellm_default_uses_default_api_key_when_none(
    settings_store, mock_litellm_api, session_maker
):
    # Arrange: User has no API key set
    settings = Settings(llm_api_key=None)

    with (
        patch(
            'server.auth.token_manager.TokenManager.get_user_info_from_user_id',
            AsyncMock(return_value={'email': 'user@example.com'}),
        ),
        patch('storage.saas_settings_store.session_maker', session_maker),
    ):
        # Act: Update settings with LiteLLM defaults
        updated_settings = await settings_store.update_settings_with_litellm_default(
            settings
        )

    # Assert: Default LiteLLM API key is assigned
    assert updated_settings is not None
    assert updated_settings.llm_api_key is not None
    assert updated_settings.llm_api_key.get_secret_value() == 'test_api_key'


@pytest.mark.asyncio
async def test_update_settings_with_litellm_default_uses_default_base_url_when_none(
    settings_store, mock_litellm_api, session_maker
):
    # Arrange: User has no base URL set
    settings = Settings(llm_base_url=None)

    with (
        patch(
            'server.auth.token_manager.TokenManager.get_user_info_from_user_id',
            AsyncMock(return_value={'email': 'user@example.com'}),
        ),
        patch('storage.saas_settings_store.session_maker', session_maker),
        patch('storage.saas_settings_store.LITE_LLM_API_URL', 'http://test.url'),
    ):
        # Act: Update settings with LiteLLM defaults
        updated_settings = await settings_store.update_settings_with_litellm_default(
            settings
        )

    # Assert: Default LiteLLM base URL is assigned (using mocked value)
    assert updated_settings is not None
    assert updated_settings.llm_base_url == 'http://test.url'


@pytest.mark.asyncio
async def test_update_settings_with_litellm_default_handles_empty_api_key(
    settings_store, mock_litellm_api, session_maker
):
    # Arrange: User has empty string as API key (edge case)
    settings = Settings(llm_api_key=SecretStr(''))

    with (
        patch(
            'server.auth.token_manager.TokenManager.get_user_info_from_user_id',
            AsyncMock(return_value={'email': 'user@example.com'}),
        ),
        patch('storage.saas_settings_store.session_maker', session_maker),
    ):
        # Act: Update settings with LiteLLM defaults
        updated_settings = await settings_store.update_settings_with_litellm_default(
            settings
        )

    # Assert: Default API key is used (empty string treated as no key)
    assert updated_settings is not None
    assert updated_settings.llm_api_key.get_secret_value() == 'test_api_key'


@pytest.mark.asyncio
async def test_update_settings_with_litellm_default_handles_empty_base_url(
    settings_store, mock_litellm_api, session_maker
):
    # Arrange: User has empty string as base URL (edge case)
    settings = Settings(llm_base_url='')

    with (
        patch(
            'server.auth.token_manager.TokenManager.get_user_info_from_user_id',
            AsyncMock(return_value={'email': 'user@example.com'}),
        ),
        patch('storage.saas_settings_store.session_maker', session_maker),
        patch('storage.saas_settings_store.LITE_LLM_API_URL', 'http://test.url'),
    ):
        # Act: Update settings with LiteLLM defaults
        updated_settings = await settings_store.update_settings_with_litellm_default(
            settings
        )

    # Assert: Default base URL is used (empty string treated as no URL)
    assert updated_settings is not None
    assert updated_settings.llm_base_url == 'http://test.url'


@pytest.mark.asyncio
async def test_update_settings_with_litellm_default_handles_whitespace_api_key(
    settings_store, mock_litellm_api, session_maker
):
    # Arrange: User has whitespace-only API key (edge case)
    settings = Settings(llm_api_key=SecretStr('   '))

    with (
        patch(
            'server.auth.token_manager.TokenManager.get_user_info_from_user_id',
            AsyncMock(return_value={'email': 'user@example.com'}),
        ),
        patch('storage.saas_settings_store.session_maker', session_maker),
    ):
        # Act: Update settings with LiteLLM defaults
        updated_settings = await settings_store.update_settings_with_litellm_default(
            settings
        )

    # Assert: Default API key is used (whitespace treated as no key)
    assert updated_settings is not None
    assert updated_settings.llm_api_key.get_secret_value() == 'test_api_key'


@pytest.mark.asyncio
async def test_update_settings_with_litellm_default_handles_whitespace_base_url(
    settings_store, mock_litellm_api, session_maker
):
    # Arrange: User has whitespace-only base URL (edge case)
    settings = Settings(llm_base_url='   ')

    with (
        patch(
            'server.auth.token_manager.TokenManager.get_user_info_from_user_id',
            AsyncMock(return_value={'email': 'user@example.com'}),
        ),
        patch('storage.saas_settings_store.session_maker', session_maker),
        patch('storage.saas_settings_store.LITE_LLM_API_URL', 'http://test.url'),
    ):
        # Act: Update settings with LiteLLM defaults
        updated_settings = await settings_store.update_settings_with_litellm_default(
            settings
        )

    # Assert: Default base URL is used (whitespace treated as no URL)
    assert updated_settings is not None
    assert updated_settings.llm_base_url == 'http://test.url'


# Tests for version migration and helper methods


@pytest.mark.asyncio
async def test_has_custom_settings_with_custom_base_url(settings_store):
    # Arrange: User with custom base URL (BYOR)
    with patch('storage.saas_settings_store.LITE_LLM_API_URL', 'http://default.url'):
        settings = Settings(llm_base_url='http://custom.url')

        # Act: Check if has custom settings
        has_custom = settings_store._has_custom_settings(settings, None)

        # Assert: Custom base URL detected
        assert has_custom is True


@pytest.mark.asyncio
async def test_has_custom_settings_with_default_base_url(settings_store):
    # Arrange: User with default base URL
    with patch('storage.saas_settings_store.LITE_LLM_API_URL', 'http://default.url'):
        settings = Settings(llm_base_url='http://default.url')

        # Act: Check if has custom settings
        has_custom = settings_store._has_custom_settings(settings, None)

        # Assert: No custom settings (no model set)
        assert has_custom is False


@pytest.mark.asyncio
async def test_has_custom_settings_with_no_model(settings_store):
    # Arrange: User with no model set
    with patch('storage.saas_settings_store.LITE_LLM_API_URL', 'http://default.url'):
        settings = Settings(llm_model=None, llm_base_url='http://default.url')

        # Act: Check if has custom settings
        has_custom = settings_store._has_custom_settings(settings, None)

        # Assert: No custom settings (using defaults)
        assert has_custom is False


@pytest.mark.asyncio
async def test_has_custom_settings_with_empty_model(settings_store):
    # Arrange: User with empty model
    with patch('storage.saas_settings_store.LITE_LLM_API_URL', 'http://default.url'):
        settings = Settings(llm_model='', llm_base_url='http://default.url')

        # Act: Check if has custom settings
        has_custom = settings_store._has_custom_settings(settings, None)

        # Assert: No custom settings (empty treated as no model)
        assert has_custom is False


@pytest.mark.asyncio
async def test_has_custom_settings_with_whitespace_model(settings_store):
    # Arrange: User with whitespace-only model
    with patch('storage.saas_settings_store.LITE_LLM_API_URL', 'http://default.url'):
        settings = Settings(llm_model='   ', llm_base_url='http://default.url')

        # Act: Check if has custom settings
        has_custom = settings_store._has_custom_settings(settings, None)

        # Assert: No custom settings (whitespace treated as no model)
        assert has_custom is False


@pytest.mark.asyncio
async def test_has_custom_settings_with_custom_model(settings_store):
    # Arrange: User with custom model
    with patch('storage.saas_settings_store.LITE_LLM_API_URL', 'http://default.url'):
        settings = Settings(llm_model='gpt-4', llm_base_url='http://default.url')

        # Act: Check if has custom settings
        has_custom = settings_store._has_custom_settings(settings, None)

        # Assert: Custom model detected
        assert has_custom is True


@pytest.mark.asyncio
async def test_has_custom_settings_matches_old_default_model(settings_store):
    # Arrange: User with old version and model matching old default
    with (
        patch('storage.saas_settings_store.LITE_LLM_API_URL', 'http://default.url'),
        patch('server.constants.CURRENT_USER_SETTINGS_VERSION', 5),
        patch(
            'server.constants.USER_SETTINGS_VERSION_TO_MODEL',
            {1: 'claude-3-5-sonnet-20241022'},
        ),
    ):
        settings = Settings(
            llm_model='litellm_proxy/prod/claude-3-5-sonnet-20241022',
            llm_base_url='http://default.url',
        )

        # Act: Check if has custom settings
        has_custom = settings_store._has_custom_settings(settings, 1)

        # Assert: Matches old default, so not custom
        assert has_custom is False


@pytest.mark.asyncio
async def test_has_custom_settings_matches_old_default_by_base_name(settings_store):
    # Arrange: User with old version and model matching old default by base name
    with (
        patch('storage.saas_settings_store.LITE_LLM_API_URL', 'http://default.url'),
        patch('server.constants.CURRENT_USER_SETTINGS_VERSION', 5),
        patch(
            'server.constants.USER_SETTINGS_VERSION_TO_MODEL',
            {1: 'claude-3-5-sonnet-20241022'},
        ),
    ):
        settings = Settings(
            llm_model='anthropic/claude-3-5-sonnet-20241022',
            llm_base_url='http://default.url',
        )

        # Act: Check if has custom settings
        has_custom = settings_store._has_custom_settings(settings, 1)

        # Assert: Matches old default by base name, so not custom
        assert has_custom is False


@pytest.mark.asyncio
async def test_has_custom_settings_with_old_version_but_custom_model(settings_store):
    # Arrange: User with old version but custom model
    with (
        patch('storage.saas_settings_store.LITE_LLM_API_URL', 'http://default.url'),
        patch('server.constants.CURRENT_USER_SETTINGS_VERSION', 5),
        patch(
            'server.constants.USER_SETTINGS_VERSION_TO_MODEL',
            {1: 'claude-3-5-sonnet-20241022'},
        ),
    ):
        settings = Settings(llm_model='gpt-4', llm_base_url='http://default.url')

        # Act: Check if has custom settings
        has_custom = settings_store._has_custom_settings(settings, 1)

        # Assert: Custom model detected
        assert has_custom is True


@pytest.mark.asyncio
async def test_has_custom_settings_with_current_version(settings_store):
    # Arrange: User with current version
    with (
        patch('storage.saas_settings_store.LITE_LLM_API_URL', 'http://default.url'),
        patch('server.constants.CURRENT_USER_SETTINGS_VERSION', 5),
        patch(
            'server.constants.USER_SETTINGS_VERSION_TO_MODEL',
            {1: 'claude-3-5-sonnet-20241022', 5: 'claude-opus-4-5-20251101'},
        ),
    ):
        settings = Settings(
            llm_model='claude-3-5-sonnet-20241022', llm_base_url='http://default.url'
        )

        # Act: Check if has custom settings
        has_custom = settings_store._has_custom_settings(settings, 5)

        # Assert: Current version, so model is custom (not old default)
        assert has_custom is True


@pytest.mark.asyncio
async def test_has_custom_settings_with_none_version(settings_store):
    # Arrange: User with no version
    with patch('storage.saas_settings_store.LITE_LLM_API_URL', 'http://default.url'):
        settings = Settings(
            llm_model='claude-3-5-sonnet-20241022', llm_base_url='http://default.url'
        )

        # Act: Check if has custom settings
        has_custom = settings_store._has_custom_settings(settings, None)

        # Assert: No version, so model is custom
        assert has_custom is True


@pytest.mark.asyncio
async def test_has_custom_settings_with_invalid_version(settings_store):
    # Arrange: User with invalid version
    with (
        patch('storage.saas_settings_store.LITE_LLM_API_URL', 'http://default.url'),
        patch('server.constants.CURRENT_USER_SETTINGS_VERSION', 5),
        patch(
            'server.constants.USER_SETTINGS_VERSION_TO_MODEL',
            {1: 'claude-3-5-sonnet-20241022'},
        ),
    ):
        settings = Settings(
            llm_model='claude-3-5-sonnet-20241022', llm_base_url='http://default.url'
        )

        # Act: Check if has custom settings
        has_custom = settings_store._has_custom_settings(settings, 99)

        # Assert: Invalid version, so model is custom
        assert has_custom is True


@pytest.mark.asyncio
async def test_has_custom_settings_normalizes_whitespace(settings_store):
    # Arrange: Settings with whitespace in values
    with patch('storage.saas_settings_store.LITE_LLM_API_URL', 'http://default.url'):
        settings = Settings(
            llm_model='  claude-3-5-sonnet-20241022  ',
            llm_base_url='  http://default.url  ',
        )

        # Act: Check if has custom settings
        has_custom = settings_store._has_custom_settings(settings, None)

        # Assert: Whitespace is normalized, custom model detected
        assert has_custom is True


@pytest.mark.asyncio
async def test_update_settings_upgrades_user_from_old_defaults(
    settings_store, mock_litellm_api, session_maker
):
    # Arrange: User with old version using old defaults
    old_version = 1
    old_model = 'litellm_proxy/prod/claude-3-5-sonnet-20241022'
    settings = Settings(llm_model=old_model, llm_base_url=LITE_LLM_API_URL)

    # Use a consistent test URL
    test_base_url = 'http://test.url'

    with (
        patch('storage.saas_settings_store.session_maker', session_maker),
        patch(
            'server.constants.USER_SETTINGS_VERSION_TO_MODEL',
            {1: 'claude-3-5-sonnet-20241022', 5: 'claude-opus-4-5-20251101'},
        ),
        patch(
            'storage.saas_settings_store.USER_SETTINGS_VERSION_TO_MODEL',
            {1: 'claude-3-5-sonnet-20241022', 5: 'claude-opus-4-5-20251101'},
        ),
        patch('server.constants.CURRENT_USER_SETTINGS_VERSION', 5),
        patch('storage.saas_settings_store.CURRENT_USER_SETTINGS_VERSION', 5),
        patch('storage.saas_settings_store.LITE_LLM_API_URL', test_base_url),
        patch(
            'storage.saas_settings_store.get_default_litellm_model',
            return_value='litellm_proxy/prod/claude-opus-4-5-20251101',
        ),
        patch(
            'server.auth.token_manager.TokenManager.get_user_info_from_user_id',
            AsyncMock(return_value={'email': 'user@example.com'}),
        ),
    ):
        # Create existing user settings with old version
        with session_maker() as session:
            existing_settings = UserSettings(
                keycloak_user_id=settings_store.user_id,
                user_version=old_version,
                llm_model=old_model,
                llm_base_url=test_base_url,
            )
            session.add(existing_settings)
            session.commit()

        # Update settings to use test_base_url
        # Set user_version to match the database so _has_custom_settings can detect old defaults
        settings = Settings(
            llm_model=old_model, llm_base_url=test_base_url, user_version=old_version
        )

        # Act: Update settings
        updated_settings = await settings_store.update_settings_with_litellm_default(
            settings
        )

        # Assert: Settings upgraded to new defaults
        assert updated_settings is not None
        assert (
            updated_settings.llm_model == 'litellm_proxy/prod/claude-opus-4-5-20251101'
        )
        assert updated_settings.llm_base_url == test_base_url


@pytest.mark.asyncio
async def test_update_settings_preserves_custom_settings_during_upgrade(
    settings_store, mock_litellm_api, session_maker
):
    # Arrange: User with old version but custom settings
    old_version = 1
    custom_model = 'gpt-4'
    custom_base_url = 'http://custom.url'
    settings = Settings(llm_model=custom_model, llm_base_url=custom_base_url)

    with (
        patch('storage.saas_settings_store.session_maker', session_maker),
        patch(
            'server.constants.USER_SETTINGS_VERSION_TO_MODEL',
            {1: 'claude-3-5-sonnet-20241022'},
        ),
        patch(
            'server.auth.token_manager.TokenManager.get_user_info_from_user_id',
            AsyncMock(return_value={'email': 'user@example.com'}),
        ),
    ):
        # Create existing user settings with old version
        with session_maker() as session:
            existing_settings = UserSettings(
                keycloak_user_id=settings_store.user_id,
                user_version=old_version,
                llm_model=custom_model,
                llm_base_url=custom_base_url,
            )
            session.add(existing_settings)
            session.commit()

        # Act: Update settings
        updated_settings = await settings_store.update_settings_with_litellm_default(
            settings
        )

        # Assert: Custom settings preserved
        assert updated_settings is not None
        assert updated_settings.llm_model == custom_model
        assert updated_settings.llm_base_url == custom_base_url


@pytest.mark.asyncio
async def test_update_settings_migrates_billing_margin_v3_to_v4(
    settings_store, mock_litellm_api, session_maker
):
    # Arrange: User with version 3 and billing margin
    old_version = 3
    billing_margin = 2.0
    max_budget = 10.0
    spend = 5.0

    settings = Settings()

    mock_get_response = AsyncMock()
    mock_get_response.is_success = True
    mock_get_response.json = MagicMock(
        return_value={'user_info': {'max_budget': max_budget, 'spend': spend}}
    )

    mock_post_response = AsyncMock()
    mock_post_response.is_success = True
    mock_post_response.json = MagicMock(return_value={'key': 'test_api_key'})

    with (
        patch('storage.saas_settings_store.session_maker', session_maker),
        patch(
            'server.auth.token_manager.TokenManager.get_user_info_from_user_id',
            AsyncMock(return_value={'email': 'user@example.com'}),
        ),
        patch('httpx.AsyncClient') as mock_client,
    ):
        mock_client.return_value.__aenter__.return_value.get.return_value = (
            mock_get_response
        )
        mock_client.return_value.__aenter__.return_value.post.return_value = (
            mock_post_response
        )

        # Create existing user settings with version 3 and billing margin
        with session_maker() as session:
            existing_settings = UserSettings(
                keycloak_user_id=settings_store.user_id,
                user_version=old_version,
                billing_margin=billing_margin,
            )
            session.add(existing_settings)
            session.commit()

        # Act: Update settings
        updated_settings = await settings_store.update_settings_with_litellm_default(
            settings
        )

        # Assert: Settings updated
        assert updated_settings is not None

        # Assert: Billing margin applied to budget
        call_args = mock_client.return_value.__aenter__.return_value.post.call_args[1]
        assert call_args['json']['max_budget'] == max_budget * billing_margin
        assert call_args['json']['spend'] == spend * billing_margin

        # Assert: Billing margin reset to 1.0
        with session_maker() as session:
            updated_user_settings = (
                session.query(UserSettings)
                .filter(UserSettings.keycloak_user_id == settings_store.user_id)
                .first()
            )
            assert updated_user_settings.billing_margin == 1.0


@pytest.mark.asyncio
async def test_update_settings_skips_billing_margin_migration_when_already_v4(
    settings_store, mock_litellm_api, session_maker
):
    # Arrange: User with version 4
    version = 4
    billing_margin = 2.0
    max_budget = 10.0
    spend = 5.0

    settings = Settings()

    mock_get_response = AsyncMock()
    mock_get_response.is_success = True
    mock_get_response.json = MagicMock(
        return_value={'user_info': {'max_budget': max_budget, 'spend': spend}}
    )

    mock_post_response = AsyncMock()
    mock_post_response.is_success = True
    mock_post_response.json = MagicMock(return_value={'key': 'test_api_key'})

    with (
        patch('storage.saas_settings_store.session_maker', session_maker),
        patch(
            'server.auth.token_manager.TokenManager.get_user_info_from_user_id',
            AsyncMock(return_value={'email': 'user@example.com'}),
        ),
        patch('httpx.AsyncClient') as mock_client,
    ):
        mock_client.return_value.__aenter__.return_value.get.return_value = (
            mock_get_response
        )
        mock_client.return_value.__aenter__.return_value.post.return_value = (
            mock_post_response
        )

        # Create existing user settings with version 4
        with session_maker() as session:
            existing_settings = UserSettings(
                keycloak_user_id=settings_store.user_id,
                user_version=version,
                billing_margin=billing_margin,
            )
            session.add(existing_settings)
            session.commit()

        # Act: Update settings
        updated_settings = await settings_store.update_settings_with_litellm_default(
            settings
        )

        # Assert: Settings updated
        assert updated_settings is not None

        # Assert: Billing margin NOT applied (version >= 4)
        call_args = mock_client.return_value.__aenter__.return_value.post.call_args[1]
        assert call_args['json']['max_budget'] == max_budget
        assert call_args['json']['spend'] == spend
