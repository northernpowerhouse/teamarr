"""Dynamic channel-profile patterns assign only the resolved profile (#894).

Two bugs put {sport}/{league}-pattern channels in every profile:

1. A profile the resolver created mid-run was missing from the per-run
   profile catalog, so _validate_profile_ids dropped it as stale and the
   channel fell back to the [0] all-profiles sentinel.
2. The next run's sync diffed the stored [0] as if it were a profile id:
   "remove from profile 0" failed in Dispatcharr, the real profiles were
   never left, and the new ids were stored anyway, so it never retried.
"""

from unittest.mock import MagicMock, patch

from teamarr.consumers.lifecycle.dynamic_resolver import DynamicResolver
from teamarr.dispatcharr.managers.channels import ChannelManager
from teamarr.dispatcharr.types import DispatcharrChannelProfile, OperationResult
from tests.fakes import FakeManagedChannel


def _make_service(channel_manager=None):
    from teamarr.consumers.lifecycle.service import ChannelLifecycleService

    return ChannelLifecycleService(
        db_factory=MagicMock(),
        sports_service=MagicMock(),
        channel_manager=channel_manager,
        logo_manager=MagicMock(),
        epg_manager=MagicMock(),
    )


def _profiles(membership: dict[int, set[int]]) -> list[DispatcharrChannelProfile]:
    return [
        DispatcharrChannelProfile(id=pid, name=f"P{pid}", channel_ids=tuple(chans))
        for pid, chans in membership.items()
    ]


class TestProfileCreatedMidRun:
    def test_new_profile_is_valid_not_stale(self, caplog):
        cm = MagicMock()
        cm.list_profiles.return_value = _profiles({1: set()})
        service = _make_service(channel_manager=cm)
        assert service._all_profile_ids() == {1}

        # The resolver creates profile 5 after the catalog was loaded.
        cm.list_profiles.return_value = _profiles({1: set(), 5: set()})
        with caplog.at_level("WARNING"):
            assert service._validate_profile_ids([5]) == [5]
        assert "does not exist" not in caplog.text
        assert "falling back to ALL profiles" not in caplog.text

    def test_stale_id_refetches_catalog_once_per_run(self, caplog):
        cm = MagicMock()
        cm.list_profiles.return_value = _profiles({1: set()})
        service = _make_service(channel_manager=cm)

        with caplog.at_level("WARNING"):
            assert service._validate_profile_ids([9]) == [0]
            assert service._validate_profile_ids([9]) == [0]
        # Initial load + one re-fetch for the unknown id, not one per channel.
        assert cm.list_profiles.call_count == 2
        assert caplog.text.count("profile id 9") == 1

    def test_failed_refetch_keeps_previous_catalog(self):
        cm = MagicMock()
        cm.list_profiles.return_value = _profiles({1: set()})
        service = _make_service(channel_manager=cm)
        service._all_profile_ids()

        cm.list_profiles.side_effect = RuntimeError("down")
        assert service._validate_profile_ids([1, 9]) == [1]
        assert service._all_profile_ids() == {1}


class TestResolverCreatesEmptyProfile:
    def test_created_profile_starts_empty(self):
        dispatcharr = MagicMock()
        dispatcharr.channels.create_profile.return_value = OperationResult(
            success=True, data={"id": 5}
        )
        r = DynamicResolver()
        r._initialized = True
        r._get_dispatcharr = lambda: dispatcharr

        assert r._get_or_create_profile("Rugby") == 5
        dispatcharr.channels.create_profile.assert_called_once_with(
            "Rugby", start_empty=True
        )

    def test_manager_sends_start_empty_only_when_requested(self):
        client = MagicMock()
        client.post.return_value = MagicMock(status_code=201, json=lambda: {"id": 5})
        manager = ChannelManager(client)

        manager.create_profile("Rugby")
        assert client.post.call_args.args[1] == {"name": "Rugby"}

        manager.create_profile("Rugby", start_empty=True)
        assert client.post.call_args.args[1] == {"name": "Rugby", "start_empty": True}


