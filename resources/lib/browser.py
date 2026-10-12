# -*- coding: utf-8 -*-
"""Read-only views of the collector database; safe alongside the service."""
import datetime
import os
import re
import sqlite3
from urllib.parse import quote

_ADDON = r'(?:plugin|script|service|repository|weather|skin|resource|screensaver|peripheral|inputstream)\.[\w.-]+'


def source_of(row):
    """Infer the source from the recorded message, not an adjacent log line.

    Returns (category, addon_id). Does not rewrite the collector database.
    Shared requests/urllib modules are not blamed for their caller's error.
    """
    sample = row.get('sample') or ''
    first = sample.splitlines()[0] if sample else ''
    if row.get('kind') == 'crash':
        return 'kodi', None  # thread stack paths do not prove which add-on caused a native crash
    explicit = re.search(r'\[(' + _ADDON + r')\]', first)
    if explicit:
        return 'addons', explicit.group(1)
    binary = re.search(r'AddOnLog:\s*(' + _ADDON + r'):', first)
    if binary:
        return 'addons', binary.group(1)
    repository = re.search(r'Repository add-on\s+(' + _ADDON + r')', first)
    if repository:
        return 'addons', repository.group(1)
    for addon in re.findall(r'[/\\]addons[/\\](' + _ADDON + r')[/\\]', sample):
        if not addon.startswith('script.module.'):
            return 'addons', addon
    text = (first + ' ' + (row.get('title') or '')).lower()
    for addon in ('weather.gismeteo', 'plugin.video.filmix', 'repository.elementumorg'):
        if addon in text:
            return 'addons', addon
    if '/youtube/' in text or 'googlevideo.com' in text:
        return 'addons', 'plugin.video.youtube'
    if 'plugin://plugin.video.elementum' in text:
        return 'addons', 'plugin.video.elementum'
    if '65223/' in text:
        return 'addons', 'repository.elementumorg'
    if any(word in text for word in ('dbus', '[xkb]', 'compose file', 'libreelec.tv',
                                      'out of memory', 'no space left on device',
                                      'read-only file system', 'i/o error')):
        return 'system', None
    return 'kodi', None


def source_sections(rows):
    sections = {'addons': [], 'system': [], 'kodi': []}
    for row in rows:
        sections[source_of(row)[0]].append(row)
    return sections


def addon_sections(rows):
    sections = {}
    for row in rows:
        category, addon = source_of(row)
        if category == 'addons':
            sections.setdefault(addon, []).append(row)
    return sorted(sections.items(), key=lambda item: (-sum(r['count'] for r in item[1]), item[0]))


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
    category, addon = source_of(row)
    return ('Source (inferred): {source}\nSignature: {signature}\nType: {kind}\nOccurrences: {count}\n'
            'First collected: {first}\nLast collected: {last}\n'
            'GitHub issue: {issue}\n\n{sample}').format(
                source=addon or category,
                signature=row['signature'], kind=row['kind'], count=row['count'],
                first=stamp(row.get('first_seen')), last=stamp(row.get('last_seen')),
                issue=row.get('issue_number') or '—', sample=row.get('sample') or '')
