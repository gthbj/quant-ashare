from __future__ import annotations

import json
from datetime import timedelta

from google.cloud.exceptions import NotFound, PreconditionFailed

from quant_ashare.strategy1 import state as state_module
from quant_ashare.strategy1.annual_pipeline_scheduler import GcsSchedulerLease
from quant_ashare.strategy1.config import Experiment
from quant_ashare.strategy1.state import GcsLeaseLock, LockConfig, utc_now


class FakeBlob:
    def __init__(self, bucket: "FakeBucket", name: str):
        self.bucket = bucket
        self.name = name
        self.generation: int | None = None

    def _record(self) -> dict[str, object] | None:
        return self.bucket.objects.get(self.name)

    def upload_from_string(self, data, content_type=None, if_generation_match=None):
        record = self._record()
        if if_generation_match == 0:
            if record is not None:
                raise PreconditionFailed("object already exists")
        elif if_generation_match is not None:
            if record is None or record["generation"] != if_generation_match:
                raise PreconditionFailed("generation mismatch")

        next_generation = 1 if record is None else int(record["generation"]) + 1
        payload = data.encode("utf-8") if isinstance(data, str) else data
        self.bucket.objects[self.name] = {
            "data": payload,
            "generation": next_generation,
        }
        self.generation = next_generation

    def reload(self):
        record = self._record()
        if record is None:
            raise NotFound("object missing")
        self.generation = int(record["generation"])

    def download_as_bytes(self, if_generation_match=None):
        record = self._record()
        if record is None:
            raise NotFound("object missing")
        if if_generation_match is not None and record["generation"] != if_generation_match:
            raise PreconditionFailed("generation mismatch")
        self.generation = int(record["generation"])
        return record["data"]

    def delete(self, if_generation_match=None):
        record = self._record()
        if record is None:
            raise NotFound("object missing")
        if if_generation_match is not None and record["generation"] != if_generation_match:
            raise PreconditionFailed("generation mismatch")
        del self.bucket.objects[self.name]
        self.generation = None


class FakeBucket:
    def __init__(self, name: str):
        self.name = name
        self.objects: dict[str, dict[str, object]] = {}

    def blob(self, name: str) -> FakeBlob:
        return FakeBlob(self, name)


class FakeStorageClient:
    def __init__(self):
        self.buckets: dict[str, FakeBucket] = {}

    def bucket(self, name: str) -> FakeBucket:
        if name not in self.buckets:
            self.buckets[name] = FakeBucket(name)
        return self.buckets[name]


def _payload(bucket: FakeBucket, name: str) -> dict[str, object]:
    return json.loads(bucket.objects[name]["data"].decode("utf-8"))


def _store_payload(bucket: FakeBucket, name: str, payload: dict[str, object], *, bump_generation: bool = False) -> None:
    record = bucket.objects[name]
    record["data"] = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if bump_generation:
        record["generation"] = int(record["generation"]) + 1


def _experiment() -> Experiment:
    return Experiment(
        experiment_id="exp-unit",
        run_id="run-unit",
        backtest_id="bt-unit",
        prediction_run_id="pred-unit",
        stage_id="stage-unit",
    )


def _cloudrun_lock(client: FakeStorageClient, owner: str) -> GcsLeaseLock:
    lock = GcsLeaseLock(
        LockConfig(
            project="unit-test-project",
            region="asia-east2",
            bucket="unit-test-bucket",
            prefix="locks/test",
            ttl_minutes=30,
        ),
        "cloudrun:unit-test",
        _experiment(),
        "cloudrun_unit_test",
        owner,
    )
    lock._client = client
    return lock


def _scheduler_lease(client: FakeStorageClient, owner: str, *, ttl_minutes: int = 30) -> GcsSchedulerLease:
    return GcsSchedulerLease(
        project="unit-test-project",
        bucket="unit-test-bucket",
        prefix="locks/test",
        lock_key="annual-scheduler-unit-test",
        owner=owner,
        ttl_minutes=ttl_minutes,
        client=client,
    )


