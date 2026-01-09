"""
Tests for tamper-evident hash chain audit logging.

This test suite proves that the audit log's hash chain mechanically detects
tampering by:
1. Verifying hash chain integrity on valid logs
2. Detecting payload tampering (modifying event data)
3. Detecting chain break (modifying prev_hash)
4. Detecting reordering (modifying event_id)
5. Detecting hash forgery (modifying record_hash)
"""

import pytest
from datetime import datetime
from dataclasses import replace
from clarity_kernel import (
    AuditLogger,
    LogEntry,
    EventType,
    ResolutionOutcome,
    DecompositionStatus,
    ChainIntegrityViolation,
)


def test_empty_chain_is_valid():
    """Empty chain should verify successfully."""
    logger = AuditLogger(in_memory=True)
    assert logger.verify_chain() is True


def test_single_entry_chain_is_valid():
    """Single entry chain should verify successfully."""
    logger = AuditLogger(in_memory=True)

    logger.log_invariant_violation(
        invariant_id="I-1",
        kernel_state="IDLE",
        message="Test violation"
    )

    # Chain should be valid
    assert logger.verify_chain() is True

    # Verify genesis record properties
    entries = logger.get_all_entries()
    assert len(entries) == 1

    genesis = entries[0]
    assert genesis.event_id == 0
    assert genesis.prev_hash == "NULL"
    assert genesis.payload_hash != ""
    assert genesis.record_hash != ""


def test_multiple_entry_chain_is_valid():
    """Multi-entry chain should verify successfully."""
    logger = AuditLogger(in_memory=True)

    # Add multiple entries
    logger.log_invariant_violation("I-1", "IDLE", "Violation 1")
    logger.log_invariant_violation("I-2", "AUTHORIZED", "Violation 2")
    logger.log_invariant_violation("I-7", "WIDTH_OK", "Violation 3")

    # Chain should be valid
    assert logger.verify_chain() is True

    # Verify chain properties
    entries = logger.get_all_entries()
    assert len(entries) == 3

    # Verify sequential event_ids
    for i, entry in enumerate(entries):
        assert entry.event_id == i

    # Verify chain links
    assert entries[0].prev_hash == "NULL"
    assert entries[1].prev_hash == entries[0].record_hash
    assert entries[2].prev_hash == entries[1].record_hash


def test_payload_tampering_is_detected():
    """Tampering with event data should break the chain."""
    logger = AuditLogger(in_memory=True)

    # Add entries
    logger.log_invariant_violation("I-1", "IDLE", "Original message")
    logger.log_invariant_violation("I-2", "AUTHORIZED", "Another message")

    # Verify chain is valid before tampering
    assert logger.verify_chain() is True

    # TAMPER: Modify the message in the first entry
    # This simulates an attacker trying to change the logged event data
    tampered_entry = replace(
        logger._entries[0],
        message="TAMPERED MESSAGE"
    )
    logger._entries[0] = tampered_entry

    # Verification should fail with ChainIntegrityViolation
    with pytest.raises(ChainIntegrityViolation) as exc_info:
        logger.verify_chain()

    # Verify exception details
    assert exc_info.value.failed_at_index == 0
    assert "payload tampering detected" in str(exc_info.value)


def test_prev_hash_tampering_is_detected():
    """Tampering with prev_hash should break the chain."""
    logger = AuditLogger(in_memory=True)

    # Add entries
    logger.log_invariant_violation("I-1", "IDLE", "Message 1")
    logger.log_invariant_violation("I-2", "AUTHORIZED", "Message 2")
    logger.log_invariant_violation("I-7", "WIDTH_OK", "Message 3")

    # Verify chain is valid before tampering
    assert logger.verify_chain() is True

    # TAMPER: Modify prev_hash of middle entry
    # This simulates an attacker trying to break the chain linkage
    tampered_entry = replace(
        logger._entries[1],
        prev_hash="FORGED_HASH_1234567890abcdef"
    )
    logger._entries[1] = tampered_entry

    # Verification should fail
    with pytest.raises(ChainIntegrityViolation) as exc_info:
        logger.verify_chain()

    # Should detect either record_hash mismatch or chain link break
    assert exc_info.value.failed_at_index == 1
    assert ("chain link broken" in str(exc_info.value) or
            "record_hash mismatch" in str(exc_info.value))


