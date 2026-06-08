import json
import unittest

from google.cloud.exceptions import NotFound, PreconditionFailed

from scripts.pipeline_control.state import ControlConfig, PipelineStateStore


class FakeBlob:
    def __init__(self, bucket, name):
        self.bucket = bucket
        self.name = name
        self.generation = None

    def _record(self):
        return self.bucket.objects.get(self.name)

    def upload_from_string(self, data, content_type=None, if_generation_match=None):
        record = self._record()
        if if_generation_match == 0:
            if record is not None:
                raise PreconditionFailed("object already exists")
        elif if_generation_match is not None:
            if record is None or record["generation"] != if_generation_match:
                raise PreconditionFailed("generation mismatch")

        next_generation = 1 if record is None else record["generation"] + 1
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
        self.generation = record["generation"]

    def download_as_bytes(self, if_generation_match=None):
        record = self._record()
        if record is None:
            raise NotFound("object missing")
        if if_generation_match is not None and record["generation"] != if_generation_match:
            raise PreconditionFailed("generation mismatch")
        self.generation = record["generation"]
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
    def __init__(self, name):
        self.name = name
        self.objects = {}

    def blob(self, name):
        return FakeBlob(self, name)


class FakeStorageClient:
    def __init__(self):
        self.buckets = {}

    def bucket(self, name):
        if name not in self.buckets:
            self.buckets[name] = FakeBucket(name)
        return self.buckets[name]


class PipelineStateStoreLockTest(unittest.TestCase):
    def setUp(self):
        config = ControlConfig(
            project_id="unit-test-project",
            region="asia-east2",
            bq_location="asia-east2",
            lock_bucket="unit-test-bucket",
            lock_prefix="locks/test",
        )
        self.store = PipelineStateStore(config)
        self.store._storage_client = FakeStorageClient()
        self.lock_key = "ashare_warehouse_window_refresh"
        self.owner = "workflow-execution-1"

    def test_lock_lifecycle_acquire_lookup_heartbeat_release(self):
        acquired = self.store.acquire_lock(
            lock_key=self.lock_key,
            owner=self.owner,
            lease_seconds=120,
            metadata={"warehouse_mode": "qa_only"},
        )

        self.assertTrue(acquired["acquired"])
        self.assertEqual(acquired["generation"], 1)
        self.assertIn("lock_path", acquired)

        lookup_generation = self.store.lock_generation_for_owner(
            lock_key=self.lock_key,
            owner=self.owner,
        )
        self.assertEqual(lookup_generation, acquired["generation"])

        heartbeat = self.store.heartbeat_lock(
            lock_key=self.lock_key,
            generation=lookup_generation,
            lease_seconds=240,
        )
        self.assertEqual(heartbeat["lock_path"], acquired["lock_path"])
        self.assertGreater(heartbeat["generation"], lookup_generation)

        bucket = self.store._storage_client.bucket("unit-test-bucket")
        stored_payload = json.loads(bucket.objects[self._lock_blob_name()]["data"].decode("utf-8"))
        self.assertEqual(stored_payload["lock_owner"], self.owner)
        self.assertEqual(stored_payload["warehouse_mode"], "qa_only")
        self.assertIn("lease_expires_at", stored_payload)
        self.assertIn("last_heartbeat_at", stored_payload)

        released = self.store.release_lock(
            lock_key=self.lock_key,
            generation=heartbeat["generation"],
        )
        self.assertTrue(released["released"])
        self.assertEqual(released["lock_path"], heartbeat["lock_path"])
        self.assertFalse(bucket.objects)

    def test_lock_generation_lookup_rejects_owner_mismatch(self):
        self.store.acquire_lock(
            lock_key=self.lock_key,
            owner=self.owner,
            lease_seconds=120,
        )

        with self.assertRaises(RuntimeError):
            self.store.lock_generation_for_owner(
                lock_key=self.lock_key,
                owner="different-workflow-execution",
            )

    def _lock_blob_name(self):
        return "locks/test/ashare_warehouse_window_refresh.lock"


if __name__ == "__main__":
    unittest.main()
