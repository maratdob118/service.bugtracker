# -*- coding: utf-8 -*-
"""Tail kodi.log, classify problems, normalize into groupable signatures."""

import glob
import hashlib
import os
import re
from urllib.parse import urlsplit, urlunsplit

_TIMESTAMP_RE = re.compile(r'^\ufeff?\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+\s+\S+\s+', re.M)
_LOG_LINE_RE = re.compile(r'^\ufeff?\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+\s+')
_THREAD_RE = re.compile(r'\bT:\d+\b')
_ADDR_RE = re.compile(r'\b0x[0-9a-fA-F]+\b')
_NUM_RE = re.compile(r'(?<=[:=\s(])\d{4,}(?=[\s,).;:]|$)')
_SECRET_RE = re.compile(r'(?i)((?:passw(?:or)?d|token|secret|api[_-]?key)[=:]\s*)([^\s&;,"]+)')
_ADDON_RE = re.compile(r'\[([a-z0-9._-]+\.[a-z0-9._-]+)\]')

MAX_EVENT_LINES = 40


def strip_prefix(line):
    """Remove Kodi timestamp/thread/severity prefix for grouping."""
    line = _TIMESTAMP_RE.sub('', line)
    parts = line.split(None, 1)
    if parts and parts[0] in ('error', 'warning', 'info', 'debug'):
        line = parts[1] if len(parts) > 1 else ''
    return line.strip()


def normalize(text):
    """Scrub volatile bits (timestamps, tids, addresses, secrets)."""
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    text = _TIMESTAMP_RE.sub('', text)
    def clean_url(match):
        try:
            url = urlsplit(match.group(0))
            return urlunsplit((url.scheme, url.netloc.rsplit('@', 1)[-1], url.path, '', ''))
        except ValueError:
            return '[URL]'
    text = re.sub(r'https?://[^\s<>\"\']+', clean_url, text)
    text = _THREAD_RE.sub('T:N', text)
    text = _ADDR_RE.sub('0xADDR', text)
    text = _NUM_RE.sub('N', text)
    text = _SECRET_RE.sub(r'\1***', text)
    return text.strip()


def signature(normalized, kind=None):
    if kind == 'traceback' or normalized.startswith('Traceback'):
        from browser import source_of
        lines = normalized.splitlines()
        errors = [line.strip() for line in lines
                  if re.match(r'^[\w.]+(?:Error|Exception):', line.strip())]
        if errors:
            category, addon = source_of({'sample': normalized})
            normalized = (addon or category) + '|' + errors[-1]
    return hashlib.sha1(normalized.encode('utf-8')).hexdigest()[:12]


def addon_of(line):
    from browser import source_of
    category, addon = source_of({'sample': line})
    return addon or category


def title_for(normalized, addon):
    first = normalized.splitlines()[0] if normalized else 'unknown error'
    if first.startswith('Traceback'):
        errors = [l.strip() for l in normalized.splitlines()
                  if re.match(r'^[\w.]+(?:Error|Exception):', l.strip())]
        if errors:
            first = errors[-1]
    first = re.sub(r'^<\w+>:\s*', '', first)
    if len(first) > 110:
        first = first[:107] + '...'
    return '[%s] %s' % (addon, first)


def is_error_line(line):
    low = line.lower()
    return ' error ' in line or ' critical ' in line or low.rstrip().endswith(' error')


def extract_events(new_lines):
    """Split fresh log lines into (kind, text) events.

    Kinds: 'traceback', 'error', 'crash' is handled separately.
    Multiline Python tracebacks are joined into one event.
    """
    events = []
    current = None
    for line in new_lines:
        stripped = strip_prefix(line)
        if 'Traceback (most recent call last)' in line:
            if current:
                events.append(current)
            current = {'kind': 'traceback', 'lines': [line]}
            continue
        if current is not None:
            if (not _LOG_LINE_RE.match(line) and len(current['lines']) < MAX_EVENT_LINES
                    and (not stripped or line != line.lstrip() or not stripped[0].isalnum())):
                current['lines'].append(line)
                continue
            events.append(current)
            current = None
        if is_error_line(line):
            events.append({'kind': 'error', 'lines': [line]})
    if current:
        events.append(current)
    return [('\n'.join(ev['lines']), ev['kind']) for ev in events]


