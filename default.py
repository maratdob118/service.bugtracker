# -*- coding: utf-8 -*-
"""Kodi UI for browsing local grouped problems and requesting manual sends."""

import os
import sys

import xbmcaddon
import xbmcgui
import xbmcvfs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'resources', 'lib'))
from browser import group_details, read_groups, short_title

ADDON_ID = 'service.bugtracker'


def _flush():
    xbmcgui.Window(10000).setProperty('service.bugtracker.flush', 'true')
    addon = xbmcaddon.Addon(ADDON_ID)
    xbmcgui.Dialog().notification('Bug Tracker', addon.getLocalizedString(32027), time=2000)


def browse():
    addon = xbmcaddon.Addon(ADDON_ID)
    dialog = xbmcgui.Dialog()
    profile = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
    path = os.path.join(profile, 'reports.db')
    order, kind = 'count', None
    filters = [(32020, 'count', None), (32021, 'last_seen', None),
               (32022, 'last_seen', 'error'), (32023, 'last_seen', 'traceback'),
               (32024, 'last_seen', 'crash')]
    while True:
        try:
            rows = read_groups(path, order, kind)
        except Exception as exc:
            dialog.ok('Bug Tracker', addon.getLocalizedString(32028) + ': ' + str(exc))
            return
        heading = addon.getLocalizedString(32031) % (len(rows), sum(row['count'] for row in rows))
        actions = [addon.getLocalizedString(i) for i in (32025, 32026, 32015, 32029)]
        labels = actions + ['[%d] %s' % (row['count'], short_title(row)) for row in rows]
        selection = dialog.select(heading, labels)
        if selection < 0:
            return
        if selection == 0:
            chosen = dialog.select(addon.getLocalizedString(32025),
                                   [addon.getLocalizedString(item[0]) for item in filters])
            if chosen >= 0:
                _, order, kind = filters[chosen]
        elif selection == 1:
            addon.openSettings()
        elif selection == 2:
            _flush()
        elif selection == 3:
            continue
        else:
            row = rows[selection - len(actions)]
            dialog.textviewer(short_title(row), group_details(row), usemono=True)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'flush':
        _flush()
    else:
        browse()