def test_event_id_tampering_is_detected():
    """Tampering with event_id should break the chain."""
    logger = AuditLogger(in_memory=True)

    # Add entries
    logger.log_invariant_violation("I-1", "IDLE", "Message 1")
    logger.log_invariant_violation("I-2", "AUTHORIZED", "Message 2")

    # Verify chain is valid before tampering
    assert logger.verify_chain() is True

    # TAMPER: Modify event_id (simulate reordering attack)
    tampered_entry = replace(
        logger._entries[1],
        event_id=99  # Invalid event_id
    )
    logger._entries[1] = tampered_entry

    # Verification should fail
    with pytest.raises(ChainIntegrityViolation) as exc_info:
        logger.verify_chain()

    # Should detect event_id mismatch (verified before payload hash)
    assert exc_info.value.failed_at_index == 1
    assert ("invalid event_id" in str(exc_info.value) or
            "payload tampering detected" in str(exc_info.value))


def test_record_hash_forgery_is_detected():
    """Forging record_hash should be detected."""
    logger = AuditLogger(in_memory=True)

    # Add entries
    logger.log_invariant_violation("I-1", "IDLE", "Message 1")
    logger.log_invariant_violation("I-2", "AUTHORIZED", "Message 2")

    # Verify chain is valid before tampering
    assert logger.verify_chain() is True

    # TAMPER: Modify record_hash directly
    # This simulates an attacker trying to forge the hash
    tampered_entry = replace(
        logger._entries[0],
        record_hash="FORGED_HASH_1234567890abcdef"
    )
    logger._entries[0] = tampered_entry

    # Verification should fail
    with pytest.raises(ChainIntegrityViolation) as exc_info:
        logger.verify_chain()

    # Should detect record_hash mismatch or chain link break
    assert exc_info.value.failed_at_index in [0, 1]


def test_entry_deletion_breaks_chain():
    """Deleting an entry should break the chain."""
    logger = AuditLogger(in_memory=True)

    # Add entries
    logger.log_invariant_violation("I-1", "IDLE", "Message 1")
    logger.log_invariant_violation("I-2", "AUTHORIZED", "Message 2")
    logger.log_invariant_violation("I-7", "WIDTH_OK", "Message 3")

    # Verify chain is valid before deletion
    assert logger.verify_chain() is True

    # DELETE: Remove middle entry
    # This simulates an attacker trying to delete a record
    del logger._entries[1]

    # Verification should fail
    with pytest.raises(ChainIntegrityViolation) as exc_info:
        logger.verify_chain()

    # Should detect event_id mismatch or chain link break
    assert exc_info.value.failed_at_index in [1, 2]


def test_entry_insertion_breaks_chain():
    """Inserting an entry should break the chain."""
    logger = AuditLogger(in_memory=True)

    # Add entries
    logger.log_invariant_violation("I-1", "IDLE", "Message 1")
    logger.log_invariant_violation("I-2", "AUTHORIZED", "Message 2")

    # Verify chain is valid before insertion
    assert logger.verify_chain() is True

    # INSERT: Create fake entry and insert it
    fake_entry = LogEntry(
        timestamp=datetime.now(),
        event_type=EventType.INVARIANT_VIOLATION,
        kernel_state="FAKE",
        ssl_version="v1.2.0",
        invariants_evaluated={"I-99": False},
        message="FAKE ENTRY",
        event_id=1,  # Try to insert between 0 and 1
        prev_hash=logger._entries[0].record_hash,
        payload_hash="FAKE_PAYLOAD_HASH",
        record_hash="FAKE_RECORD_HASH"
    )
    logger._entries.insert(1, fake_entry)

    # Verification should fail
    with pytest.raises(ChainIntegrityViolation) as exc_info:
        logger.verify_chain()