class TestSyncOffAllProfiles:
    CHANNEL_ID = 100

    def _sync(self, service, stored, resolved):
        existing = FakeManagedChannel(
            id=1, dispatcharr_channel_id=self.CHANNEL_ID, channel_profile_ids=stored
        )
        service._dynamic_resolver = MagicMock()
        service._dynamic_resolver.resolve_channel_profiles.return_value = resolved
        settings = MagicMock()
        settings.default_channel_profile_ids = ["{sport}"]
        changes: list[str] = []
        with (
            patch("teamarr.database.channels.update_managed_channel") as update_db,
            patch(
                "teamarr.database.settings.get_dispatcharr_settings",
                return_value=settings,
            ),
        ):
            service._sync_channel_profiles(
                conn=MagicMock(),
                existing=existing,
                event_sport="rugby",
                event_league="premiership",
                changes_made=changes,
            )
        return update_db, changes

    def _service(self, membership, bulk_result=None):
        cm = MagicMock()
        cm.list_profiles.return_value = _profiles(membership)
        cm.bulk_update_profile_channels.return_value = bulk_result or OperationResult(
            success=True
        )
        return _make_service(channel_manager=cm), cm

    def test_removes_from_actual_profiles_never_profile_zero(self):
        ch = self.CHANNEL_ID
        service, _ = self._service({1: {ch}, 5: {ch}, 6: {ch}, 7: set()})

        update_db, _ = self._sync(service, "[0]", [5])

        assert service._pending_profile_changes == {
            1: {"add": set(), "remove": {ch}},
            6: {"add": set(), "remove": {ch}},
        }
        update_db.assert_not_called()  # deferred until Dispatcharr accepts

    def test_adds_profile_the_channel_is_not_enabled_in(self):
        # Profile 7 was created (empty) after the channel was created with [0].
        ch = self.CHANNEL_ID
        service, _ = self._service({1: {ch}, 7: set()})

        self._sync(service, "[0]", [7])

        assert service._pending_profile_changes == {
            1: {"add": set(), "remove": {ch}},
            7: {"add": {ch}, "remove": set()},
        }

    def test_already_in_exactly_the_resolved_profile_stores_immediately(self):
        service, _ = self._service({1: set(), 5: {self.CHANNEL_ID}})

        update_db, _ = self._sync(service, "[0]", [5])

        assert service._pending_profile_changes == {}
        assert update_db.call_args.args[2] == {"channel_profile_ids": "[5]"}

    def test_catalog_unavailable_changes_nothing(self):
        service, cm = self._service({})
        cm.list_profiles.return_value = []

        update_db, changes = self._sync(service, "[0]", [5])

        assert service._pending_profile_changes == {}
        assert changes == []
        update_db.assert_not_called()

    def test_ids_stored_after_bulk_update_succeeds(self):
        ch = self.CHANNEL_ID
        service, cm = self._service({1: {ch}, 5: {ch}})
        self._sync(service, "[0]", [5])

        conn = MagicMock()
        with patch("teamarr.database.channels.update_managed_channel") as update_db:
            service._apply_pending_profile_changes(conn)

        cm.bulk_update_profile_channels.assert_called_once_with(
            profile_id=1, add_channel_ids=None, remove_channel_ids=[ch]
        )
        update_db.assert_called_once_with(conn, 1, {"channel_profile_ids": "[5]"})

    def test_ids_not_stored_when_bulk_update_fails(self):
        ch = self.CHANNEL_ID
        service, _ = self._service(
            {1: {ch}, 5: {ch}},
            bulk_result=OperationResult(success=False, error="boom"),
        )
        self._sync(service, "[0]", [5])

        with patch("teamarr.database.channels.update_managed_channel") as update_db:
            service._apply_pending_profile_changes(MagicMock())

        update_db.assert_not_called()
        assert service._pending_profile_db_writes == {}
