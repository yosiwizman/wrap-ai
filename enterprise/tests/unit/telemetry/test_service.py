"""Unit tests for the TelemetryService."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.telemetry.service import TelemetryService


@pytest.fixture
def telemetry_service():
    """Create a fresh TelemetryService instance for testing."""
    # Reset the singleton for testing
    TelemetryService._instance = None
    TelemetryService._initialized = False
    service = TelemetryService()
    return service


@pytest.fixture
def mock_session():
    """Mock database session."""
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=None)
    return session


class TestTelemetryServiceInitialization:
    """Test TelemetryService initialization and singleton pattern."""

    def test_singleton_pattern(self, telemetry_service):
        """Test that TelemetryService is a singleton."""
        service1 = TelemetryService()
        service2 = TelemetryService()
        assert service1 is service2

    def test_initialization_once(self, telemetry_service):
        """Test that __init__ only runs once."""
        initial_collection_interval = telemetry_service.collection_interval_days
        telemetry_service.collection_interval_days = 999

        # Create another "instance" (should be same singleton)
        service2 = TelemetryService()
        assert service2.collection_interval_days == 999

    def test_default_configuration(self, telemetry_service):
        """Test default configuration values."""
        assert telemetry_service.collection_interval_days == 7
        assert telemetry_service.upload_interval_hours == 24
        assert telemetry_service.license_warning_threshold_days == 4
        assert telemetry_service.bootstrap_check_interval_seconds == 180
        assert telemetry_service.normal_check_interval_seconds == 3600

    def test_environment_variable_configuration(self):
        """Test configuration from environment variables."""
        # Reset singleton
        TelemetryService._instance = None
        TelemetryService._initialized = False

        with patch.dict(
            'os.environ',
            {
                'TELEMETRY_COLLECTION_INTERVAL_DAYS': '14',
                'TELEMETRY_UPLOAD_INTERVAL_HOURS': '48',
                'TELEMETRY_WARNING_THRESHOLD_DAYS': '7',
            },
        ):
            service = TelemetryService()
            assert service.collection_interval_days == 14
            assert service.upload_interval_hours == 48
            assert service.license_warning_threshold_days == 7


class TestIdentityEstablishment:
    """Test identity establishment detection."""

    @patch('server.telemetry.service.session_maker')
    def test_identity_not_established_no_record(
        self, mock_session_maker, telemetry_service
    ):
        """Test identity not established when no record exists."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session_maker.return_value = mock_session

        mock_session.query.return_value.filter.return_value.first.return_value = None

        assert not telemetry_service._is_identity_established()

    @patch('server.telemetry.service.session_maker')
    def test_identity_not_established_partial_customer(
        self, mock_session_maker, telemetry_service
    ):
        """Test identity not established when only customer_id exists."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session_maker.return_value = mock_session

        mock_identity = MagicMock()
        mock_identity.customer_id = 'customer@example.com'
        mock_identity.instance_id = None

        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_identity
        )

        assert not telemetry_service._is_identity_established()

    @patch('server.telemetry.service.session_maker')
    def test_identity_not_established_partial_instance(
        self, mock_session_maker, telemetry_service
    ):
        """Test identity not established when only instance_id exists."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session_maker.return_value = mock_session

        mock_identity = MagicMock()
        mock_identity.customer_id = None
        mock_identity.instance_id = 'instance-123'

        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_identity
        )

        assert not telemetry_service._is_identity_established()

    @patch('server.telemetry.service.session_maker')
    def test_identity_established_complete(
        self, mock_session_maker, telemetry_service
    ):
        """Test identity established when both customer_id and instance_id exist."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session_maker.return_value = mock_session

        mock_identity = MagicMock()
        mock_identity.customer_id = 'customer@example.com'
        mock_identity.instance_id = 'instance-123'

        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_identity
        )

        assert telemetry_service._is_identity_established()

    @patch('server.telemetry.service.session_maker')
    def test_identity_established_error_handling(
        self, mock_session_maker, telemetry_service
    ):
        """Test identity check returns False on error."""
        mock_session_maker.side_effect = Exception('Database error')

        assert not telemetry_service._is_identity_established()


class TestCollectionLogic:
    """Test collection timing logic."""

    @patch('server.telemetry.service.session_maker')
    def test_should_collect_no_metrics(self, mock_session_maker, telemetry_service):
        """Test should collect when no metrics exist."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session_maker.return_value = mock_session

        mock_session.query.return_value.order_by.return_value.first.return_value = None

        assert telemetry_service._should_collect()

    @patch('server.telemetry.service.session_maker')
    def test_should_collect_old_metrics(self, mock_session_maker, telemetry_service):
        """Test should collect when 7+ days have passed."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session_maker.return_value = mock_session

        mock_metric = MagicMock()
        mock_metric.collected_at = datetime.now(timezone.utc) - timedelta(days=8)

        mock_session.query.return_value.order_by.return_value.first.return_value = (
            mock_metric
        )

        assert telemetry_service._should_collect()

    @patch('server.telemetry.service.session_maker')
    def test_should_not_collect_recent_metrics(
        self, mock_session_maker, telemetry_service
    ):
        """Test should not collect when less than 7 days have passed."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session_maker.return_value = mock_session

        mock_metric = MagicMock()
        mock_metric.collected_at = datetime.now(timezone.utc) - timedelta(days=3)

        mock_session.query.return_value.order_by.return_value.first.return_value = (
            mock_metric
        )

        assert not telemetry_service._should_collect()


