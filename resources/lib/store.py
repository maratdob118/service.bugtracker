# -*- coding: utf-8 -*-
"""SQLite storage for grouped problems and send state."""

import os
import sqlite3
import time


_SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
    signature TEXT PRIMARY KEY,
    title TEXT,
    sample TEXT,
    kind TEXT,
    first_seen REAL,
    last_seen REAL,
    count INTEGER DEFAULT 1,
    issue_number INTEGER,
    last_sent REAL DEFAULT 0
);
"""


class Store(object):
    def __init__(self, path):
        directory = os.path.dirname(path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        self._db = sqlite3.connect(path)
        self._db.execute(_SCHEMA)
        self._db.commit()

    def close(self):
        try:
            self._db.close()
        except Exception:
            pass

    def record(self, sig, title, sample, kind):
        """Add an occurrence. Returns (is_new_group, count)."""
        now = time.time()
        row = self._db.execute(
            'SELECT count FROM groups WHERE signature=?', (sig,)).fetchone()
        if row is None:
            self._db.execute(
                'INSERT INTO groups (signature, title, sample, kind, first_seen, last_seen, count)'
                ' VALUES (?, ?, ?, ?, ?, ?, 1)', (sig, title, sample, kind, now, now))
            self._db.commit()
            return True, 1
        count = (row[0] or 0) + 1
        self._db.execute(
            'UPDATE groups SET last_seen=?, count=?, title=?, sample=? WHERE signature=?',
            (now, count, title, sample, sig))
        self._db.commit()
        return False, count

    def pending(self):
        """Groups never filed as an issue."""
        return self._db.execute(
            'SELECT signature, title, sample, kind, first_seen, last_seen, count,'
            ' COALESCE(issue_number, 0) FROM groups WHERE issue_number IS NULL'
            ' ORDER BY last_seen DESC').fetchall()

    def set_issue(self, sig, number):
        self._db.execute(
            'UPDATE groups SET issue_number=?, last_sent=? WHERE signature=?',
            (number, time.time(), sig))
        self._db.commit()

    def stats(self):
        row = self._db.execute(
            'SELECT COUNT(*), COALESCE(SUM(count), 0) FROM groups').fetchone()
        return {'groups': row[0], 'events': row[1]}
