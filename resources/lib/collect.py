# -*- coding: utf-8 -*-
"""Tail kodi.log, classify problems, normalize into groupable signatures."""

import glob
import hashlib
import os
import re

_TIMESTAMP_RE = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+\s+\S+\s+')
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
    text = _TIMESTAMP_RE.sub('', text)
    text = _THREAD_RE.sub('T:N', text)
    text = _ADDR_RE.sub('0xADDR', text)
    text = _NUM_RE.sub('N', text)
    text = _SECRET_RE.sub(r'\1***', text)
    return text.strip()


def signature(normalized):
    return hashlib.sha1(normalized.encode('utf-8')).hexdigest()[:12]


def addon_of(line):
    match = _ADDON_RE.search(line)
    return match.group(1) if match else 'kodi'


def title_for(normalized, addon):
    first = normalized.splitlines()[0] if normalized else 'unknown error'
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
            if (len(current['lines']) < MAX_EVENT_LINES
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