def test_reordering_entries_breaks_chain():
    """Reordering entries should break the chain."""
    logger = AuditLogger(in_memory=True)

    # Add entries
    logger.log_invariant_violation("I-1", "IDLE", "Message 1")
    logger.log_invariant_violation("I-2", "AUTHORIZED", "Message 2")
    logger.log_invariant_violation("I-7", "WIDTH_OK", "Message 3")

    # Verify chain is valid before reordering
    assert logger.verify_chain() is True

    # REORDER: Swap first two entries
    logger._entries[0], logger._entries[1] = logger._entries[1], logger._entries[0]

    # Verification should fail
    with pytest.raises(ChainIntegrityViolation) as exc_info:
        logger.verify_chain()

    # Should detect event_id mismatch
    assert exc_info.value.failed_at_index in [0, 1]


def test_genesis_prev_hash_tampering_is_detected():
    """Tampering with genesis prev_hash should be detected."""
    logger = AuditLogger(in_memory=True)

    # Add entry
    logger.log_invariant_violation("I-1", "IDLE", "Message 1")

    # Verify chain is valid before tampering
    assert logger.verify_chain() is True

    # TAMPER: Change genesis prev_hash from NULL
    tampered_entry = replace(
        logger._entries[0],
        prev_hash="NOT_NULL"
    )
    logger._entries[0] = tampered_entry

    # Verification should fail
    with pytest.raises(ChainIntegrityViolation) as exc_info:
        logger.verify_chain()

    assert exc_info.value.failed_at_index == 0
    assert "Genesis record has invalid prev_hash" in str(exc_info.value)


def test_complex_tampering_scenario():
    """
    Simulate a sophisticated attack: modify payload AND recompute hashes.

    This tests that the chain is cryptographically secure even if an attacker
    tries to recompute hashes after modification.
    """
    logger = AuditLogger(in_memory=True)

    # Add entries
    logger.log_invariant_violation("I-1", "IDLE", "Legitimate message")
    logger.log_invariant_violation("I-2", "AUTHORIZED", "Another message")
    logger.log_invariant_violation("I-7", "WIDTH_OK", "Third message")

    # Verify chain is valid
    assert logger.verify_chain() is True

    # SOPHISTICATED ATTACK: Modify payload AND recompute payload_hash
    # (but can't recompute record_hash without breaking the chain)
    tampered_entry = replace(
        logger._entries[1],
        message="ATTACKER MODIFIED THIS",
    )

    # Recompute payload_hash for tampered entry
    new_payload_hash = tampered_entry.compute_payload_hash()
    tampered_entry = replace(
        tampered_entry,
        payload_hash=new_payload_hash
    )

    # Try to recompute record_hash
    new_record_hash = LogEntry.compute_record_hash(
        tampered_entry.prev_hash,
        new_payload_hash
    )
    tampered_entry = replace(
        tampered_entry,
        record_hash=new_record_hash
    )

    # Replace entry with tampered version
    logger._entries[1] = tampered_entry

    # Verification should STILL fail because next entry's prev_hash
    # no longer matches this entry's new record_hash
    with pytest.raises(ChainIntegrityViolation) as exc_info:
        logger.verify_chain()

    # Should detect chain link break at entry 2
    assert exc_info.value.failed_at_index == 2
    assert "chain link broken" in str(exc_info.value)


def test_hash_chain_persists_across_logger_instances():
    """
    Verify that hash chain can be verified after serialization/deserialization.

    This tests that the tamper-evidence property is preserved even if
    logs are written to disk and loaded later.
    """
    # Note: This test verifies the hash chain concept, not actual file persistence
    # (file persistence would require deserialization logic)

    logger = AuditLogger(in_memory=True)

    # Add entries
    logger.log_invariant_violation("I-1", "IDLE", "Message 1")
    logger.log_invariant_violation("I-2", "AUTHORIZED", "Message 2")

    # Get entries
    entries = logger.get_all_entries()

    # Simulate loading into new logger
    new_logger = AuditLogger(in_memory=True)
    new_logger._entries = entries.copy()

    # Verification should succeed
    assert new_logger.verify_chain() is True

    # Tamper with copied entries
    tampered = replace(entries[0], message="TAMPERED")
    new_logger._entries[0] = tampered

    # Verification should fail
    with pytest.raises(ChainIntegrityViolation):
        new_logger.verify_chain()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