def read_log(path, cursor):
    """Byte cursor with a stable log-session identity and complete-line reads."""
    try:
        with open(path, 'rb') as handle:
            st = os.fstat(handle.fileno())
            header = handle.readline(1024)
            identity = hashlib.sha1(('%s:%s:' % (st.st_dev, st.st_ino)).encode() + header).hexdigest()
            offset = int(cursor.get('offset', 0)) if cursor.get('identity') == identity else 0
            if offset > st.st_size:
                offset = 0
            handle.seek(offset)
            data = handle.read(256 * 1024)
    except OSError:
        return [], cursor
    end = data.rfind(b'\n') + 1
    data = data[:end]
    records = []
    position = offset
    for line in data.splitlines(keepends=True):
        records.append((position, line.decode('utf-8', 'replace').rstrip('\r\n')))
        position += len(line)
    return records, {'identity': identity, 'offset': offset + len(data)}


def log_events(records, pending):
    """Keep traceback continuations across polling boundaries."""
    events = []
    current = pending
    for offset, line in records:
        if current and (_LOG_LINE_RE.match(line) or 'Traceback (most recent call last)' in line):
            events.append(('\n'.join(current['lines']), 'traceback', current['offset']))
            current = None
        if 'Traceback (most recent call last)' in line:
            current = {'offset': offset, 'lines': [line]}
        elif current:
            if len(current['lines']) < 120:
                current['lines'].append(line)
            if re.match(r'^[\w.]+(?:Error|Exception):', line.strip()):
                events.append(('\n'.join(current['lines']), 'traceback', current['offset']))
                current = None
        elif is_error_line(line):
            events.append((line, 'error', offset))
    if not records and current:
        events.append(('\n'.join(current['lines']), 'traceback', current['offset']))
        current = None
    return events, current


def read_crash(path):
    """Read a finished crash log, retaining the signal and main-thread stack."""
    try:
        with open(path, 'rb') as handle:
            digest = hashlib.sha256()
            head = bytearray()
            tail = b''
            while True:
                chunk = handle.read(256 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                if len(head) < 2 * 1024 * 1024:
                    head.extend(chunk)
                tail = (tail + chunk)[-8192:]
    except OSError:
        return None
    text = bytes(head).decode('utf-8', 'replace')
    if b'end kodi crash log' not in tail.lower():
        return None  # crash writer is still working, retry on the next scan
    lines = text.splitlines()
    summary = []
    for index, line in enumerate(lines):
        if 'Program terminated with signal' in line:
            summary.extend(lines[index:index + 3])
        if line.startswith('Thread 1 '):
            for frame in lines[index + 1:index + 30]:
                if not frame.startswith('#'):
                    break
                summary.append(frame)
            break
    if not summary:
        summary = lines[:45]
    return digest.hexdigest(), '\n'.join(summary)


def crashlog_events(temp_dir, since_mtime):
    """New kodi_crashlog files since SINCE_MTIME as (kind, text) events."""
    events = []
    try:
        files = glob.glob(os.path.join(temp_dir, 'kodi_crashlog*.log'))
    except Exception:
        return events
    for path in sorted(files):
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if mtime <= since_mtime:
            continue
        try:
            with open(path, 'r', errors='replace') as handle:
                head = [next(handle).rstrip('\n') for _ in range(45)]
        except (OSError, StopIteration):
            continue
        events.append(('crashlog %s\n%s' % (os.path.basename(path), '\n'.join(head)), 'crash'))
    return events