def test_gcs_lease_lock_acquire_competition() -> None:
    client = FakeStorageClient()
    first = _cloudrun_lock(client, "owner-1")
    second = _cloudrun_lock(client, "owner-2")

    assert first.acquire() is True
    assert second.acquire() is False

    bucket = client.bucket("unit-test-bucket")
    stored = _payload(bucket, "locks/test/cloudrun:unit-test.lock")
    assert stored["lock_owner"] == "owner-1"


def test_gcs_lease_lock_reclaims_stale_only_after_execution_terminal(monkeypatch) -> None:
    client = FakeStorageClient()
    first = _cloudrun_lock(client, "owner-1")
    second = _cloudrun_lock(client, "owner-2")
    assert first.acquire() is True

    bucket = client.bucket("unit-test-bucket")
    blob_name = "locks/test/cloudrun:unit-test.lock"
    stale_payload = _payload(bucket, blob_name)
    stale_payload["lease_expires_at"] = (utc_now() - timedelta(minutes=5)).isoformat()
    stale_payload["cloud_run_execution_id"] = "execution-running"
    _store_payload(bucket, blob_name, stale_payload)

    monkeypatch.setattr(state_module, "is_cloud_run_execution_terminal", lambda *args: False)
    assert second.acquire() is False
    assert _payload(bucket, blob_name)["lock_owner"] == "owner-1"

    monkeypatch.setattr(state_module, "is_cloud_run_execution_terminal", lambda *args: True)
    assert second.acquire() is True
    assert _payload(bucket, blob_name)["lock_owner"] == "owner-2"


def test_gcs_lease_lock_heartbeat_returns_none_after_generation_loss() -> None:
    client = FakeStorageClient()
    lock = _cloudrun_lock(client, "owner-1")
    assert lock.acquire() is True

    bucket = client.bucket("unit-test-bucket")
    blob_name = "locks/test/cloudrun:unit-test.lock"
    payload = _payload(bucket, blob_name)
    payload["lock_owner"] = "owner-2"
    _store_payload(bucket, blob_name, payload, bump_generation=True)

    assert lock.heartbeat() is None


def test_gcs_scheduler_lease_acquire_generation_conflict() -> None:
    client = FakeStorageClient()
    first = _scheduler_lease(client, "scheduler-1")
    second = _scheduler_lease(client, "scheduler-2")

    assert first.acquire() is True
    assert second.acquire() is False

    bucket = client.bucket("unit-test-bucket")
    stored = _payload(bucket, "locks/test/annual-scheduler-unit-test.lock")
    assert stored["lock_owner"] == "scheduler-1"


def test_gcs_scheduler_lease_heartbeat_stops_when_owner_is_lost() -> None:
    client = FakeStorageClient()
    lease = _scheduler_lease(client, "scheduler-1")
    assert lease.acquire() is True

    bucket = client.bucket("unit-test-bucket")
    blob_name = "locks/test/annual-scheduler-unit-test.lock"
    payload = _payload(bucket, blob_name)
    payload["lock_owner"] = "scheduler-2"
    _store_payload(bucket, blob_name, payload)

    assert lease.heartbeat() is False


def test_gcs_scheduler_lease_does_not_reclaim_expired_existing_lock() -> None:
    client = FakeStorageClient()
    first = _scheduler_lease(client, "scheduler-1", ttl_minutes=1)
    second = _scheduler_lease(client, "scheduler-2", ttl_minutes=1)
    assert first.acquire() is True

    bucket = client.bucket("unit-test-bucket")
    blob_name = "locks/test/annual-scheduler-unit-test.lock"
    expired = _payload(bucket, blob_name)
    expired["lease_expires_at"] = (utc_now() - timedelta(minutes=5)).isoformat()
    _store_payload(bucket, blob_name, expired)

    assert second.acquire() is False
    assert _payload(bucket, blob_name)["lock_owner"] == "scheduler-1"
