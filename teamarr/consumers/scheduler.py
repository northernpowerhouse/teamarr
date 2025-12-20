"""Background scheduler for channel lifecycle tasks.

Runs periodic tasks:
- EPG generation and file delivery
- Process scheduled channel deletions
- Light reconciliation (detect and log issues)
- Cleanup old history records

Integrates with FastAPI lifespan for clean startup/shutdown.
"""

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class LifecycleScheduler:
    """Background scheduler for channel lifecycle tasks.

    Runs periodic tasks in a daemon thread:
    - Channel deletion based on scheduled times
    - Light reconciliation (detect-only)
    - History cleanup

    Usage:
        scheduler = LifecycleScheduler(
            db_factory=get_db,
            interval_minutes=15,
        )
        scheduler.start()
        # ... application runs ...
        scheduler.stop()

    FastAPI integration:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            scheduler = LifecycleScheduler(get_db)
            scheduler.start()
            yield
            scheduler.stop()
    """

    def __init__(
        self,
        db_factory: Any,
        interval_minutes: int = 15,
        dispatcharr_client: Any = None,
    ):
        """Initialize the scheduler.

        Args:
            db_factory: Factory function returning database connection
            interval_minutes: Minutes between task runs
            dispatcharr_client: Optional DispatcharrClient for Dispatcharr operations
        """
        self._db_factory = db_factory
        self._interval_minutes = interval_minutes
        self._dispatcharr_client = dispatcharr_client

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False
        self._last_run: datetime | None = None

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running and self._thread is not None and self._thread.is_alive()

    @property
    def last_run(self) -> datetime | None:
        """Get time of last task run."""
        return self._last_run

    def start(self) -> bool:
        """Start the scheduler.

        Returns:
            True if started, False if already running
        """
        if self.is_running:
            logger.warning("Scheduler already running")
            return False

        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name="lifecycle-scheduler",
            daemon=True,
        )
        self._thread.start()
        logger.info(f"Lifecycle scheduler started (interval: {self._interval_minutes} minutes)")
        return True

    def stop(self, timeout: float = 30.0) -> bool:
        """Stop the scheduler gracefully.

        Args:
            timeout: Maximum seconds to wait for thread to stop

        Returns:
            True if stopped, False if timeout
        """
        if not self.is_running:
            return True

        logger.info("Stopping lifecycle scheduler...")
        self._stop_event.set()
        self._running = False

        if self._thread:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("Scheduler thread did not stop in time")
                return False

        logger.info("Lifecycle scheduler stopped")
        return True

    def run_once(self) -> dict:
        """Run all scheduled tasks once (for testing/manual trigger).

        Returns:
            Dict with task results
        """
        return self._run_tasks()

    def _run_loop(self) -> None:
        """Main scheduler loop - runs in background thread."""
        interval_seconds = self._interval_minutes * 60

        # Run immediately on startup
        try:
            self._run_tasks()
        except Exception as e:
            logger.exception(f"Error in initial scheduler run: {e}")

        while not self._stop_event.is_set():
            # Wait for interval (checking stop event periodically)
            for _ in range(int(interval_seconds)):
                if self._stop_event.is_set():
                    return
                time.sleep(1)

            # Run tasks
            try:
                self._run_tasks()
            except Exception as e:
                logger.exception(f"Error in scheduler run: {e}")

    def _run_tasks(self) -> dict:
        """Run all scheduled tasks.

        Returns:
            Dict with task results
        """
        self._last_run = datetime.now()
        results = {
            "started_at": self._last_run.isoformat(),
            "epg_generation": {},
            "deletions": {},
            "reconciliation": {},
            "cleanup": {},
        }

        try:
            # Task 1: EPG generation and file delivery
            results["epg_generation"] = self._task_generate_epg()
        except Exception as e:
            logger.warning(f"EPG generation task failed: {e}")
            results["epg_generation"] = {"error": str(e)}

        try:
            # Task 2: Process scheduled deletions
            results["deletions"] = self._task_process_deletions()
        except Exception as e:
            logger.warning(f"Deletion task failed: {e}")
            results["deletions"] = {"error": str(e)}

        try:
            # Task 3: Light reconciliation (detect only)
            results["reconciliation"] = self._task_light_reconciliation()
        except Exception as e:
            logger.warning(f"Reconciliation task failed: {e}")
            results["reconciliation"] = {"error": str(e)}

        try:
            # Task 4: Cleanup old history
            results["cleanup"] = self._task_cleanup_history()
        except Exception as e:
            logger.warning(f"Cleanup task failed: {e}")
            results["cleanup"] = {"error": str(e)}

        results["completed_at"] = datetime.now().isoformat()
        return results

    def _task_generate_epg(self) -> dict:
        """Generate EPG for all teams and groups, write to output file.

        Flow:
        1. Refresh M3U accounts (with 60-min skip cache)
        2. Process all active teams (generates XMLTV per team)
        3. Process all active event groups (generates XMLTV per group)
        4. Get all stored XMLTV from database (teams + groups)
        5. Merge into single XMLTV document
        6. Write to output file path
        7. Trigger Dispatcharr EPG refresh
        8. Associate EPG data with managed channels

        Returns:
            Dict with generation stats
        """
        from teamarr.consumers import process_all_event_groups, process_all_teams
        from teamarr.consumers.team_processor import get_all_team_xmltv
        from teamarr.database.groups import get_all_group_xmltv
        from teamarr.database.settings import get_dispatcharr_settings, get_epg_settings
        from teamarr.utilities.xmltv import merge_xmltv_content

        result = {
            "m3u_refresh": {},
            "teams_processed": 0,
            "teams_programmes": 0,
            "groups_processed": 0,
            "groups_programmes": 0,
            "programmes_generated": 0,
            "file_written": False,
            "file_path": None,
            "file_size": 0,
            "epg_refresh": {},
            "epg_association": {},
        }

        # Get settings
        with self._db_factory() as conn:
            settings = get_epg_settings(conn)
            dispatcharr_settings = get_dispatcharr_settings(conn)

        output_path = settings.epg_output_path
        if not output_path:
            logger.debug("EPG output path not configured, skipping file write")
            return result

        # Step 1: Refresh M3U accounts before processing event groups
        if self._dispatcharr_client:
            result["m3u_refresh"] = self._refresh_m3u_accounts()

        # Step 2: Process all active teams
        team_result = process_all_teams(db_factory=self._db_factory)
        result["teams_processed"] = team_result.teams_processed
        result["teams_programmes"] = team_result.total_programmes

        if team_result.teams_processed > 0:
            logger.info(
                f"Processed {team_result.teams_processed} teams, "
                f"{team_result.total_programmes} programmes"
            )

        # Step 3: Process all event groups
        group_result = process_all_event_groups(
            db_factory=self._db_factory,
            dispatcharr_client=self._dispatcharr_client,
        )
        result["groups_processed"] = group_result.groups_processed
        result["groups_programmes"] = group_result.total_programmes

        if group_result.groups_processed > 0:
            logger.info(
                f"Processed {group_result.groups_processed} event groups, "
                f"{group_result.total_programmes} programmes"
            )

        # Calculate total
        result["programmes_generated"] = (
            team_result.total_programmes + group_result.total_programmes
        )

        # Check if anything was processed
        if team_result.teams_processed == 0 and group_result.groups_processed == 0:
            logger.debug("No teams or event groups processed, skipping EPG file write")
            return result

        # Get all stored XMLTV content (teams + groups)
        xmltv_contents: list[str] = []
        with self._db_factory() as conn:
            # Get team XMLTV
            team_xmltv = get_all_team_xmltv(conn)
            xmltv_contents.extend(team_xmltv)

            # Get group XMLTV
            group_xmltv = get_all_group_xmltv(conn)
            xmltv_contents.extend(group_xmltv)

        if not xmltv_contents:
            logger.debug("No XMLTV content available, skipping file write")
            return result

        # Merge all XMLTV documents
        merged_xmltv = merge_xmltv_content(xmltv_contents)

        # Write to file
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Write with backup
            if output_file.exists():
                backup_path = output_file.with_suffix(".xml.bak")
                try:
                    if backup_path.exists():
                        backup_path.unlink()
                    output_file.rename(backup_path)
                except Exception as e:
                    logger.warning(f"Could not create backup: {e}")

            output_file.write_text(merged_xmltv, encoding="utf-8")

            result["file_written"] = True
            result["file_path"] = str(output_file.absolute())
            result["file_size"] = len(merged_xmltv)

            logger.info(
                f"EPG written to {output_path} "
                f"({len(merged_xmltv):,} bytes, {result['programmes_generated']} programmes)"
            )

        except Exception as e:
            logger.error(f"Failed to write EPG file: {e}")
            result["error"] = str(e)
            return result

        # Step 7: Trigger Dispatcharr EPG refresh
        if self._dispatcharr_client and dispatcharr_settings.epg_id:
            result["epg_refresh"] = self._trigger_epg_refresh(dispatcharr_settings.epg_id)

        # Step 8: Associate EPG data with managed channels
        if self._dispatcharr_client and dispatcharr_settings.epg_id:
            result["epg_association"] = self._associate_epg_with_channels(
                dispatcharr_settings.epg_id
            )

        return result

    def _refresh_m3u_accounts(self) -> dict:
        """Refresh M3U accounts for all event groups.

        Collects unique M3U account IDs from all active event groups
        and refreshes them in parallel with 60-minute skip cache.

        Returns:
            Dict with refresh stats
        """
        from teamarr.database.groups import get_all_groups
        from teamarr.dispatcharr import M3UManager

        result = {"refreshed": 0, "skipped": 0, "failed": 0, "account_ids": []}

        if not self._dispatcharr_client:
            return result

        # Collect unique M3U account IDs from active groups
        with self._db_factory() as conn:
            groups = get_all_groups(conn, include_disabled=False)

        account_ids = set()
        for group in groups:
            if group.m3u_account_id:
                account_ids.add(group.m3u_account_id)

        if not account_ids:
            logger.debug("No M3U accounts to refresh")
            return result

        result["account_ids"] = list(account_ids)

        # Refresh all accounts in parallel
        m3u_manager = M3UManager(self._dispatcharr_client)
        batch_result = m3u_manager.refresh_multiple(
            list(account_ids),
            timeout=120,
            skip_if_recent_minutes=60,
        )

        result["refreshed"] = batch_result.succeeded_count - batch_result.skipped_count
        result["skipped"] = batch_result.skipped_count
        result["failed"] = batch_result.failed_count
        result["duration"] = batch_result.duration

        if batch_result.succeeded_count > 0:
            logger.info(
                f"M3U refresh: {result['refreshed']} refreshed, "
                f"{result['skipped']} skipped (recently updated)"
            )

        return result

    def _trigger_epg_refresh(self, epg_id: int) -> dict:
        """Trigger Dispatcharr EPG refresh and wait for completion.

        Args:
            epg_id: Dispatcharr EPG source ID

        Returns:
            Dict with refresh result
        """
        from teamarr.dispatcharr import EPGManager

        if not self._dispatcharr_client:
            return {"skipped": True, "reason": "No Dispatcharr client"}

        epg_manager = EPGManager(self._dispatcharr_client)
        refresh_result = epg_manager.wait_for_refresh(epg_id, timeout=60)

        if refresh_result.success:
            logger.info(
                f"Dispatcharr EPG refresh completed in {refresh_result.duration:.1f}s"
            )
        else:
            logger.warning(f"Dispatcharr EPG refresh failed: {refresh_result.message}")

        return {
            "success": refresh_result.success,
            "message": refresh_result.message,
            "duration": refresh_result.duration,
        }

    def _associate_epg_with_channels(self, epg_source_id: int) -> dict:
        """Associate EPG data with managed channels after EPG refresh.

        Args:
            epg_source_id: Dispatcharr EPG source ID

        Returns:
            Dict with association stats
        """
        from teamarr.consumers import create_lifecycle_service

        if not self._dispatcharr_client:
            return {"skipped": True, "reason": "No Dispatcharr client"}

        service = create_lifecycle_service(
            self._db_factory,
            dispatcharr_client=self._dispatcharr_client,
        )

        result = service.associate_epg_with_channels(epg_source_id)

        if result.get("associated", 0) > 0:
            logger.info(f"Associated EPG data with {result['associated']} channels")

        return result

    def _task_process_deletions(self) -> dict:
        """Process channels past their scheduled delete time."""
        from teamarr.consumers import create_lifecycle_service

        service = create_lifecycle_service(
            self._db_factory,
            self._dispatcharr_client,
        )

        result = service.process_scheduled_deletions()

        if result.deleted:
            logger.info(f"Scheduler deleted {len(result.deleted)} expired channel(s)")

        return {
            "deleted_count": len(result.deleted),
            "error_count": len(result.errors),
        }

    def _task_light_reconciliation(self) -> dict:
        """Run detect-only reconciliation and log issues."""
        from teamarr.consumers import create_reconciler
        from teamarr.database.channels import get_reconciliation_settings

        # Check if reconciliation is enabled
        with self._db_factory() as conn:
            settings = get_reconciliation_settings(conn)

        if not settings.get("reconcile_on_epg_generation", True):
            return {"skipped": True, "reason": "disabled"}

        reconciler = create_reconciler(
            self._db_factory,
            self._dispatcharr_client,
        )

        # Detect only - don't auto-fix in background
        result = reconciler.reconcile(auto_fix=False)

        if result.issues_found:
            logger.info(
                f"Reconciliation found {len(result.issues_found)} issue(s): {result.summary}"
            )

        return result.summary

    def _task_cleanup_history(self) -> dict:
        """Cleanup old channel history records."""
        from teamarr.database.channels import (
            cleanup_old_history,
            get_reconciliation_settings,
        )

        # Get retention days from settings
        with self._db_factory() as conn:
            settings = get_reconciliation_settings(conn)
            retention_days = settings.get("channel_history_retention_days", 90)
            deleted_count = cleanup_old_history(conn, retention_days)

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old history record(s)")

        return {"deleted_count": deleted_count}


