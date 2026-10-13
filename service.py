# -*- coding: utf-8 -*-
"""Bug Tracker service: collect, group, file Kodi problems."""

import os
import sys
import time
import glob
import hashlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'resources', 'lib'))

import collect
import report
import store as store_mod


def _kodi():
    import xbmc
    import xbmcaddon
    import xbmcgui
    import xbmcvfs
    return xbmc, xbmcaddon, xbmcgui, xbmcvfs


class Tracker(object):
    def __init__(self):
        xbmc, xbmcaddon, xbmcgui, xbmcvfs = _kodi()
        self._xbmc = xbmc
        self._xbmcgui = xbmcgui
        self.addon = xbmcaddon.Addon()
        self.monitor = xbmc.Monitor()
        profile = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        self.store = store_mod.Store(os.path.join(profile, 'reports.db'))
        self.store.regroup()
        self.log_path = xbmcvfs.translatePath('special://logpath/kodi.log')
        temp = xbmcvfs.translatePath('special://temp/')
        self.temp_dir = temp
        self._last_crash_scan = 0
        if self.store.get_state('log_cursor') is None and self.store.stats()['events']:
            # Upgrade from v1: old counts have no event positions. Do not replay
            # the current log and count the same history again.
            _, cursor = collect.read_log(self.log_path, {})
            try:
                cursor['offset'] = os.path.getsize(self.log_path)
            except OSError:
                pass
            self.store.set_state('log_cursor', cursor)
        try:
            self.box = xbmc.getInfoLabel('System.HostName') or 'kodi'
        except Exception:
            self.box = 'kodi'
        try:
            self.box += ' kodi-' + xbmc.getInfoLabel('System.BuildVersion')[:6]
        except Exception:
            pass
        self._last_flush = 0

    def setting(self, key, default=''):
        try:
            value = self.addon.getSetting(key)
            return value if value != '' else default
        except Exception:
            return default

    def notify(self, text):
        try:
            self._xbmcgui.Dialog().notification('Bug Tracker', text, time=4000)
        except Exception:
            pass

    def _handle(self, text, kind, event_key):
        normalized = collect.normalize(text)
        sig = collect.signature(normalized, kind)
        title = collect.title_for(normalized, collect.addon_of(text))
        is_new, count = self.store.record(sig, title, normalized[:4000], kind, event_key)
        if is_new and self.setting('notify_new', 'false') == 'true':
            self.notify(self.addon.getLocalizedString(32100) % title[:60])
        return sig

    def _collect(self):
        cursor = self.store.get_state('log_cursor', {})
        records, new_cursor = collect.read_log(self.log_path, cursor)
        pending = self.store.get_state('pending_traceback')
        if pending and cursor.get('identity') != new_cursor.get('identity'):
            text = '\n'.join(pending['lines'])
            event_key = hashlib.sha1((cursor.get('identity', '') + ':' + str(pending['offset']) + ':' + text).encode()).hexdigest()
            self._handle(text, 'traceback', event_key)
            pending = None
        events, pending = collect.log_events(records, pending)
        for text, kind, offset in events:
            event_key = hashlib.sha1((new_cursor.get('identity', '') + ':' + str(offset) + ':' + text).encode()).hexdigest()
            self._handle(text, kind, event_key)
        if new_cursor != cursor or events or records:
            self.store.set_state('pending_traceback', pending)
            self.store.set_state('log_cursor', new_cursor)
        if self.setting('send_crashlogs', 'true') == 'true' and time.monotonic() - self._last_crash_scan >= 60:
            self._last_crash_scan = time.monotonic()
            known = self.store.get_state('crash_files', {})
            paths = set(glob.glob(os.path.join(self.temp_dir, 'kodi_crash*.log'))
                        + glob.glob(os.path.join(os.path.expanduser('~'), 'kodi_crash*.log')))
            changed = False
            for path in sorted(paths):
                try:
                    stat = os.stat(path)
                except OSError:
                    continue
                stamp = [stat.st_mtime_ns, stat.st_size]
                if known.get(path) == stamp:
                    continue
                result = collect.read_crash(path)
                if result is None:
                    continue
                digest, text = result
                self._handle(text, 'crash', 'crash:' + digest)
                known[path] = stamp
                changed = True
            if changed:
                self.store.set_state('crash_files', known)

    def _send_all(self):
        token = self.setting('github_token')
        repo = self.setting('target_repo', 'maratdob118/kodi-reports')
        if not token or not repo or '/' not in repo:
            return 'missing token/repo'
        sent = 0
        for sig, title, sample, kind, first, last, count, _ in self.store.pending():
            try:
                number = report.find_issue(repo, sig, token)
            except Exception as exc:
                return 'search failed: %s' % exc
            body = report.render_body(self.box, sig, kind, sample, count, first, last)
            try:
                if number is None:
                    number = report.file_issue(repo, title, body, token)
                self.store.set_issue(sig, number)
                sent += 1
            except Exception as exc:
                return 'filing #%s failed: %s' % (title[:40], exc)
        return 'sent %d' % sent

    def run(self):
        while not self.monitor.abortRequested():
            if self.monitor.waitForAbort(5):
                break
            try:
                if self.setting('enabled', 'true') != 'true':
                    continue
                self._collect()
                flush = False
                try:
                    import xbmcgui
                    window = xbmcgui.Window(10000)
                    if window.getProperty('service.bugtracker.flush') == 'true':
                        window.clearProperty('service.bugtracker.flush')
                        flush = True
                except Exception:
                    pass
                auto = self.setting('auto_send', 'false') == 'true'
                if flush or (auto and time.time() - self._last_flush > 3600):
                    self._last_flush = time.time()
                    result = self._send_all()
                    if flush or result != 'sent 0':
                        self.notify(self.addon.getLocalizedString(32101) % result)
            except Exception as exc:
                try:
                    self._xbmc.log('Bug Tracker loop: %s' % exc, 1)
                except Exception:
                    pass
        self.store.close()


if __name__ == '__main__':
    Tracker().run()
