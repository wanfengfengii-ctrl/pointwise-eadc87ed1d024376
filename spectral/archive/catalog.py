from contextlib import contextmanager
import sqlite3
from uuid import uuid4

from spectral.archive.codec import encode_payload, decode_payload


class Catalog:
    def __init__(self, path):
        self.connection = sqlite3.connect(str(path), isolation_level=None)
        self.connection.execute("PRAGMA foreign_keys=ON")
        try:
            self.initialize()
        except BaseException:
            self.connection.close()
            raise

    def initialize(self):
        version = self.connection.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            raise ValueError("unsupported catalog version")
        with self.transaction():
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS records "
                "(id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL)")
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS heads "
                "(kind TEXT NOT NULL, source TEXT NOT NULL, "
                "revision TEXT NOT NULL REFERENCES records(id), "
                "PRIMARY KEY(kind,source))")
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS payloads "
                "(id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS artifacts "
                "(id TEXT PRIMARY KEY REFERENCES payloads(id), kind TEXT NOT NULL, "
                "logical_key TEXT NOT NULL UNIQUE, parents TEXT NOT NULL)")
            self.connection.execute("PRAGMA user_version=1")

    @contextmanager
    def transaction(self):
        if self.connection.in_transaction:
            raise RuntimeError("nested catalog transaction")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield self
            self.connection.execute("COMMIT")
        except BaseException:
            if self.connection.in_transaction:
                self.connection.execute("ROLLBACK")
            raise

    def _require_transaction(self):
        if not self.connection.in_transaction:
            raise RuntimeError("write requires transaction")

    def append_record(self, kind, payload, record_id=None):
        self._require_transaction()
        record_id = record_id or uuid4().hex
        self.connection.execute("INSERT INTO records VALUES (?,?,?)",
                                (record_id, kind, encode_payload(payload)))
        return record_id

    def read_record(self, record_id, kind=None):
        row = self.connection.execute(
            "SELECT kind,payload FROM records WHERE id=?", (record_id,)).fetchone()
        if row is None:
            raise KeyError(record_id)
        if kind is not None and row[0] != kind:
            raise ValueError("wrong source record kind")
        return {"id": record_id, "kind": row[0], "data": decode_payload(row[1])}

    def resolve_head(self, kind, source):
        row = self.connection.execute(
            "SELECT revision FROM heads WHERE kind=? AND source=?",
            (kind, source)).fetchone()
        if row is None:
            raise KeyError((kind, source))
        return row[0]

    def advance_head(self, kind, source, revision):
        self._require_transaction()
        self.read_record(revision, kind)
        self.connection.execute(
            "INSERT INTO heads VALUES (?,?,?) ON CONFLICT(kind,source) "
            "DO UPDATE SET revision=excluded.revision", (kind, source, revision))

    def stage_payload(self, artifact_id, payload):
        self._require_transaction()
        self.connection.execute("INSERT INTO payloads VALUES (?,?)",
                                (artifact_id, encode_payload(payload)))

    def stage_index(self, artifact_id, kind, logical_key, parents):
        self._require_transaction()
        self.connection.execute("INSERT INTO artifacts VALUES (?,?,?,?)",
                                (artifact_id, kind, logical_key, encode_payload(parents)))

    def find_publication(self, logical_key):
        row = self.connection.execute(
            "SELECT id FROM artifacts WHERE logical_key=?", (logical_key,)).fetchone()
        return None if row is None else row[0]

    def read_artifact(self, artifact_id):
        row = self.connection.execute(
            "SELECT a.kind,a.parents,p.payload FROM artifacts a "
            "JOIN payloads p ON p.id=a.id WHERE a.id=?", (artifact_id,)).fetchone()
        if row is None:
            raise KeyError(artifact_id)
        return {"id": artifact_id, "kind": row[0],
                "parents": decode_payload(row[1]), "data": decode_payload(row[2])}

    def counts(self):
        return {table: self.connection.execute(
            "SELECT count(*) FROM " + table).fetchone()[0]
                for table in ("records", "heads", "payloads", "artifacts")}

    def close(self):
        self.connection.close()
