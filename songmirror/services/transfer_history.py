"""Persistent transfer snapshots and a state-change audit trail in the data volume."""

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from ..diagnostics import redact_data


def utc_now():
    return datetime.now(timezone.utc).isoformat()


TERMINAL = {"done", "error", "stopped"}
FIELDS = {"id", "status", "source", "dest", "added", "deferred", "preserve_order",
          "chronology_replayed", "unavailable", "total", "processed", "phase", "written",
          "write_total", "conflicts", "error", "created_at", "started_at", "finished_at",
          "updated_at"}
ENDPOINT_FIELDS = {"account", "provider", "name", "playlist_id", "playlist_name"}


class TransferHistory:
    def __init__(self, data_dir):
        self.path = Path(data_dir) / "transfer_history.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        fd = os.open(self.path, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(fd)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS transfers (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, status TEXT NOT NULL,
                    source_account TEXT, dest_account TEXT, source_provider TEXT, dest_provider TEXT,
                    source_name TEXT, dest_name TEXT, search_text TEXT NOT NULL, snapshot TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS transfers_created ON transfers(created_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS transfers_status ON transfers(status);
                CREATE TABLE IF NOT EXISTS transfer_events (
                    sequence INTEGER PRIMARY KEY, transfer_id TEXT NOT NULL,
                    event TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS events_transfer ON transfer_events(transfer_id, sequence);
            """)

    @contextmanager
    def _connect(self):
        # No long-lived connection crosses the worker/event-loop thread boundary.
        with self._lock:
            db = sqlite3.connect(self.path, timeout=10)
            db.row_factory = sqlite3.Row
            try:
                with db:
                    yield db
            finally:
                db.close()

    def save(self, job, *, kind=None):
        snapshot = {k: v for k, v in job.items() if k in FIELDS}
        for side in ("source", "dest"):
            snapshot[side] = {k: v for k, v in job.get(side, {}).items() if k in ENDPOINT_FIELDS}
        # Make an independent JSON snapshot; runtime callables, credentials and
        # the private original-track cache never enter this store.
        snapshot = redact_data(json.loads(json.dumps(snapshot)))
        now = utc_now()
        snapshot.setdefault("created_at", now)
        snapshot["updated_at"] = now
        if snapshot["status"] in TERMINAL:
            snapshot["finished_at"] = snapshot.get("finished_at") or now
        else:
            snapshot["finished_at"] = None
        source, dest = snapshot["source"], snapshot["dest"]
        with self._connect() as db:
            previous = db.execute("SELECT snapshot FROM transfers WHERE id=?", (job["id"],)).fetchone()
            previous = json.loads(previous[0]) if previous else None
            changed = previous is None or any(
                previous.get(key) != snapshot.get(key) for key in ("status", "phase", "error")
            )
            if changed or kind:
                event = {"at": now, "kind": kind or snapshot["status"],
                         "status": snapshot["status"], "phase": snapshot.get("phase"),
                         "added": snapshot.get("added", 0), "error": snapshot.get("error")}
                db.execute("INSERT INTO transfer_events(transfer_id,event) VALUES (?,?)",
                           (job["id"], json.dumps(event)))
            db.execute("""INSERT OR REPLACE INTO transfers VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (
                snapshot["id"], snapshot["created_at"], snapshot["status"],
                source.get("account"), dest.get("account"), source.get("provider"), dest.get("provider"),
                source.get("name"), dest.get("name"),
                " ".join(str(endpoint.get(key) or "") for endpoint in (source, dest)
                         for key in ("playlist_name", "playlist_id")).lower(), json.dumps(snapshot),
            ))
        return snapshot

    def get(self, job_id):
        with self._connect() as db:
            row = db.execute("SELECT snapshot FROM transfers WHERE id=?", (job_id,)).fetchone()
            if not row:
                return None
            snapshot = json.loads(row[0])
            snapshot["events"] = [json.loads(e[0]) for e in db.execute(
                "SELECT event FROM transfer_events WHERE transfer_id=? ORDER BY sequence", (job_id,))]
            return redact_data(snapshot)

    def list(self, *, status=None, account=None, provider=None, search="", after=None,
             before=None, limit=25, offset=0):
        clauses, values = [], []
        for value, clause in ((status, "status=?"), (account, "(source_account=? OR dest_account=?)"),
                              (provider, "(source_provider=? OR dest_provider=?)"),
                              (after, "created_at>=?"), (before, "created_at<?")):
            if value:
                clauses.append(clause)
                values.extend([value] * clause.count("?"))
        if search:
            clauses.append("instr(search_text,?)>0")
            values.append(search.lower())
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connect() as db:
            total = db.execute("SELECT count(*) FROM transfers" + where, values).fetchone()[0]
            rows = db.execute("SELECT snapshot FROM transfers" + where +
                              " ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
                              [*values, min(100, max(1, limit)), max(0, offset)]).fetchall()
            accounts = db.execute("""SELECT source_account,source_name,dest_account,dest_name
                FROM transfers ORDER BY created_at,id""").fetchall()
            providers = db.execute("""SELECT source_provider FROM transfers
                UNION SELECT dest_provider FROM transfers ORDER BY 1""").fetchall()
        # A renamed account remains filterable once, using its most recent transfer's label.
        return {"items": [redact_data(json.loads(row[0])) for row in rows], "total": total,
                "accounts": sorted({id: {"id": id, "name": name or id}
                                    for row in accounts for id, name in (tuple(row[:2]), tuple(row[2:]))
                                    if id}.values(), key=lambda a: a["name"]),
                "providers": [row[0] for row in providers if row[0]]}

    def recover(self):
        """A restarted process cannot resume a worker's private in-memory spec."""
        with self._connect() as db:
            rows = db.execute("SELECT snapshot FROM transfers WHERE status NOT IN ('done','error','stopped')").fetchall()
            for row in rows:
                job = json.loads(row[0])
                job.update(status="error", error="Transfer interrupted by a server restart. Tracks already copied are kept. Start a new copy to continue.")
                self.save(job, kind="interrupted")
