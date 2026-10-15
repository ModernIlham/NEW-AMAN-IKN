"""The test-only adapter preserves bulk semantics and rejects unsupported sort."""

import mongomock
import pytest
from pymongo import UpdateOne


def test_bulk_compat_keeps_filters_inc_and_upsert(mongomock_update_sort_compat):
    collection = mongomock.MongoClient().test.assets
    collection.insert_many([
        {"id": "a", "version": 1, "scope": "own"},
        {"id": "b", "version": 1, "scope": "foreign"},
    ])
    result = collection.bulk_write([
        UpdateOne({"id": "a", "scope": "own"},
                  {"$set": {"state": "updated"}, "$inc": {"version": 1}}),
        UpdateOne({"id": "b", "scope": "own"}, {"$set": {"state": "wrong"}}),
        UpdateOne({"id": "new"},
                  {"$set": {"state": "created"}, "$setOnInsert": {"version": 1}},
                  upsert=True),
    ], ordered=False)
    assert (result.matched_count, result.modified_count, result.upserted_count) == (1, 1, 1)
    assert collection.find_one({"id": "a"})["version"] == 2
    assert collection.find_one({"id": "a"})["state"] == "updated"
    assert "state" not in collection.find_one({"id": "b"})
    assert collection.find_one({"id": "new"})["version"] == 1


def test_bulk_compat_does_not_hide_real_sort(mongomock_update_sort_compat):
    collection = mongomock.MongoClient().test.assets
    with pytest.raises(NotImplementedError, match="does not support sort"):
        collection.bulk_write([
            UpdateOne({"scope": "own"}, {"$set": {"state": "updated"}},
                      sort={"version": 1}),
        ])
