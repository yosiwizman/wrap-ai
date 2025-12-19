# OpenHands Enterprise Usage Telemetry Service

## Table of Contents

1. [Introduction](#1-introduction)
   - 1.1 [Problem Statement](#11-problem-statement)
   - 1.2 [Proposed Solution](#12-proposed-solution)
2. [User Interface](#2-user-interface)
   - 2.1 [License Warning Banner](#21-license-warning-banner)
   - 2.2 [Administrator Experience](#22-administrator-experience)
3. [Other Context](#3-other-context)
   - 3.1 [Replicated Platform Integration](#31-replicated-platform-integration)
   - 3.2 [Administrator Email Detection Strategy](#32-administrator-email-detection-strategy)
   - 3.3 [Metrics Collection Framework](#33-metrics-collection-framework)
4. [Technical Design](#4-technical-design)
   - 4.1 [Database Schema](#41-database-schema)
     - 4.1.1 [Telemetry Metrics Table](#411-telemetry-metrics-table)
     - 4.1.2 [Telemetry Identity Table](#412-telemetry-identity-table)
   - 4.2 [Metrics Collection Framework](#42-metrics-collection-framework)
     - 4.2.1 [Base Collector Interface](#421-base-collector-interface)
     - 4.2.2 [Collector Registry](#422-collector-registry)
     - 4.2.3 [Example Collector Implementation](#423-example-collector-implementation)
   - 4.3 [Embedded Telemetry Service](#43-embedded-telemetry-service)
     - 4.3.1 [TelemetryService - Core Service Class](#431-telemetryservice---core-service-class)
     - 4.3.2 [FastAPI Lifespan Integration](#432-fastapi-lifespan-integration)
     - 4.3.3 [Enterprise Server Integration](#433-enterprise-server-integration)
   - 4.4 [License Warning System](#44-license-warning-system)
     - 4.4.1 [License Status Endpoint](#441-license-status-endpoint)
     - 4.4.2 [UI Integration](#442-ui-integration)
   - 4.5 [Environment Configuration](#45-environment-configuration)
     - 4.5.1 [Required Environment Variables](#451-required-environment-variables)
     - 4.5.2 [Helm Chart Values](#452-helm-chart-values)
     - 4.5.3 [Helm Secret Configuration](#453-helm-secret-configuration)
     - 4.5.4 [Deployment Environment Variables](#454-deployment-environment-variables)
5. [Implementation Plan](#5-implementation-plan)
   - 5.1 [Database Schema and Models (M1)](#51-database-schema-and-models-m1)
     - 5.1.1 [OpenHands - Database Migration](#511-openhands---database-migration)
     - 5.1.2 [OpenHands - Model Tests](#512-openhands---model-tests)
   - 5.2 [Metrics Collection Framework (M2)](#52-metrics-collection-framework-m2)
     - 5.2.1 [OpenHands - Core Collection Framework](#521-openhands---core-collection-framework)
     - 5.2.2 [OpenHands - Example Collectors](#522-openhands---example-collectors)
     - 5.2.3 [OpenHands - Framework Tests](#523-openhands---framework-tests)
   - 5.3 [Embedded Telemetry Service (M3)](#53-embedded-telemetry-service-m3)
     - 5.3.1 [OpenHands - Telemetry Service](#531-openhands---telemetry-service)
     - 5.3.2 [OpenHands - Server Integration](#532-openhands---server-integration)
     - 5.3.3 [OpenHands - Integration Tests](#533-openhands---integration-tests)
   - 5.4 [License Warning API (M4)](#54-license-warning-api-m4)
     - 5.4.1 [OpenHands - License Status API](#541-openhands---license-status-api)
     - 5.4.2 [OpenHands - API Integration](#542-openhands---api-integration)
   - 5.5 [UI Warning Banner (M5)](#55-ui-warning-banner-m5)
     - 5.5.1 [OpenHands - UI Warning Banner](#551-openhands---ui-warning-banner)
     - 5.5.2 [OpenHands - UI Integration](#552-openhands---ui-integration)
   - 5.6 [Helm Chart Environment Configuration (M6)](#56-helm-chart-environment-configuration-m6)
     - 5.6.1 [OpenHands-Cloud - Secret Management](#561-openhands-cloud---secret-management)
     - 5.6.2 [OpenHands-Cloud - Values Configuration](#562-openhands-cloud---values-configuration)
     - 5.6.3 [OpenHands-Cloud - Deployment Environment Variables](#563-openhands-cloud---deployment-environment-variables)
   - 5.7 [Documentation and Enhanced Collectors (M7)](#57-documentation-and-enhanced-collectors-m7)
     - 5.7.1 [OpenHands - Advanced Collectors](#571-openhands---advanced-collectors)
     - 5.7.2 [OpenHands - Monitoring and Testing](#572-openhands---monitoring-and-testing)
     - 5.7.3 [OpenHands - Technical Documentation](#573-openhands---technical-documentation)

## 1. Introduction

### 1.1 Problem Statement

OpenHands Enterprise (OHE) helm charts are publicly available but not open source, creating a visibility gap for the sales team. Unknown users can install and use OHE without the vendor's knowledge, preventing proper customer engagement and sales pipeline management. Without usage telemetry, the vendor cannot identify potential customers, track installation health, or proactively support users who may need assistance.

### 1.2 Proposed Solution

We propose implementing a comprehensive telemetry service that leverages the Replicated metrics platform and Python SDK to track OHE installations and usage. The solution provides automatic customer discovery, instance monitoring, and usage metrics collection while maintaining a clear license compliance pathway.

The system consists of three main components: (1) a pluggable metrics collection framework that allows developers to easily define and register custom metrics collectors, (2) an embedded background service that runs within the main enterprise server process using AsyncIO to periodically collect metrics and upload them to Replicated's vendor portal, and (3) a license compliance warning system that displays UI notifications when telemetry uploads fail, indicating potential license expiration.

The design ensures that telemetry cannot be easily disabled by embedding it deeply into the enterprise server code. The telemetry service starts automatically with the FastAPI application using lifespan events and runs as independent AsyncIO background tasks. This approach makes the telemetry system significantly harder to detect and disable compared to external Kubernetes CronJobs, while balancing user transparency with business requirements for customer visibility.

## 2. User Interface

### 2.1 License Warning Banner

When telemetry uploads fail for more than 4 days, users will see a prominent warning banner in the OpenHands Enterprise UI:

```
⚠️ Your OpenHands Enterprise license will expire in 30 days. Please contact support if this issue persists.
```

The banner appears at the top of all pages and cannot be permanently dismissed while the condition persists. Users can temporarily dismiss it, but it will reappear on page refresh until telemetry uploads resume successfully.

### 2.2 Administrator Experience

System administrators will not need to configure the telemetry system manually. The service automatically:

1. **Detects OHE installations** using existing required environment variables (`GITHUB_APP_CLIENT_ID`, `KEYCLOAK_SERVER_URL`, etc.)

2. **Generates unique customer identifiers** using administrator contact information:
   - Customer email: Determined by the following priority order:
     1. `OPENHANDS_ADMIN_EMAIL` environment variable (if set in helm values)
     2. Email of the first user who accepted Terms of Service (earliest `accepted_tos` timestamp)
   - Instance ID: Automatically generated by Replicated SDK using machine fingerprinting (IOPlatformUUID on macOS, D-Bus machine ID on Linux, Machine GUID on Windows)
   - **No Fallback**: If neither email source is available, telemetry collection is skipped until at least one user exists

3. **Collects and uploads metrics transparently** in the background via AsyncIO tasks that run within the main server process (weekly collection, daily upload)

4. **Displays warnings only when necessary** for license compliance - no notifications appear during normal operation

## 3. Other Context

### 3.1 Replicated Platform Integration

The Replicated platform provides vendor-hosted infrastructure for collecting customer and instance telemetry. The Python SDK handles authentication, state management, and reliable metric delivery.

**SDK Information:**
- **PyPI Package**: [`replicated`](https://pypi.org/project/replicated/) - Install via `pip install replicated`
- **Documentation**: [docs.replicated.com/sdk/python](https://docs.replicated.com/sdk/python)
- **License**: MIT
- **Current Version**: 0.1.0a2 (alpha)

**Authentication - Publishable API Keys:**

Replicated uses a **publishable key** model (similar to Stripe and other modern SaaS APIs) that is specifically designed to be safely embedded in customer-deployed applications:

- **Publishable Key** (`replicated_pk_...`): Safe to embed in application code and Docker images
  - **Limited Privileges**: Can only report metrics and instance status to the vendor portal (write-only for telemetry)
  - **Read-Only Access**: Cannot access other customers' data or modify vendor account settings
  - **Shared Across Deployments**: The same key is used for all customer installations of your application
  - **Not Customer-Specific**: Unlike license keys, the publishable key identifies your vendor account, not individual customers
  
- **Customer Identification**: Individual customers are identified by their email address or instance fingerprint, not by different API keys

This security model allows vendors to embed telemetry collection directly in their application without exposing sensitive credentials. The key should be stored in environment variables for configurability, but can be safely committed to source code if needed.

**Key Concepts:**
- **Customer**: Represents a unique OHE installation, identified by email or installation fingerprint
- **Instance**: Represents a specific deployment of OHE for a customer
- **Metrics**: Custom key-value data points collected from the installation
- **Status**: Instance health indicators (running, degraded, updating, etc.)

The SDK automatically handles machine fingerprinting, local state caching, and retry logic for failed uploads.

### 3.2 Administrator Email Detection Strategy

To identify the appropriate administrator contact for sales outreach, the system uses a three-tier approach that avoids performance penalties on user authentication:

**Tier 1: Explicit Configuration** - The `OPENHANDS_ADMIN_EMAIL` environment variable allows administrators to explicitly specify the contact email during deployment.

**Tier 2: First Active User Detection** - If no explicit email is configured, the system identifies the first user who accepted Terms of Service (earliest `accepted_tos` timestamp with a valid email). This represents the first person to actively engage with the system and is very likely the administrator or installer.

**No Fallback Needed** - If neither email source is available, telemetry collection is skipped entirely. This ensures we only report meaningful usage data when there are actual active users.

**Performance Optimization**: The admin email determination is performed only during telemetry upload attempts, ensuring zero performance impact on user login flows.

### 3.3 Metrics Collection Framework

The proposed collector framework allows developers to define metrics in a single file change:

```python
@register_collector("user_activity")
class UserActivityCollector(MetricsCollector):
    def collect(self) -> Dict[str, Any]:
        # Query database and return metrics
        return {"active_users_7d": count, "conversations_created": total}
```

Collectors are automatically discovered and executed by the background collection task, making the system extensible without modifying core collection logic.

## 4. Technical Design

### 4.1 Database Schema

#### 4.1.1 Telemetry Metrics Table

Stores collected metrics with transmission status tracking:

```sql
CREATE TABLE telemetry_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metrics_data JSONB NOT NULL,
    uploaded_at TIMESTAMP WITH TIME ZONE NULL,
    upload_attempts INTEGER DEFAULT 0,
    last_upload_error TEXT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_telemetry_metrics_collected_at ON telemetry_metrics(collected_at);
CREATE INDEX idx_telemetry_metrics_uploaded_at ON telemetry_metrics(uploaded_at);
```

#### 4.1.2 Telemetry Identity Table

Stores persistent identity information that must survive container restarts:

```sql
CREATE TABLE telemetry_identity (
    id INTEGER PRIMARY KEY DEFAULT 1,
    customer_id VARCHAR(255) NULL,
    instance_id VARCHAR(255) NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT single_identity_row CHECK (id = 1)
);
```

**Design Rationale:**
- **Separation of Concerns**: Identity data (customer_id, instance_id) is separated from operational data
- **Persistent vs Computed**: Only data that cannot be reliably recomputed is persisted
- **Upload Tracking**: Upload timestamps are tied directly to the metrics they represent
- **Simplified Queries**: System state can be derived from metrics table (e.g., `MAX(uploaded_at)` for last successful upload)

### 4.2 Metrics Collection Framework

#### 4.2.1 Base Collector Interface

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class MetricResult:
    key: str
    value: Any

class MetricsCollector(ABC):
    """Base class for metrics collectors."""

    @abstractmethod
    def collect(self) -> List[MetricResult]:
        """Collect metrics and return results."""
        pass

    @property
    @abstractmethod
    def collector_name(self) -> str:
        """Unique name for this collector."""
        pass

    def should_collect(self) -> bool:
        """Override to add collection conditions."""
        return True
```

#### 4.2.2 Collector Registry

```python
from typing import Dict, Type, List
import importlib
import pkgutil

class CollectorRegistry:
    """Registry for metrics collectors."""

    def __init__(self):
        self._collectors: Dict[str, Type[MetricsCollector]] = {}

    def register(self, collector_class: Type[MetricsCollector]) -> None:
        """Register a collector class."""
        collector = collector_class()
        self._collectors[collector.collector_name] = collector_class

    def get_all_collectors(self) -> List[MetricsCollector]:
        """Get instances of all registered collectors."""
        return [cls() for cls in self._collectors.values()]

    def discover_collectors(self, package_path: str) -> None:
        """Auto-discover collectors in a package."""
        # Implementation to scan for @register_collector decorators
        pass

# Global registry instance
collector_registry = CollectorRegistry()

def register_collector(name: str):
    """Decorator to register a collector."""
    def decorator(cls: Type[MetricsCollector]) -> Type[MetricsCollector]:
        collector_registry.register(cls)
        return cls
    return decorator
```

#### 4.2.3 Example Collector Implementation

```python
@register_collector("system_metrics")
class SystemMetricsCollector(MetricsCollector):
    """Collects basic system and usage metrics."""

    @property
    def collector_name(self) -> str:
        return "system_metrics"

    def collect(self) -> List[MetricResult]:
        results = []

        # Collect user count
        with session_maker() as session:
            user_count = session.query(UserSettings).count()
            results.append(MetricResult(
                key="total_users",
                value=user_count
            ))

            # Collect conversation count (last 30 days)
            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
            conversation_count = session.query(StoredConversationMetadata)\
                .filter(StoredConversationMetadata.created_at >= thirty_days_ago)\
                .count()

            results.append(MetricResult(
                key="conversations_30d",
                value=conversation_count
            ))

        return results
```

### 4.3 Embedded Telemetry Service

The telemetry system runs as an embedded service within the main enterprise server process, using AsyncIO background tasks managed by FastAPI's lifespan events. This approach makes it significantly harder to detect and disable compared to external Kubernetes CronJobs.

#### 4.3.1 TelemetryService - Core Service Class

**File**: `enterprise/server/telemetry/service.py`

```python
"""Embedded telemetry service that runs as part of the enterprise server process."""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from server.logger import logger
from storage.database import session_maker
from storage.telemetry_identity import TelemetryIdentity
from storage.telemetry_metrics import TelemetryMetrics
from storage.user_settings import UserSettings
from telemetry.registry import CollectorRegistry


class TelemetryService:
    """Singleton service for managing embedded telemetry collection and upload.
    
    This service runs as part of the main enterprise server process using AsyncIO
    background tasks. It starts automatically during FastAPI application startup
    and runs independently without requiring external CronJobs or maintenance workers.
    """
    
    _instance: Optional['TelemetryService'] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._collection_task: Optional[asyncio.Task] = None
        self._upload_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Configuration (from environment or defaults)
        self.collection_interval_days = int(os.getenv('TELEMETRY_COLLECTION_INTERVAL_DAYS', '7'))
        self.upload_interval_hours = int(os.getenv('TELEMETRY_UPLOAD_INTERVAL_HOURS', '24'))
        self.license_warning_threshold_days = int(os.getenv('TELEMETRY_WARNING_THRESHOLD_DAYS', '4'))
        
        # Replicated API configuration
        # NOTE: REPLICATED_PUBLISHABLE_KEY is a vendor-wide publishable key (starts with replicated_pk_...)
        # that is safe to embed in the application. It has limited privileges (write-only for metrics)
        # and cannot access other customers' data. The same key is shared across all customer deployments.
        # Individual customers are identified by email, not by different API keys.
        self.replicated_publishable_key = os.getenv('REPLICATED_PUBLISHABLE_KEY')
        self.replicated_app_slug = os.getenv('REPLICATED_APP_SLUG', 'openhands-enterprise')
        
        logger.info("TelemetryService initialized")
    
    async def start(self):
        """Start the telemetry service background tasks.
        
        Called automatically during FastAPI application startup via lifespan events.
        """
        if self._collection_task is not None or self._upload_task is not None:
            logger.warning("TelemetryService already started")
            return
        
        logger.info("Starting TelemetryService background tasks")
        
        # Start independent background loops
        self._collection_task = asyncio.create_task(self._collection_loop())
        self._upload_task = asyncio.create_task(self._upload_loop())
        
        # Run initial collection if needed (don't wait for 7-day interval)
        asyncio.create_task(self._initial_collection_check())
    
    async def stop(self):
        """Stop the telemetry service and perform cleanup.
        
        Called automatically during FastAPI application shutdown via lifespan events.
        """
        logger.info("Stopping TelemetryService")
        
        self._shutdown_event.set()
        
        # Cancel background tasks
        if self._collection_task:
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass
        
        if self._upload_task:
            self._upload_task.cancel()
            try:
                await self._upload_task
            except asyncio.CancelledError:
                pass
        
        logger.info("TelemetryService stopped")
    
    async def _collection_loop(self):
        """Background task that checks hourly if metrics collection is needed.
        
        Sleeps for 1 hour between checks. When 7 days have passed since the last
        collection, it triggers metrics collection from all registered collectors.
        """
        logger.info(f"Collection loop started (interval: {self.collection_interval_days} days)")
        
        while not self._shutdown_event.is_set():
            try:
                # Check if collection is needed
                if self._should_collect():
                    logger.info("Starting metrics collection")
                    await self._collect_metrics()
                    logger.info("Metrics collection completed")
                
                # Sleep for 1 hour before checking again
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                logger.info("Collection loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in collection loop: {e}", exc_info=True)
                # Continue running even if collection fails
                await asyncio.sleep(3600)
    
    async def _upload_loop(self):
        """Background task that checks hourly if metrics upload is needed.
        
        Sleeps for 1 hour between checks. When 24 hours have passed since the last
        upload, it triggers upload of pending metrics to Replicated.
        """
        logger.info(f"Upload loop started (interval: {self.upload_interval_hours} hours)")
        
        while not self._shutdown_event.is_set():
            try:
                # Check if upload is needed
                if self._should_upload():
                    logger.info("Starting metrics upload")
                    await self._upload_pending_metrics()
                    logger.info("Metrics upload completed")
                
                # Sleep for 1 hour before checking again
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                logger.info("Upload loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in upload loop: {e}", exc_info=True)
                # Continue running even if upload fails
                await asyncio.sleep(3600)
    
    async def _initial_collection_check(self):
        """Check on startup if initial collection is needed."""
        try:
            with session_maker() as session:
                count = session.query(TelemetryMetrics).count()
                if count == 0:
                    logger.info("No existing metrics found, running initial collection")
                    await self._collect_metrics()
        except Exception as e:
            logger.error(f"Error during initial collection check: {e}")
    
    def _should_collect(self) -> bool:
        """Check if 7 days have passed since last collection."""
        try:
            with session_maker() as session:
                last_metric = (
                    session.query(TelemetryMetrics)
                    .order_by(TelemetryMetrics.collected_at.desc())
                    .first()
                )
                
                if not last_metric:
                    return True  # First collection
                
                days_since = (datetime.now(timezone.utc) - last_metric.collected_at).days
                return days_since >= self.collection_interval_days
        except Exception as e:
            logger.error(f"Error checking collection status: {e}")
            return False
    
    def _should_upload(self) -> bool:
        """Check if 24 hours have passed since last upload."""
        try:
            with session_maker() as session:
                last_uploaded = (
                    session.query(TelemetryMetrics)
                    .filter(TelemetryMetrics.uploaded_at.isnot(None))
                    .order_by(TelemetryMetrics.uploaded_at.desc())
                    .first()
                )
                
                if not last_uploaded:
                    # Check if we have any pending metrics to upload
                    pending_count = session.query(TelemetryMetrics).filter(
                        TelemetryMetrics.uploaded_at.is_(None)
                    ).count()
                    return pending_count > 0
                
                hours_since = (datetime.now(timezone.utc) - last_uploaded.uploaded_at).total_seconds() / 3600
                return hours_since >= self.upload_interval_hours
        except Exception as e:
            logger.error(f"Error checking upload status: {e}")
            return False
    
    async def _collect_metrics(self):
        """Collect metrics from all registered collectors and store in database."""
        try:
            # Get all registered collectors
            registry = CollectorRegistry()
            collectors = registry.get_all_collectors()
            
            # Collect metrics from each collector
            all_metrics = {}
            collector_results = {}
            
            for collector in collectors:
                try:
                    if collector.should_collect():
                        results = collector.collect()
                        for result in results:
                            all_metrics[result.key] = result.value
                        collector_results[collector.collector_name] = len(results)
                        logger.info(f"Collected {len(results)} metrics from {collector.collector_name}")
                except Exception as e:
                    logger.error(f"Collector {collector.collector_name} failed: {e}", exc_info=True)
                    collector_results[collector.collector_name] = f"error: {str(e)}"
            
            # Store metrics in database
            with session_maker() as session:
                telemetry_record = TelemetryMetrics(
                    metrics_data=all_metrics,
                    collected_at=datetime.now(timezone.utc)
                )
                session.add(telemetry_record)
                session.commit()
                
                logger.info(f"Stored {len(all_metrics)} metrics in database")
        
        except Exception as e:
            logger.error(f"Error during metrics collection: {e}", exc_info=True)
    
    async def _upload_pending_metrics(self):
        """Upload pending metrics to Replicated."""
        if not self.replicated_publishable_key:
            logger.warning("REPLICATED_PUBLISHABLE_KEY not set, skipping upload")
            return
        
        try:
            from replicated import ReplicatedClient, InstanceStatus
            
            # Get pending metrics
            with session_maker() as session:
                pending_metrics = (
                    session.query(TelemetryMetrics)
                    .filter(TelemetryMetrics.uploaded_at.is_(None))
                    .order_by(TelemetryMetrics.collected_at)
                    .all()
                )
                
                if not pending_metrics:
                    logger.info("No pending metrics to upload")
                    return
                
                # Get admin email - skip if not available
                admin_email = self._get_admin_email(session)
                if not admin_email:
                    logger.warning("No admin email available, skipping upload")
                    return
                
                # Get or create identity
                identity = self._get_or_create_identity(session, admin_email)
                
                # Initialize Replicated client with publishable key
                # This publishable key is intentionally embedded in the application and shared
                # across all customer deployments. It's safe to use here because:
                # 1. It only has write privileges for metrics (cannot read other customers' data)
                # 2. It identifies the vendor (OpenHands), not individual customers
                # 3. Customer identification happens via email address passed to get_or_create()
                client = ReplicatedClient(
                    publishable_key=self.replicated_publishable_key,
                    app_slug=self.replicated_app_slug
                )
                
                # Upload each pending metric
                successful_count = 0
                # Get or create customer and instance
                customer = client.customer.get_or_create(email_address=admin_email)
                instance = customer.get_or_create_instance()
                
                # Update identity with Replicated IDs
                identity.customer_id = customer.customer_id
                identity.instance_id = instance.instance_id
                session.commit()
                
                # Upload each pending metric
                for metric in pending_metrics:
                    try:
                        # Send individual metrics
                        for key, value in metric.metrics_data.items():
                            instance.send_metric(key, value)
                        
                        # Update instance status
                        instance.set_status(InstanceStatus.RUNNING)
                        
                        # Mark as uploaded
                        metric.uploaded_at = datetime.now(timezone.utc)
                        metric.upload_attempts += 1
                        metric.last_upload_error = None
                        successful_count += 1
                        
                        logger.info(f"Uploaded metric {metric.id} to Replicated")
                    
                    except Exception as e:
                        metric.upload_attempts += 1
                        metric.last_upload_error = str(e)
                        logger.error(f"Error uploading metric {metric.id}: {e}")
                
                session.commit()
                logger.info(f"Successfully uploaded {successful_count}/{len(pending_metrics)} metrics")
        
        except Exception as e:
            logger.error(f"Error during metrics upload: {e}", exc_info=True)
    
    def _get_admin_email(self, session) -> Optional[str]:
        """Determine admin email from environment or database."""
        # Try environment variable first
        admin_email = os.getenv('OPENHANDS_ADMIN_EMAIL')
        if admin_email:
            logger.info("Using admin email from OPENHANDS_ADMIN_EMAIL environment variable")
            return admin_email
        
        # Try first user who accepted ToS
        try:
            first_user = (
                session.query(UserSettings)
                .filter(UserSettings.accepted_tos == True)  # noqa: E712
                .filter(UserSettings.email.isnot(None))
                .order_by(UserSettings.accepted_tos_timestamp)
                .first()
            )
            if first_user and first_user.email:
                logger.info(f"Using first active user email: {first_user.email}")
                return first_user.email
        except Exception as e:
            logger.error(f"Error determining admin email: {e}")
        
        return None
    
    def _get_or_create_identity(self, session, admin_email: str) -> TelemetryIdentity:
        """Get or create telemetry identity with customer and instance IDs."""
        identity = session.query(TelemetryIdentity).filter(
            TelemetryIdentity.id == 1
        ).first()
        
        if not identity:
            identity = TelemetryIdentity(id=1)
            session.add(identity)
        
        # Set customer_id to admin email if not already set
        if not identity.customer_id:
            identity.customer_id = admin_email
        
        # Generate instance_id using Replicated SDK if not set
        if not identity.instance_id:
            try:
                from replicated import ReplicatedClient
                client = ReplicatedClient(
                    publishable_key=self.replicated_publishable_key,
                    app_slug=self.replicated_app_slug
                )
                # Create customer and instance to get IDs
                customer = client.customer.get_or_create(email_address=admin_email)
                instance = customer.get_or_create_instance()
                identity.instance_id = instance.instance_id
            except Exception as e:
                logger.error(f"Error generating instance_id: {e}")
                # Generate a fallback UUID if Replicated SDK fails
                import uuid
                identity.instance_id = str(uuid.uuid4())
        
        session.commit()
        return identity
    
    def get_license_warning_status(self) -> dict:
        """Get current license warning status for UI display.
        
        Returns:
            dict with 'should_warn', 'days_since_upload', and 'message' keys
        """
        try:
            with session_maker() as session:
                last_uploaded = (
                    session.query(TelemetryMetrics)
                    .filter(TelemetryMetrics.uploaded_at.isnot(None))
                    .order_by(TelemetryMetrics.uploaded_at.desc())
                    .first()
                )
                
                if not last_uploaded:
                    return {
                        'should_warn': False,
                        'days_since_upload': None,
                        'message': 'No uploads yet'
                    }
                
                days_since_upload = (
                    datetime.now(timezone.utc) - last_uploaded.uploaded_at
                ).days
                
                should_warn = days_since_upload > self.license_warning_threshold_days
                
                return {
                    'should_warn': should_warn,
                    'days_since_upload': days_since_upload,
                    'message': f'Last upload: {days_since_upload} days ago'
                }
        except Exception as e:
            logger.error(f"Error getting license warning status: {e}")
            return {
                'should_warn': False,
                'days_since_upload': None,
                'message': f'Error: {str(e)}'
            }


# Global singleton instance
telemetry_service = TelemetryService()
```

#### 4.3.2 FastAPI Lifespan Integration

**File**: `enterprise/server/telemetry/lifecycle.py`

```python
"""FastAPI lifespan integration for the embedded telemetry service."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from server.logger import logger
from server.telemetry.service import telemetry_service


@asynccontextmanager
async def telemetry_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan context manager for telemetry service.
    
    This is called automatically during FastAPI application startup and shutdown,
    managing the lifecycle of the telemetry background tasks.
    
    Startup: Initializes and starts background collection and upload tasks
    Shutdown: Gracefully stops background tasks
    """
    logger.info("Starting telemetry service lifespan")
    
    # Startup - start background tasks
    try:
        await telemetry_service.start()
        logger.info("Telemetry service started successfully")
    except Exception as e:
        logger.error(f"Error starting telemetry service: {e}", exc_info=True)
        # Don't fail server startup if telemetry fails
    
    yield  # Server runs here
    
    # Shutdown - stop background tasks
    try:
        await telemetry_service.stop()
        logger.info("Telemetry service stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping telemetry service: {e}", exc_info=True)
```

#### 4.3.3 Enterprise Server Integration

**File**: `enterprise/saas_server.py` (add to existing file)

```python
# Add import at top of file with other imports
from server.telemetry.lifecycle import telemetry_lifespan  # noqa: E402

# Later in the file, after base_app is imported from openhands.server.app
# Add telemetry lifespan to the application
from openhands.server.app import lifespans

# Append telemetry lifespan to existing lifespans
lifespans.append(telemetry_lifespan)

# Note: The base_app already uses combine_lifespans(*lifespans) in openhands/server/app.py
# so adding to the lifespans list will automatically include it
```

### 4.4 License Warning System

#### 4.4.1 License Status Endpoint

```python
from fastapi import APIRouter
from datetime import datetime, timezone, timedelta

license_router = APIRouter()

@license_router.get("/license-status")
async def get_license_status():
    """Get license warning status for UI display."""

    # Only show warnings for OHE installations
    if not _is_openhands_enterprise():
        return {"warn": False, "message": ""}

    with session_maker() as session:
        # Get last successful upload time from metrics table
        last_upload = session.query(func.max(TelemetryMetrics.uploaded_at))\
            .filter(TelemetryMetrics.uploaded_at.isnot(None))\
            .scalar()

        if not last_upload:
            # No successful uploads yet - show warning after 4 days
            return {
                "warn": True,
                "message": "OpenHands Enterprise license verification pending. Please ensure network connectivity."
            }

        # Check if last successful upload was more than 4 days ago
        days_since_upload = (datetime.now(timezone.utc) - last_upload).days

        if days_since_upload > 4:
            # Find oldest unsent batch
            oldest_unsent = session.query(TelemetryMetrics)\
                .filter(TelemetryMetrics.uploaded_at.is_(None))\
                .order_by(TelemetryMetrics.collected_at)\
                .first()

            if oldest_unsent:
                # Calculate expiration date (oldest unsent + 34 days)
                expiration_date = oldest_unsent.collected_at + timedelta(days=34)
                days_until_expiration = (expiration_date - datetime.now(timezone.utc)).days

                if days_until_expiration <= 0:
                    message = "Your OpenHands Enterprise license has expired. Please contact support immediately."
                else:
                    message = f"Your OpenHands Enterprise license will expire in {days_until_expiration} days. Please contact support if this issue persists."

                return {"warn": True, "message": message}

        return {"warn": False, "message": ""}

def _is_openhands_enterprise() -> bool:
    """Detect if this is an OHE installation."""
    # Check for required OHE environment variables
    required_vars = [
        'GITHUB_APP_CLIENT_ID',
        'KEYCLOAK_SERVER_URL',
        'KEYCLOAK_REALM_NAME'
    ]

    return all(os.getenv(var) for var in required_vars)
```

#### 4.4.2 UI Integration

The frontend will poll the license status endpoint and display warnings using the existing banner component pattern:

```typescript
// New component: LicenseWarningBanner.tsx
interface LicenseStatus {
  warn: boolean;
  message: string;
}

export function LicenseWarningBanner() {
  const [licenseStatus, setLicenseStatus] = useState<LicenseStatus>({ warn: false, message: "" });

  useEffect(() => {
    const checkLicenseStatus = async () => {
      try {
        const response = await fetch('/api/license-status');
        const status = await response.json();
        setLicenseStatus(status);
      } catch (error) {
        console.error('Failed to check license status:', error);
      }
    };

    // Check immediately and then every hour
    checkLicenseStatus();
    const interval = setInterval(checkLicenseStatus, 60 * 60 * 1000);

    return () => clearInterval(interval);
  }, []);

  if (!licenseStatus.warn) {
    return null;
  }

  return (
    <div className="bg-red-600 text-white p-4 rounded flex items-center justify-between">
      <div className="flex items-center">
        <FaExclamationTriangle className="mr-3" />
        <span>{licenseStatus.message}</span>
      </div>
    </div>
  );
}
```

### 4.5 Environment Configuration

The telemetry service is configured entirely through environment variables. No Kubernetes CronJobs or separate worker processes are required - the service runs automatically within the main enterprise server process.

#### 4.5.1 Required Environment Variables

```bash
# Replicated API configuration (required for upload)
# The publishable key is a vendor-wide key that is safe to embed in your application.
# It starts with "replicated_pk_" and has limited privileges (write-only for metrics).
# The same key is shared across ALL customer deployments - customers are identified
# by their email address, not by different API keys.
REPLICATED_PUBLISHABLE_KEY=replicated_pk_xxxxxxxxxxxxxxxxxxxxx
REPLICATED_APP_SLUG=openhands-enterprise

# Optional: Explicit admin email (recommended)
OPENHANDS_ADMIN_EMAIL=admin@company.com

# Optional: Custom intervals (defaults shown)
TELEMETRY_COLLECTION_INTERVAL_DAYS=7
TELEMETRY_UPLOAD_INTERVAL_HOURS=24
TELEMETRY_WARNING_THRESHOLD_DAYS=4
```

#### 4.5.2 Helm Chart Values

**File**: `charts/openhands/values.yaml` (additions)

```yaml
# Telemetry configuration
telemetry:
  # Replicated configuration
  replicated:
    # Publishable key (replicated_pk_...) - safe to embed, shared across all deployments
    # This key only has write privileges for metrics and cannot access other customers' data
    publishableKey: ""  # Set via secret or values (can be committed to source if needed)
    appSlug: "openhands-enterprise"
  
  # Optional admin email
  adminEmail: ""
  
  # Collection and upload intervals
  collectionIntervalDays: 7
  uploadIntervalHours: 24
  warningThresholdDays: 4
```

#### 4.5.3 Helm Secret Configuration

**File**: `charts/openhands/templates/telemetry-secret.yaml`

```yaml
{{- if .Values.telemetry.replicated.publishableKey }}
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "openhands.fullname" . }}-telemetry
  labels:
    {{- include "openhands.labels" . | nindent 4 }}
type: Opaque
stringData:
  replicated-publishable-key: {{ .Values.telemetry.replicated.publishableKey }}
{{- end }}
```

#### 4.5.4 Deployment Environment Variables

**File**: `charts/openhands/templates/deployment.yaml` (additions to env section)

```yaml
# Add to existing deployment's container env section
{{- if .Values.telemetry.replicated.publishableKey }}
- name: REPLICATED_PUBLISHABLE_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "openhands.fullname" . }}-telemetry
      key: replicated-publishable-key
- name: REPLICATED_APP_SLUG
  value: {{ .Values.telemetry.replicated.appSlug | quote }}
{{- end }}
{{- if .Values.telemetry.adminEmail }}
- name: OPENHANDS_ADMIN_EMAIL
  value: {{ .Values.telemetry.adminEmail | quote }}
{{- end }}
{{- if .Values.telemetry.collectionIntervalDays }}
- name: TELEMETRY_COLLECTION_INTERVAL_DAYS
  value: {{ .Values.telemetry.collectionIntervalDays | quote }}
{{- end }}
{{- if .Values.telemetry.uploadIntervalHours }}
- name: TELEMETRY_UPLOAD_INTERVAL_HOURS
  value: {{ .Values.telemetry.uploadIntervalHours | quote }}
{{- end }}
{{- if .Values.telemetry.warningThresholdDays }}
- name: TELEMETRY_WARNING_THRESHOLD_DAYS
  value: {{ .Values.telemetry.warningThresholdDays | quote }}
{{- end }}
```

**Note**: Unlike the previous CronJob-based design, this embedded approach requires no separate Kubernetes resources. The telemetry service starts automatically with the main application server and cannot be disabled without modifying the application code itself.

## 5. Implementation Plan

All implementation must pass existing lints and tests. New functionality requires comprehensive unit tests with >90% coverage. Integration tests should verify end-to-end telemetry flow including collection, storage, upload, and warning display.

### 5.1 Database Schema and Models (M1)

**Repository**: OpenHands
Establish the foundational database schema and SQLAlchemy models for telemetry data storage.

#### 5.1.1 OpenHands - Database Migration

- [ ] `enterprise/migrations/versions/077_create_telemetry_tables.py`
- [ ] `enterprise/storage/telemetry_metrics.py`
- [ ] `enterprise/storage/telemetry_config.py`

#### 5.1.2 OpenHands - Model Tests

- [ ] `enterprise/tests/unit/storage/test_telemetry_metrics.py`
- [ ] `enterprise/tests/unit/storage/test_telemetry_config.py`

**Demo**: Database tables created and models can store/retrieve telemetry data.

### 5.2 Metrics Collection Framework (M2)

**Repository**: OpenHands
Implement the pluggable metrics collection system with registry and base classes.

#### 5.2.1 OpenHands - Core Collection Framework

- [ ] `enterprise/server/telemetry/__init__.py`
- [ ] `enterprise/server/telemetry/collector_base.py`
- [ ] `enterprise/server/telemetry/collector_registry.py`
- [ ] `enterprise/server/telemetry/decorators.py`

#### 5.2.2 OpenHands - Example Collectors

- [ ] `enterprise/server/telemetry/collectors/__init__.py`
- [ ] `enterprise/server/telemetry/collectors/system_metrics.py`
- [ ] `enterprise/server/telemetry/collectors/user_activity.py`

#### 5.2.3 OpenHands - Framework Tests

- [ ] `enterprise/tests/unit/telemetry/test_collector_base.py`
- [ ] `enterprise/tests/unit/telemetry/test_collector_registry.py`
- [ ] `enterprise/tests/unit/telemetry/test_system_metrics.py`

**Demo**: Developers can create new collectors with a single file change using the @register_collector decorator.

### 5.3 Embedded Telemetry Service (M3)

**Repository**: OpenHands
Implement the embedded telemetry service that runs within the main enterprise server process using AsyncIO background tasks.

#### 5.3.1 OpenHands - Telemetry Service

- [ ] `enterprise/server/telemetry/__init__.py` - Package initialization
- [ ] `enterprise/server/telemetry/service.py` - Core TelemetryService singleton class
- [ ] `enterprise/server/telemetry/lifecycle.py` - FastAPI lifespan integration
- [ ] `enterprise/tests/unit/telemetry/test_service.py` - Service unit tests
- [ ] `enterprise/tests/unit/telemetry/test_lifecycle.py` - Lifespan integration tests

**Key Features**:
- Singleton service pattern with thread-safe initialization
- Independent AsyncIO background tasks for collection (7 days) and upload (24 hours)
- Graceful startup and shutdown via FastAPI lifespan events
- Automatic recovery from errors without crashing main server

#### 5.3.2 OpenHands - Server Integration

- [ ] Update `enterprise/saas_server.py` to register telemetry lifespan
- [ ] Update `openhands/server/app.py` lifespans list (if needed)
- [ ] `enterprise/tests/integration/test_telemetry_embedded.py` - End-to-end integration tests

**Integration Points**:
- Add `telemetry_lifespan` to the FastAPI app's lifespan list
- No changes to request handling code required
- Zero overhead on normal operations

#### 5.3.3 OpenHands - Integration Tests

- [ ] `enterprise/tests/integration/test_telemetry_flow.py` - Full collection and upload cycle
- [ ] Test startup/shutdown behavior
- [ ] Test interval timing and database state
- [ ] Test Replicated API integration (mocked)
- [ ] Test error handling and recovery

**Demo**: Telemetry service starts automatically with the enterprise server, collects metrics weekly, uploads daily to Replicated, and cannot be disabled without code modification.

### 5.4 License Warning API (M4)

**Repository**: OpenHands
Implement the license status endpoint for the warning system.

#### 5.4.1 OpenHands - License Status API

- [ ] `enterprise/server/routes/license.py`
- [ ] `enterprise/tests/unit/routes/test_license.py`

#### 5.4.2 OpenHands - API Integration

- [ ] Update `enterprise/saas_server.py` to include license router

**Demo**: License status API returns warning status based on telemetry upload success.

### 5.5 UI Warning Banner (M5)

**Repository**: OpenHands
Implement the frontend warning banner component and integration.

#### 5.5.1 OpenHands - UI Warning Banner

- [ ] `frontend/src/components/features/license/license-warning-banner.tsx`
- [ ] `frontend/src/components/features/license/license-warning-banner.test.tsx`

#### 5.5.2 OpenHands - UI Integration

- [ ] Update main UI layout to include license warning banner
- [ ] Add license status polling service

**Demo**: License warnings appear in UI when telemetry uploads fail for >4 days, with accurate expiration countdown.

### 5.6 Helm Chart Environment Configuration (M6)

**Repository**: OpenHands-Cloud
Configure environment variables and secrets for the embedded telemetry service. No separate Kubernetes resources (CronJobs, workers) are required.

#### 5.6.1 OpenHands-Cloud - Secret Management

- [ ] `charts/openhands/templates/telemetry-secret.yaml` - Replicated API key secret
- [ ] Configure secret in deployment to provide `REPLICATED_PUBLISHABLE_KEY`

**Secret Template**:
```yaml
{{- if .Values.telemetry.replicated.publishableKey }}
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "openhands.fullname" . }}-telemetry
type: Opaque
stringData:
  replicated-publishable-key: {{ .Values.telemetry.replicated.publishableKey }}
{{- end }}
```

#### 5.6.2 OpenHands-Cloud - Values Configuration

- [ ] Update `charts/openhands/values.yaml` with telemetry configuration options:
  ```yaml
  # Add to values.yaml
  telemetry:
    replicated:
      publishableKey: ""  # Required for upload (set via secret or sealed secret)
      appSlug: "openhands-enterprise"
    adminEmail: ""  # Optional: explicit admin email
    collectionIntervalDays: 7
    uploadIntervalHours: 24
    warningThresholdDays: 4
  ```

#### 5.6.3 OpenHands-Cloud - Deployment Environment Variables

- [ ] Update `charts/openhands/templates/deployment.yaml` to inject telemetry environment variables:
  ```yaml
  # Add to deployment container env section
  {{- if .Values.telemetry.replicated.publishableKey }}
  - name: REPLICATED_PUBLISHABLE_KEY
    valueFrom:
      secretKeyRef:
        name: {{ include "openhands.fullname" . }}-telemetry
        key: replicated-publishable-key
  - name: REPLICATED_APP_SLUG
    value: {{ .Values.telemetry.replicated.appSlug | quote }}
  {{- end }}
  {{- if .Values.telemetry.adminEmail }}
  - name: OPENHANDS_ADMIN_EMAIL
    value: {{ .Values.telemetry.adminEmail | quote }}
  {{- end }}
  - name: TELEMETRY_COLLECTION_INTERVAL_DAYS
    value: {{ .Values.telemetry.collectionIntervalDays | default "7" | quote }}
  - name: TELEMETRY_UPLOAD_INTERVAL_HOURS
    value: {{ .Values.telemetry.uploadIntervalHours | default "24" | quote }}
  - name: TELEMETRY_WARNING_THRESHOLD_DAYS
    value: {{ .Values.telemetry.warningThresholdDays | default "4" | quote }}
  ```

**Note**: The telemetry service runs automatically within the main deployment - no CronJobs or additional pods are created.

**Demo**: Complete telemetry system deployed via helm chart with configurable collection intervals and Replicated integration.

### 5.7 Documentation and Enhanced Collectors (M7)

**Repository**: OpenHands
Add comprehensive metrics collectors, monitoring capabilities, and documentation.

#### 5.7.1 OpenHands - Advanced Collectors

- [ ] `enterprise/server/telemetry/collectors/conversation_metrics.py`
- [ ] `enterprise/server/telemetry/collectors/integration_usage.py`
- [ ] `enterprise/server/telemetry/collectors/performance_metrics.py`

#### 5.7.2 OpenHands - Monitoring and Testing

- [ ] `enterprise/server/telemetry/monitoring.py`
- [ ] `enterprise/tests/e2e/test_telemetry_system.py`
- [ ] Performance tests for large-scale metric collection

#### 5.7.3 OpenHands - Technical Documentation

- [ ] `enterprise/server/telemetry/README.md`
- [ ] Update deployment documentation with telemetry configuration instructions
- [ ] Add troubleshooting guide for telemetry issues

**Demo**: Rich telemetry data flowing to vendor portal with comprehensive monitoring, alerting for system health, and complete documentation.
