# -*- coding: utf-8 -*-
"""Bug Tracker service: collect, group, file Kodi problems."""

import os
import sys
import time

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
        self.log_path = xbmcvfs.translatePath('special://logpath/kodi.log')
        temp = xbmcvfs.translatePath('special://temp/')
        self.temp_dir = temp
        self.offset = 0
        self.inode = None
        self.last_crash_mtime = time.time()
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

    def _fresh_lines(self):
        try:
            st = os.stat(self.log_path)
        except OSError:
            return []
        key = (st.st_ino, st.st_size)
        if self.inode is None or key[0] != self.inode or key[1] < self.offset:
            self.inode = key[0]
            self.offset = 0 if key[1] < 1000000 else key[1] - 200000
        if key[1] == self.offset:
            return []
        try:
            with open(self.log_path, 'r', errors='replace') as handle:
                handle.seek(self.offset)
                lines = handle.read().splitlines()
                self.offset = handle.tell()
        except OSError:
            return []
        return lines

    def _handle(self, text, kind):
        normalized = collect.normalize(text)
        sig = collect.signature(normalized)
        title = collect.title_for(normalized, collect.addon_of(text))
        is_new, count = self.store.record(sig, title, normalized[:4000], kind)
        if is_new:
            self.notify(self.addon.getLocalizedString(32100) % title[:60])
        return sig

    def _collect(self):
        for text, kind in collect.extract_events(self._fresh_lines()):
            self._handle(text, kind)
        if self.setting('send_crashlogs', 'true') == 'true':
            for text, kind in collect.crashlog_events(self.temp_dir, self.last_crash_mtime):
                self.last_crash_mtime = time.time()
                self._handle(text, kind)

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