# =============================================================================
# MODULE-LEVEL FUNCTIONS
# =============================================================================


_scheduler: LifecycleScheduler | None = None


def start_lifecycle_scheduler(
    db_factory: Any,
    interval_minutes: int | None = None,
    dispatcharr_client: Any = None,
) -> bool:
    """Start the global lifecycle scheduler.

    Args:
        db_factory: Factory function returning database connection
        interval_minutes: Minutes between runs (None = use settings)
        dispatcharr_client: Optional DispatcharrClient instance

    Returns:
        True if started, False if already running or disabled
    """
    global _scheduler

    from teamarr.database.channels import get_scheduler_settings

    # Get settings
    with db_factory() as conn:
        settings = get_scheduler_settings(conn)

    if not settings.get("enabled", True):
        logger.info("Scheduler disabled in settings")
        return False

    interval = interval_minutes or settings.get("interval_minutes", 15)

    if _scheduler and _scheduler.is_running:
        logger.warning("Scheduler already running")
        return False

    _scheduler = LifecycleScheduler(
        db_factory=db_factory,
        interval_minutes=interval,
        dispatcharr_client=dispatcharr_client,
    )
    return _scheduler.start()


def stop_lifecycle_scheduler(timeout: float = 30.0) -> bool:
    """Stop the global lifecycle scheduler.

    Args:
        timeout: Maximum seconds to wait

    Returns:
        True if stopped
    """
    global _scheduler

    if not _scheduler:
        return True

    result = _scheduler.stop(timeout)
    _scheduler = None
    return result


def is_scheduler_running() -> bool:
    """Check if the global scheduler is running."""
    return _scheduler is not None and _scheduler.is_running


def get_scheduler_status() -> dict:
    """Get status of the global scheduler."""
    if not _scheduler:
        return {"running": False}

    return {
        "running": _scheduler.is_running,
        "last_run": _scheduler.last_run.isoformat() if _scheduler.last_run else None,
        "interval_minutes": _scheduler._interval_minutes,
    }
