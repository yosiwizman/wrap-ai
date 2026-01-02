"""Unit tests for GitlabWebhookStore."""

import pytest
from integrations.types import GitLabResourceType
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from storage.base import Base
from storage.gitlab_webhook import GitlabWebhook
from storage.gitlab_webhook_store import GitlabWebhookStore


@pytest.fixture
async def async_engine():
    """Create an async SQLite engine for testing."""
    engine = create_async_engine(
        'sqlite+aiosqlite:///:memory:',
        poolclass=StaticPool,
        connect_args={'check_same_thread': False},
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def async_session_maker(async_engine):
    """Create an async session maker for testing."""
    return async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def webhook_store(async_session_maker):
    """Create a GitlabWebhookStore instance for testing."""
    return GitlabWebhookStore(a_session_maker=async_session_maker)


@pytest.fixture
async def sample_webhooks(async_session_maker):
    """Create sample webhook records for testing."""
    async with async_session_maker() as session:
        # Create webhooks for user_1
        webhook1 = GitlabWebhook(
            project_id='project-1',
            group_id=None,
            user_id='user_1',
            webhook_exists=True,
            webhook_url='https://example.com/webhook',
            webhook_secret='secret-1',
            webhook_uuid='uuid-1',
        )
        webhook2 = GitlabWebhook(
            project_id='project-2',
            group_id=None,
            user_id='user_1',
            webhook_exists=True,
            webhook_url='https://example.com/webhook',
            webhook_secret='secret-2',
            webhook_uuid='uuid-2',
        )
        webhook3 = GitlabWebhook(
            project_id=None,
            group_id='group-1',
            user_id='user_1',
            webhook_exists=False,  # Already marked for reinstallation
            webhook_url='https://example.com/webhook',
            webhook_secret='secret-3',
            webhook_uuid='uuid-3',
        )

        # Create webhook for user_2
        webhook4 = GitlabWebhook(
            project_id='project-3',
            group_id=None,
            user_id='user_2',
            webhook_exists=True,
            webhook_url='https://example.com/webhook',
            webhook_secret='secret-4',
            webhook_uuid='uuid-4',
        )

        session.add_all([webhook1, webhook2, webhook3, webhook4])
        await session.commit()

        # Refresh to get IDs (outside of begin() context)
        await session.refresh(webhook1)
        await session.refresh(webhook2)
        await session.refresh(webhook3)
        await session.refresh(webhook4)

    return [webhook1, webhook2, webhook3, webhook4]


class TestMarkWebhookForReinstallation:
    """Test cases for mark_webhook_for_reinstallation method."""

    @pytest.mark.asyncio
    async def test_mark_webhooks_for_user_with_multiple_webhooks(
        self, webhook_store, async_session_maker, sample_webhooks
    ):
        """Test marking multiple webhooks for reinstallation for a user."""
        # Arrange
        user_id = 'user_1'
        expected_count = 3  # user_1 has 3 webhooks

        # Act
        webhooks_marked = await webhook_store.mark_webhook_for_reinstallation(user_id)

        # Assert
        assert webhooks_marked == expected_count

        # Verify all webhooks for user_1 are marked as webhook_exists=False
        async with async_session_maker() as session:
            result = await session.execute(
                select(GitlabWebhook).where(GitlabWebhook.user_id == user_id)
            )
            user_webhooks = result.scalars().all()

            assert len(user_webhooks) == expected_count
            for webhook in user_webhooks:
                assert webhook.webhook_exists is False

            # Verify webhooks for other users are not affected
            result_other = await session.execute(
                select(GitlabWebhook).where(GitlabWebhook.user_id == 'user_2')
            )
            other_webhooks = result_other.scalars().all()
            assert len(other_webhooks) == 1
            assert other_webhooks[0].webhook_exists is True

    @pytest.mark.asyncio
    async def test_mark_webhooks_for_user_with_single_webhook(
        self, webhook_store, async_session_maker, sample_webhooks
    ):
        """Test marking a single webhook for reinstallation."""
        # Arrange
        user_id = 'user_2'
        expected_count = 1

        # Act
        webhooks_marked = await webhook_store.mark_webhook_for_reinstallation(user_id)

        # Assert
        assert webhooks_marked == expected_count

        # Verify the webhook is marked
        async with async_session_maker() as session:
            result = await session.execute(
                select(GitlabWebhook).where(GitlabWebhook.user_id == user_id)
            )
            user_webhooks = result.scalars().all()

            assert len(user_webhooks) == expected_count
            assert user_webhooks[0].webhook_exists is False

    @pytest.mark.asyncio
    async def test_mark_webhooks_for_user_with_no_webhooks(
        self, webhook_store, async_session_maker
    ):
        """Test marking webhooks for a user with no existing webhooks."""
        # Arrange
        user_id = 'user_with_no_webhooks'

        # Act
        webhooks_marked = await webhook_store.mark_webhook_for_reinstallation(user_id)

        # Assert
        assert webhooks_marked == 0

    @pytest.mark.asyncio
    async def test_mark_webhooks_only_affects_target_user(
        self, webhook_store, async_session_maker, sample_webhooks
    ):
        """Test that marking webhooks only affects the specified user."""
        # Arrange
        target_user_id = 'user_1'
        other_user_id = 'user_2'

        # Act
        await webhook_store.mark_webhook_for_reinstallation(target_user_id)

        # Assert
        async with async_session_maker() as session:
            # Verify target user's webhooks are marked
            target_result = await session.execute(
                select(GitlabWebhook).where(GitlabWebhook.user_id == target_user_id)
            )
            target_webhooks = target_result.scalars().all()
            for webhook in target_webhooks:
                assert webhook.webhook_exists is False

            # Verify other user's webhooks are unchanged
            other_result = await session.execute(
                select(GitlabWebhook).where(GitlabWebhook.user_id == other_user_id)
            )
            other_webhooks = other_result.scalars().all()
            assert len(other_webhooks) == 1
            assert other_webhooks[0].webhook_exists is True

    @pytest.mark.asyncio
    async def test_mark_webhooks_includes_already_marked_webhooks(
        self, webhook_store, async_session_maker, sample_webhooks
    ):
        """Test that webhooks already marked for reinstallation are still counted."""
        # Arrange
        user_id = 'user_1'
        # user_1 has 3 webhooks, one already has webhook_exists=False

        # Act
        webhooks_marked = await webhook_store.mark_webhook_for_reinstallation(user_id)

        # Assert
        # Should still return 3 (all webhooks for the user)
        assert webhooks_marked == 3

        # Verify all are now False
        async with async_session_maker() as session:
            result = await session.execute(
                select(GitlabWebhook).where(GitlabWebhook.user_id == user_id)
            )
            user_webhooks = result.scalars().all()

            for webhook in user_webhooks:
                assert webhook.webhook_exists is False


class TestGetWebhookByResourceOnly:
    """Test cases for get_webhook_by_resource_only method."""

    @pytest.mark.asyncio
    async def test_get_project_webhook_by_resource_only(
        self, webhook_store, async_session_maker, sample_webhooks
    ):
        """Test getting a project webhook by resource ID without user_id filter."""
        # Arrange
        resource_type = GitLabResourceType.PROJECT
        resource_id = 'project-1'

        # Act
        webhook = await webhook_store.get_webhook_by_resource_only(
            resource_type, resource_id
        )

        # Assert
        assert webhook is not None
        assert webhook.project_id == resource_id
        assert webhook.user_id == 'user_1'

    @pytest.mark.asyncio
    async def test_get_group_webhook_by_resource_only(
        self, webhook_store, async_session_maker, sample_webhooks
    ):
        """Test getting a group webhook by resource ID without user_id filter."""
        # Arrange
        resource_type = GitLabResourceType.GROUP
        resource_id = 'group-1'

        # Act
        webhook = await webhook_store.get_webhook_by_resource_only(
            resource_type, resource_id
        )

        # Assert
        assert webhook is not None
        assert webhook.group_id == resource_id
        assert webhook.user_id == 'user_1'

    @pytest.mark.asyncio
    async def test_get_webhook_by_resource_only_not_found(
        self, webhook_store, async_session_maker
    ):
        """Test getting a webhook that doesn't exist."""
        # Arrange
        resource_type = GitLabResourceType.PROJECT
        resource_id = 'non-existent-project'

        # Act
        webhook = await webhook_store.get_webhook_by_resource_only(
            resource_type, resource_id
        )

        # Assert
        assert webhook is None

    @pytest.mark.asyncio
    async def test_get_webhook_by_resource_only_organization_wide(
        self, webhook_store, async_session_maker, sample_webhooks
    ):
        """Test that webhook lookup works regardless of which user originally created it."""
        # Arrange
        resource_type = GitLabResourceType.PROJECT
        resource_id = 'project-3'  # Created by user_2

        # Act
        webhook = await webhook_store.get_webhook_by_resource_only(
            resource_type, resource_id
        )

        # Assert
        assert webhook is not None
        assert webhook.project_id == resource_id
        # Should find webhook even though it was created by a different user
        assert webhook.user_id == 'user_2'


class TestResetWebhookForReinstallationByResource:
    """Test cases for reset_webhook_for_reinstallation_by_resource method."""

    @pytest.mark.asyncio
    async def test_reset_project_webhook_by_resource(
        self, webhook_store, async_session_maker, sample_webhooks
    ):
        """Test resetting a project webhook by resource without user_id filter."""
        # Arrange
        resource_type = GitLabResourceType.PROJECT
        resource_id = 'project-1'
        updating_user_id = 'user_2'  # Different user can reset it

        # Act
        result = await webhook_store.reset_webhook_for_reinstallation_by_resource(
            resource_type, resource_id, updating_user_id
        )

        # Assert
        assert result is True

        # Verify webhook was reset
        async with async_session_maker() as session:
            result_query = await session.execute(
                select(GitlabWebhook).where(GitlabWebhook.project_id == resource_id)
            )
            webhook = result_query.scalars().first()
            assert webhook.webhook_exists is False
            assert webhook.webhook_uuid is None
            assert (
                webhook.user_id == updating_user_id
            )  # Updated to track who modified it

    @pytest.mark.asyncio
    async def test_reset_group_webhook_by_resource(
        self, webhook_store, async_session_maker, sample_webhooks
    ):
        """Test resetting a group webhook by resource without user_id filter."""
        # Arrange
        resource_type = GitLabResourceType.GROUP
        resource_id = 'group-1'
        updating_user_id = 'user_2'

        # Act
        result = await webhook_store.reset_webhook_for_reinstallation_by_resource(
            resource_type, resource_id, updating_user_id
        )

        # Assert
        assert result is True

        # Verify webhook was reset
        async with async_session_maker() as session:
            result_query = await session.execute(
                select(GitlabWebhook).where(GitlabWebhook.group_id == resource_id)
            )
            webhook = result_query.scalars().first()
            assert webhook.webhook_exists is False
            assert webhook.webhook_uuid is None
            assert webhook.user_id == updating_user_id

    @pytest.mark.asyncio
    async def test_reset_webhook_by_resource_not_found(
        self, webhook_store, async_session_maker
    ):
        """Test resetting a webhook that doesn't exist."""
        # Arrange
        resource_type = GitLabResourceType.PROJECT
        resource_id = 'non-existent-project'
        updating_user_id = 'user_1'

        # Act
        result = await webhook_store.reset_webhook_for_reinstallation_by_resource(
            resource_type, resource_id, updating_user_id
        )

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_reset_webhook_by_resource_organization_wide(
        self, webhook_store, async_session_maker, sample_webhooks
    ):
        """Test that any user can reset a webhook regardless of original creator."""
        # Arrange
        resource_type = GitLabResourceType.PROJECT
        resource_id = 'project-3'  # Created by user_2
        updating_user_id = 'user_1'  # Different user resetting it

        # Act
        result = await webhook_store.reset_webhook_for_reinstallation_by_resource(
            resource_type, resource_id, updating_user_id
        )

        # Assert
        assert result is True

        # Verify webhook was reset and user_id updated
        async with async_session_maker() as session:
            result_query = await session.execute(
                select(GitlabWebhook).where(GitlabWebhook.project_id == resource_id)
            )
            webhook = result_query.scalars().first()
            assert webhook.webhook_exists is False
            assert webhook.user_id == updating_user_id


class TestGetWebhooksByResources:
    """Test cases for get_webhooks_by_resources method."""

    @pytest.mark.asyncio
    async def test_get_webhooks_by_resources_projects_only(
        self, webhook_store, async_session_maker, sample_webhooks
    ):
        """Test bulk fetching webhooks for multiple projects."""
        # Arrange
        project_ids = ['project-1', 'project-2', 'project-3']
        group_ids: list[str] = []

        # Act
        project_map, group_map = await webhook_store.get_webhooks_by_resources(
            project_ids, group_ids
        )

        # Assert
        assert len(project_map) == 3
        assert 'project-1' in project_map
        assert 'project-2' in project_map
        assert 'project-3' in project_map
        assert len(group_map) == 0

    @pytest.mark.asyncio
    async def test_get_webhooks_by_resources_groups_only(
        self, webhook_store, async_session_maker, sample_webhooks
    ):
        """Test bulk fetching webhooks for multiple groups."""
        # Arrange
        project_ids: list[str] = []
        group_ids = ['group-1']

        # Act
        project_map, group_map = await webhook_store.get_webhooks_by_resources(
            project_ids, group_ids
        )

        # Assert
        assert len(project_map) == 0
        assert len(group_map) == 1
        assert 'group-1' in group_map

    @pytest.mark.asyncio
    async def test_get_webhooks_by_resources_mixed(
        self, webhook_store, async_session_maker, sample_webhooks
    ):
        """Test bulk fetching webhooks for both projects and groups."""
        # Arrange
        project_ids = ['project-1', 'project-2']
        group_ids = ['group-1']

        # Act
        project_map, group_map = await webhook_store.get_webhooks_by_resources(
            project_ids, group_ids
        )

        # Assert
        assert len(project_map) == 2
        assert len(group_map) == 1
        assert 'project-1' in project_map
        assert 'project-2' in project_map
        assert 'group-1' in group_map

    @pytest.mark.asyncio
    async def test_get_webhooks_by_resources_empty_lists(
        self, webhook_store, async_session_maker
    ):
        """Test bulk fetching with empty ID lists."""
        # Arrange
        project_ids: list[str] = []
        group_ids: list[str] = []

        # Act
        project_map, group_map = await webhook_store.get_webhooks_by_resources(
            project_ids, group_ids
        )

        # Assert
        assert len(project_map) == 0
        assert len(group_map) == 0

    @pytest.mark.asyncio
    async def test_get_webhooks_by_resources_partial_matches(
        self, webhook_store, async_session_maker, sample_webhooks
    ):
        """Test bulk fetching when some IDs don't exist."""
        # Arrange
        project_ids = ['project-1', 'non-existent-project']
        group_ids = ['group-1', 'non-existent-group']

        # Act
        project_map, group_map = await webhook_store.get_webhooks_by_resources(
            project_ids, group_ids
        )

        # Assert
        assert len(project_map) == 1
        assert 'project-1' in project_map
        assert 'non-existent-project' not in project_map
        assert len(group_map) == 1
        assert 'group-1' in group_map
        assert 'non-existent-group' not in group_map