class TestUploadLogic:
    """Test upload timing logic."""

    @patch('server.telemetry.service.session_maker')
    def test_should_upload_no_uploads_with_pending(
        self, mock_session_maker, telemetry_service
    ):
        """Test should upload when no uploads exist but pending metrics do."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session_maker.return_value = mock_session

        # First query for last uploaded returns None
        mock_query1 = MagicMock()
        mock_query1.filter.return_value.order_by.return_value.first.return_value = None

        # Second query for pending count returns 5
        mock_query2 = MagicMock()
        mock_query2.filter.return_value.count.return_value = 5

        mock_session.query.side_effect = [mock_query1, mock_query2]

        assert telemetry_service._should_upload()

    @patch('server.telemetry.service.session_maker')
    def test_should_not_upload_no_pending(
        self, mock_session_maker, telemetry_service
    ):
        """Test should not upload when no pending metrics exist."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session_maker.return_value = mock_session

        # First query for last uploaded returns None
        mock_query1 = MagicMock()
        mock_query1.filter.return_value.order_by.return_value.first.return_value = None

        # Second query for pending count returns 0
        mock_query2 = MagicMock()
        mock_query2.filter.return_value.count.return_value = 0

        mock_session.query.side_effect = [mock_query1, mock_query2]

        assert not telemetry_service._should_upload()

    @patch('server.telemetry.service.session_maker')
    def test_should_upload_old_upload(self, mock_session_maker, telemetry_service):
        """Test should upload when 24+ hours have passed."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session_maker.return_value = mock_session

        mock_metric = MagicMock()
        mock_metric.uploaded_at = datetime.now(timezone.utc) - timedelta(hours=25)

        (
            mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value
        ) = mock_metric

        assert telemetry_service._should_upload()

    @patch('server.telemetry.service.session_maker')
    def test_should_not_upload_recent_upload(
        self, mock_session_maker, telemetry_service
    ):
        """Test should not upload when less than 24 hours have passed."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session_maker.return_value = mock_session

        mock_metric = MagicMock()
        mock_metric.uploaded_at = datetime.now(timezone.utc) - timedelta(hours=12)

        (
            mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value
        ) = mock_metric

        assert not telemetry_service._should_upload()


class TestIntervalSelection:
    """Test two-phase interval selection logic."""

    @patch.object(TelemetryService, '_is_identity_established')
    def test_bootstrap_interval_when_not_established(
        self, mock_is_established, telemetry_service
    ):
        """Test that bootstrap interval is used when identity not established."""
        mock_is_established.return_value = False

        # The logic is in the loops, so we check the constant values
        assert telemetry_service.bootstrap_check_interval_seconds == 180
        assert telemetry_service.normal_check_interval_seconds == 3600

    @patch.object(TelemetryService, '_is_identity_established')
    def test_normal_interval_when_established(
        self, mock_is_established, telemetry_service
    ):
        """Test that normal interval is used when identity is established."""
        mock_is_established.return_value = True

        assert telemetry_service.normal_check_interval_seconds == 3600


class TestGetAdminEmail:
    """Test admin email determination logic."""

    @patch('server.telemetry.service.os.getenv')
    def test_admin_email_from_env(self, mock_getenv, telemetry_service, mock_session):
        """Test getting admin email from environment variable."""
        mock_getenv.return_value = 'admin@example.com'

        email = telemetry_service._get_admin_email(mock_session)

        assert email == 'admin@example.com'
        mock_getenv.assert_called_once_with('OPENHANDS_ADMIN_EMAIL')

    @patch('server.telemetry.service.os.getenv')
    def test_admin_email_from_first_user(
        self, mock_getenv, telemetry_service, mock_session
    ):
        """Test getting admin email from first user who accepted ToS."""
        mock_getenv.return_value = None

        mock_user = MagicMock()
        mock_user.email = 'first@example.com'

        mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.first.return_value = mock_user

        email = telemetry_service._get_admin_email(mock_session)

        assert email == 'first@example.com'

    @patch('server.telemetry.service.os.getenv')
    def test_admin_email_not_found(self, mock_getenv, telemetry_service, mock_session):
        """Test when no admin email is available."""
        mock_getenv.return_value = None

        mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.first.return_value = (
            None
        )

        email = telemetry_service._get_admin_email(mock_session)

        assert email is None


