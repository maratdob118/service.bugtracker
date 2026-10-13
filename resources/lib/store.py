# -*- coding: utf-8 -*-
"""SQLite storage for grouped problems and send state."""

import os
import sqlite3
import time
import json


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
        self._db.execute('CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT)')
        self._db.execute('CREATE TABLE IF NOT EXISTS events (event_key TEXT PRIMARY KEY)')
        self._db.commit()

    def close(self):
        try:
            self._db.close()
        except Exception:
            pass

    def get_state(self, key, default=None):
        row = self._db.execute('SELECT value FROM state WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_state(self, key, value):
        self._db.execute('INSERT OR REPLACE INTO state VALUES (?, ?)', (key, json.dumps(value)))
        self._db.commit()

    def regroup(self):
        """One-time stable-signature migration, preserving the historic counters."""
        if self.get_state('grouping_version') == 2:
            return
        import collect
        self._db.row_factory = sqlite3.Row
        rows = [dict(row) for row in self._db.execute('SELECT * FROM groups')]
        self._db.row_factory = None
        if rows:
            backup = sqlite3.connect(self._db.execute('PRAGMA database_list').fetchone()[2]
                                     + '.pre-v2.sqlite')
            try:
                self._db.backup(backup)
            finally:
                backup.close()
        merged = {}
        for row in rows:
            row['sample'] = collect.normalize(row['sample'] or '')
            sig = collect.signature(row['sample'], row['kind'])
            row['title'] = collect.title_for(row['sample'], collect.addon_of(row['sample']))
            if sig not in merged:
                row['signature'] = sig
                merged[sig] = row
                continue
            old = merged[sig]
            old['count'] += row['count']
            old['first_seen'] = min(old['first_seen'], row['first_seen'])
            if row['last_seen'] > old['last_seen']:
                old['last_seen'], old['sample'], old['title'] = row['last_seen'], row['sample'], row['title']
            old['issue_number'] = old['issue_number'] or row['issue_number']
            old['last_sent'] = max(old['last_sent'] or 0, row['last_sent'] or 0)
        with self._db:
            self._db.execute('DELETE FROM groups')
            for row in merged.values():
                self._db.execute('INSERT INTO groups VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                                 tuple(row[k] for k in ('signature', 'title', 'sample', 'kind',
                                                       'first_seen', 'last_seen', 'count',
                                                       'issue_number', 'last_sent')))
            self._db.execute('INSERT OR REPLACE INTO state VALUES (?, ?)',
                             ('grouping_version', '2'))

    def record(self, sig, title, sample, kind, event_key=None):
        """Add an occurrence. Returns (is_new_group, count)."""
        now = time.time()
        if event_key is not None:
            inserted = self._db.execute('INSERT OR IGNORE INTO events VALUES (?)', (event_key,))
            if not inserted.rowcount:
                self._db.commit()
                return False, 0
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
