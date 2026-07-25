import sqlite3

import pytest

from app.migrations import migrate
from app.multichannel.handoff import OwnershipConflict, release_ownership, take_over, transfer_ownership
from app.multichannel.routing import RouteConfig, route_work
from app.multichannel.worker import (StaleClaim, WorkerBusy, WorkerCoordinator,
                                     claim_next, complete, recover_expired)


@pytest.fixture
def database(tmp_path):
    tmp_path.joinpath(".multicanal-identity.json").write_text(
        '{"sentinel":"proteccion360-multicanal-v1","deployment_id":"test"}', encoding="utf-8"
    )
    target = tmp_path / "proteccion360_multicanal.db"
    migrate("multicanal", target, tmp_path, "test")
    with sqlite3.connect(target) as db:
        db.execute("INSERT INTO channel_connections VALUES ('conn', 'telegram', 'ready')")
        db.execute("INSERT INTO contacts(id, display_name) VALUES ('contact', 'Ada')")
        db.execute("INSERT INTO channel_identities VALUES ('identity', 'conn', 'contact', 'u', NULL)")
        db.execute("INSERT INTO chats(id, identity_id) VALUES ('chat', 'identity')")
        db.execute("INSERT INTO messages(id, chat_id, connection_id, provider_event_id, direction, text_type, content, status, sequence) VALUES ('m1','chat','conn','e1','inbound','text','one','accepted',1)")
        db.execute("INSERT INTO work_items(id, message_id, kind, cycle, status) VALUES ('w1','m1','inbound',1,'ready')")
    return target


def test_ordering_claims_earlier_item_and_recovery_blocks_overtaking(database):
    with sqlite3.connect(database) as db:
        db.execute("INSERT INTO messages(id, chat_id, connection_id, provider_event_id, direction, text_type, content, status, sequence) VALUES ('m2','chat','conn','e2','inbound','text','two','accepted',2)")
        db.execute("INSERT INTO work_items(id, message_id, kind, cycle, status) VALUES ('w2','m2','inbound',1,'ready')")
        WorkerCoordinator(db, "worker-a").acquire(now=1)
        first = claim_next(db, "worker-a", now=10)
        assert first.work_id == "w1"
        assert claim_next(db, "worker-a", now=11) is None
        recover_expired(db, now=71)
        WorkerCoordinator(db, "worker-a").acquire(now=71)
        assert claim_next(db, "worker-a", now=72).work_id == "w1"


def test_stale_and_competing_workers_are_fenced(database):
    with sqlite3.connect(database) as db:
        owner = WorkerCoordinator(db, "worker-a")
        owner.acquire(now=1)
        with pytest.raises(WorkerBusy):
            WorkerCoordinator(db, "worker-b").acquire(now=2)
        claim = claim_next(db, "worker-a", now=2)
        recover_expired(db, now=100)
        WorkerCoordinator(db, "worker-a").acquire(now=100)
        replacement = claim_next(db, "worker-a", now=101)
        with pytest.raises(StaleClaim):
            complete(db, claim, success=True, now=102)
        complete(db, replacement, success=True, now=102)


def test_retry_backoff_dead_letter_and_route_snapshot(database):
    with sqlite3.connect(database) as db:
        WorkerCoordinator(db, "worker-a").acquire(now=1)
        claim = claim_next(db, "worker-a", now=1)
        assert complete(db, claim, success=False, retryable=True, now=2).status == "retry_wait"
        claim = claim_next(db, "worker-a", now=7)
        for now in range(8, 15):
            result = complete(db, claim, success=False, retryable=False, now=now)
            if result.status == "dead":
                break
            claim = claim_next(db, "worker-a", now=now + 1)
        assert result.status == "dead"
        assert route_work("chat", None, RouteConfig("internal_agent", 4)) == "internal_agent"
        assert route_work("chat", "operator-a", RouteConfig("external_webhook", 5, "https://example.test/hook")) == "suppressed"


def test_takeover_and_transfer_are_continuous_and_fenced(database):
    with sqlite3.connect(database) as db:
        assert take_over(db, "chat", "operator-a").owner_version == 1
        with pytest.raises(OwnershipConflict):
            transfer_ownership(db, "chat", "operator-a", "operator-b", expected_version=0)
        assert transfer_ownership(db, "chat", "operator-a", "operator-b", expected_version=1).owner_version == 2
        assert release_ownership(db, "chat", "operator-b", expected_version=2).owner_version == 3


def test_transfer_loses_deterministic_stale_transition_race(database):
    with sqlite3.connect(database) as db:
        take_over(db, "chat", "operator-a")
        db.execute("""CREATE TRIGGER competing_transfer BEFORE UPDATE OF owner_id ON chats
                      WHEN NEW.owner_id = 'operator-b'
                      BEGIN UPDATE chats SET owner_id = 'operator-c', owner_version = owner_version + 1 WHERE id = NEW.id;
                      SELECT RAISE(IGNORE); END""")
        with pytest.raises(OwnershipConflict):
            transfer_ownership(db, "chat", "operator-a", "operator-b", expected_version=1)
        assert db.execute("SELECT owner_id, owner_version FROM chats WHERE id='chat'").fetchone() == ("operator-c", 2)
