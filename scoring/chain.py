"""Append-only, hash-chained evidence store — the Scoring Layer's own.

Format-compatible with the Excavator's chain discipline (read from
``~/workspace/ultimate-eval-map/excavator/excavator/store.py``): one
JSON object per line::

    {seq, ts, type, prev_hash, hash, payload, hash_version}
    hash = sha256(canonical({seq, ts, type, prev_hash, payload}))
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    genesis prev_hash = "0" * 64

**Format v2 (Session 1.1, audit fix F1).** The v1 formula hashed only
``prev_hash + payload`` — a record's ``type``, ``ts``, and ``seq``
could be edited without breaking verification, and the typed
interpretation of the evidence (e.g. which records are decisions)
changed underneath a passing ``verify``. The v2 hash covers
``seq``, ``ts``, ``type``, ``prev_hash``, and ``payload`` together.
Every record carries ``hash_version: 2``. Chains written under v1
are NOT verifiable under v2 and are never silently mis-verified:
:meth:`Store.verify_chain` rejects them with an explicit
"old chain format" error, and :meth:`Store.append` refuses to extend
them. Regenerate a v1 chain through the CLI's seal/run flow instead.

This store writes ONLY to the Scoring Layer's own chain file
(``data/chain.jsonl`` by convention). It never touches the
Excavator's chain. Record types here: ``task_card``, ``run``,
``verdicts``, ``queue_decision``. Append-only by design: there is no
prune/delete API.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

GENESIS_PREV_HASH = "0" * 64

RECORD_TYPES = ("task_card", "run", "verdicts", "queue_decision")

# v1 (Session 1): hash = sha256(prev_hash + canonical(payload)).
# v2 (Session 1.1): hash covers seq/ts/type/prev_hash/payload.
CHAIN_FORMAT_VERSION = 2


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def compute_hash(seq: int, ts: str, type: str, prev_hash: str, payload) -> str:
    """The v2 record hash: every field that gives a record its meaning
    is inside the hash, so no field can be edited underneath a
    passing verification."""
    return hashlib.sha256(
        canonical({
            "seq": seq,
            "ts": ts,
            "type": type,
            "prev_hash": prev_hash,
            "payload": payload,
        }).encode("utf-8")
    ).hexdigest()


def _is_parseable_ts(value) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _old_format_error(seq, found) -> str:
    return (
        f"old chain format at seq {seq}: hash_version is {found!r}, "
        f"expected {CHAIN_FORMAT_VERSION}; chains written under the "
        "v1 hash formula cannot be verified — regenerate the chain "
        "through the CLI's seal/run flow"
    )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class Store:
    """An append-only hash-chained JSONL evidence store."""

    def __init__(self, path):
        self.path = Path(path)

    def _read_lines(self) -> list[str]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as fh:
            return [line for line in fh.read().splitlines() if line.strip()]

    def _tail(self, lines: list[str]) -> tuple[int, str]:
        if not lines:
            return 1, GENESIS_PREV_HASH
        last = json.loads(lines[-1])
        return int(last["seq"]) + 1, str(last["hash"])

    def append(self, type: str, payload) -> dict:
        if type not in RECORD_TYPES:
            raise ValueError(f"unknown record type: {type!r}")
        canonical(payload)  # fail fast before anything touches the file
        lines = self._read_lines()
        if lines:
            last = json.loads(lines[-1])
            if last.get("hash_version") != CHAIN_FORMAT_VERSION:
                raise ValueError(
                    "refusing to append: "
                    + _old_format_error(last.get("seq"),
                                        last.get("hash_version"))
                )
        seq, prev_hash = self._tail(lines)
        ts = _utc_now_iso()
        record = {
            "seq": seq,
            "ts": ts,
            "type": type,
            "prev_hash": prev_hash,
            "hash": compute_hash(seq, ts, type, prev_hash, payload),
            "payload": payload,
            "hash_version": CHAIN_FORMAT_VERSION,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return record

    def iter_records(self, type: str | None = None):
        for line in self._read_lines():
            record = json.loads(line)
            if type is None or record.get("type") == type:
                yield record

    def verify_chain(self) -> dict:
        """Verify the whole chain.

        Returns {ok, records, first_bad_seq, error}. A record is bad
        if its line does not parse, its seq is not its 1-based
        position, its type is not a known record type, its ts is not
        a parseable timestamp, its prev_hash does not link, or its
        hash does not recompute from seq + ts + type + prev_hash +
        payload under the v2 formula. A record written under the v1
        formula (no/older ``hash_version``) fails with an explicit
        old-format ``error`` — it is rejected, never reinterpreted.
        """
        lines = self._read_lines()
        total = len(lines)

        def bad(bad_seq, error=None):
            return {"ok": False, "records": total,
                    "first_bad_seq": bad_seq, "error": error}

        prev_hash = GENESIS_PREV_HASH
        for idx, line in enumerate(lines):
            expected_seq = idx + 1
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                return bad(expected_seq)
            if not isinstance(record, dict):
                return bad(expected_seq)
            seq = record.get("seq")
            bad_seq = seq if isinstance(seq, int) else expected_seq
            if seq != expected_seq:
                return bad(bad_seq)
            if record.get("hash_version") != CHAIN_FORMAT_VERSION:
                return bad(bad_seq,
                           _old_format_error(bad_seq,
                                             record.get("hash_version")))
            rtype = record.get("type")
            if rtype not in RECORD_TYPES:
                return bad(bad_seq)
            ts = record.get("ts")
            if not _is_parseable_ts(ts):
                return bad(bad_seq)
            if record.get("prev_hash") != prev_hash:
                return bad(bad_seq)
            if "payload" not in record or record.get("hash") != compute_hash(
                seq, ts, rtype, prev_hash, record["payload"]
            ):
                return bad(bad_seq)
            prev_hash = record["hash"]
        return {"ok": True, "records": total,
                "first_bad_seq": None, "error": None}
