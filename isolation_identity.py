"""Collision-resistant security principal leases for isolated executions."""

from __future__ import annotations

import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator


IDENTITY_SLOTS = 400_000_000
_CANDIDATE_UID_BASE = 100_000
_CANDIDATE_GID_BASE = 450_100_000
_CHECKER_UID_BASE = 900_100_000
_RPC_GID_BASE = 1_350_100_000


@dataclass(frozen=True)
class IsolationIdentity:
    """A session identifier and its disjoint candidate/checker principals."""

    session: str
    slot: int
    reservation: str
    candidate_uid: int
    candidate_gid: int
    checker_uid: int
    rpc_gid: int


class IsolationIdentityAllocator:
    """Reserve process-local identity slots for concurrent sandbox sessions."""

    def __init__(self, *, slots: int = IDENTITY_SLOTS) -> None:
        if slots <= 0 or slots > IDENTITY_SLOTS:
            raise ValueError(f"slots must be between 1 and {IDENTITY_SLOTS}")
        self._slots = slots
        self._active_slots: dict[int, str] = {}
        self._lock = threading.Lock()

    def acquire(self, *, session: str | None = None) -> IsolationIdentity:
        session = session or uuid.uuid4().hex
        try:
            initial_slot = int(session, 16) % self._slots
        except ValueError as error:
            raise ValueError("session must be a hexadecimal identifier") from error

        with self._lock:
            for offset in range(self._slots):
                slot = (initial_slot + offset) % self._slots
                if slot not in self._active_slots:
                    reservation = uuid.uuid4().hex
                    self._active_slots[slot] = reservation
                    break
            else:
                raise RuntimeError("no isolation identity slots are available")

        return IsolationIdentity(
            session=session,
            slot=slot,
            reservation=reservation,
            candidate_uid=_CANDIDATE_UID_BASE + slot,
            candidate_gid=_CANDIDATE_GID_BASE + slot,
            checker_uid=_CHECKER_UID_BASE + slot,
            rpc_gid=_RPC_GID_BASE + slot,
        )

    def release(self, identity: IsolationIdentity) -> None:
        with self._lock:
            if self._active_slots.get(identity.slot) != identity.reservation:
                raise RuntimeError("isolation identity was not active")
            del self._active_slots[identity.slot]


_ALLOCATOR = IsolationIdentityAllocator()


@contextmanager
def isolation_identity(*, session: str | None = None) -> Iterator[IsolationIdentity]:
    """Hold an identity reservation through the caller's complete cleanup path."""
    identity = _ALLOCATOR.acquire(session=session)
    try:
        yield identity
    finally:
        _ALLOCATOR.release(identity)
