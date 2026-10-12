# -*- coding: utf-8 -*-
"""Read-only views of the collector database; safe alongside the service."""
import datetime
import os
import re
import sqlite3
from urllib.parse import quote


def read_groups(path, order='count', kind=None):
    if not os.path.isfile(path):
        return []
    order_sql = 'count DESC, last_seen DESC' if order == 'count' else 'last_seen DESC, count DESC'
    connection = sqlite3.connect('file:' + quote(os.path.abspath(path), safe='/') + '?mode=ro',
                                 uri=True, timeout=3)
    connection.row_factory = sqlite3.Row
    try:
        query = 'SELECT * FROM groups'
        args = ()
        if kind is not None:
            query += ' WHERE kind=?'
            args = (kind,)
        query += ' ORDER BY ' + order_sql
        return [dict(row) for row in connection.execute(query, args)]
    finally:
        connection.close()


def short_title(row):
    title = row.get('title') or 'Unknown error'
    if row.get('kind') == 'traceback':
        lines = (row.get('sample') or '').splitlines()
        for line in reversed(lines):
            line = line.strip()
            if re.match(r'^[\w.]+(?:Error|Exception):', line):
                title = title.split(']', 1)[0] + '] ' + line
                break
    title = re.sub(r'https?://\S+', '[URL]', title)
    return title[:180]


def group_details(row):
    def stamp(value):
        return datetime.datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S') if value else '—'
    return ('Signature: {signature}\nType: {kind}\nOccurrences: {count}\n'
            'First collected: {first}\nLast collected: {last}\n'
            'GitHub issue: {issue}\n\n{sample}').format(
                signature=row['signature'], kind=row['kind'], count=row['count'],
                first=stamp(row.get('first_seen')), last=stamp(row.get('last_seen')),
                issue=row.get('issue_number') or '—', sample=row.get('sample') or '')