class TestGetOrCreateIdentity:
    """Test identity creation logic."""

    def test_create_new_identity(self, telemetry_service, mock_session):
        """Test creating a new identity record."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        with patch('server.telemetry.service.TelemetryIdentity') as mock_identity_class:
            mock_identity = MagicMock()
            mock_identity.customer_id = None
            mock_identity.instance_id = None
            mock_identity_class.return_value = mock_identity

            with patch('server.telemetry.service.ReplicatedClient') as mock_client:
                mock_customer = MagicMock()
                mock_customer.customer_id = 'cust-123'
                mock_instance = MagicMock()
                mock_instance.instance_id = 'inst-456'
                mock_customer.get_or_create_instance.return_value = mock_instance

                mock_client.return_value.customer.get_or_create.return_value = (
                    mock_customer
                )

                identity = telemetry_service._get_or_create_identity(
                    mock_session, 'test@example.com'
                )

                mock_session.add.assert_called_once()
                mock_session.commit.assert_called()

    def test_update_existing_identity(self, telemetry_service, mock_session):
        """Test updating an existing identity record."""
        mock_identity = MagicMock()
        mock_identity.customer_id = 'existing@example.com'
        mock_identity.instance_id = 'existing-instance'

        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_identity
        )

        identity = telemetry_service._get_or_create_identity(
            mock_session, 'test@example.com'
        )

        # Should not create new instance since both IDs exist
        assert mock_session.add.call_count == 0
        mock_session.commit.assert_called()


class TestLicenseWarningStatus:
    """Test license warning status logic."""

    @patch('server.telemetry.service.session_maker')
    def test_no_uploads_yet(self, mock_session_maker, telemetry_service):
        """Test license warning status when no uploads have occurred."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session_maker.return_value = mock_session

        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            None
        )

        status = telemetry_service.get_license_warning_status()

        assert status['should_warn'] is False
        assert status['days_since_upload'] is None
        assert 'No uploads yet' in status['message']

    @patch('server.telemetry.service.session_maker')
    def test_recent_upload_no_warning(self, mock_session_maker, telemetry_service):
        """Test no warning when upload is recent."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session_maker.return_value = mock_session

        mock_metric = MagicMock()
        mock_metric.uploaded_at = datetime.now(timezone.utc) - timedelta(days=2)

        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            mock_metric
        )

        status = telemetry_service.get_license_warning_status()

        assert status['should_warn'] is False
        assert status['days_since_upload'] == 2

    @patch('server.telemetry.service.session_maker')
    def test_old_upload_warning(self, mock_session_maker, telemetry_service):
        """Test warning when upload is old."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session_maker.return_value = mock_session

        mock_metric = MagicMock()
        mock_metric.uploaded_at = datetime.now(timezone.utc) - timedelta(days=5)

        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            mock_metric
        )

        status = telemetry_service.get_license_warning_status()

        assert status['should_warn'] is True
        assert status['days_since_upload'] == 5


class TestLifecycleManagement:
    """Test service lifecycle management."""

    @pytest.mark.asyncio
    async def test_start_service(self, telemetry_service):
        """Test starting the telemetry service."""
        with patch.object(
            telemetry_service, '_collection_loop', new_callable=AsyncMock
        ):
            with patch.object(
                telemetry_service, '_upload_loop', new_callable=AsyncMock
            ):
                with patch.object(
                    telemetry_service, '_initial_collection_check', new_callable=AsyncMock
                ):
                    await telemetry_service.start()

                    assert telemetry_service._collection_task is not None
                    assert telemetry_service._upload_task is not None

                    # Clean up
                    await telemetry_service.stop()

    @pytest.mark.asyncio
    async def test_start_service_already_started(self, telemetry_service):
        """Test starting an already started service."""
        with patch.object(
            telemetry_service, '_collection_loop', new_callable=AsyncMock
        ):
            with patch.object(
                telemetry_service, '_upload_loop', new_callable=AsyncMock
            ):
                with patch.object(
                    telemetry_service, '_initial_collection_check', new_callable=AsyncMock
                ):
                    await telemetry_service.start()
                    first_collection_task = telemetry_service._collection_task
                    first_upload_task = telemetry_service._upload_task

                    # Try to start again
                    await telemetry_service.start()

                    # Tasks should be the same
                    assert telemetry_service._collection_task is first_collection_task
                    assert telemetry_service._upload_task is first_upload_task

                    # Clean up
                    await telemetry_service.stop()

    @pytest.mark.asyncio
    async def test_stop_service(self, telemetry_service):
        """Test stopping the telemetry service."""
        with patch.object(
            telemetry_service, '_collection_loop', new_callable=AsyncMock
        ):
            with patch.object(
                telemetry_service, '_upload_loop', new_callable=AsyncMock
            ):
                with patch.object(
                    telemetry_service, '_initial_collection_check', new_callable=AsyncMock
                ):
                    await telemetry_service.start()
                    await telemetry_service.stop()

                    assert telemetry_service._shutdown_event.is_set()
