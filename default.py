# -*- coding: utf-8 -*-
"""Kodi UI for browsing local grouped problems and requesting manual sends."""

import os
import sys

import xbmcaddon
import xbmcgui
import xbmcvfs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'resources', 'lib'))
from browser import addon_sections, group_details, read_groups, short_title, source_of, source_sections

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
    scope, selected_addon = None, None
    filters = [(32020, 'count', None), (32021, 'last_seen', None),
               (32022, 'last_seen', 'error'), (32023, 'last_seen', 'traceback'),
               (32024, 'last_seen', 'crash')]
    while True:
        try:
            all_rows = read_groups(path, order, kind)
        except Exception as exc:
            dialog.ok('Bug Tracker', addon.getLocalizedString(32028) + ': ' + str(exc))
            return
        sections = source_sections(all_rows)
        if scope is None:
            labels = []
            for label_id, category in ((32032, 'addons'), (32033, 'system'), (32034, 'kodi')):
                subset = sections[category]
                labels.append('%s — %d / %d' % (addon.getLocalizedString(label_id),
                                               len(subset), sum(row['count'] for row in subset)))
            labels += [addon.getLocalizedString(i) for i in (32035, 32026, 32015)]
            selection = dialog.select('Bug Tracker', labels)
            if selection < 0:
                return
            if selection < 3:
                scope = ('addons', 'system', 'kodi')[selection]
            elif selection == 3:
                scope = 'all'
            elif selection == 4:
                addon.openSettings()
            else:
                _flush()
            continue
        if scope == 'addons' and selected_addon is None:
            sources = addon_sections(all_rows)
            labels = ['%s — %d / %d' % (name, len(subset), sum(row['count'] for row in subset))
                      for name, subset in sources]
            selection = dialog.select(addon.getLocalizedString(32032), labels)
            if selection < 0:
                scope = None
            else:
                selected_addon = sources[selection][0]
            continue
        if scope == 'all':
            rows = all_rows
        elif scope == 'addons':
            rows = [row for row in all_rows if source_of(row)[1] == selected_addon]
        else:
            rows = sections[scope]
        heading = addon.getLocalizedString(32031) % (len(rows), sum(row['count'] for row in rows))
        actions = [addon.getLocalizedString(i) for i in (32025, 32026, 32015, 32029)]
        labels = actions + ['[%d] %s' % (row['count'], short_title(row)) for row in rows]
        selection = dialog.select(heading, labels)
        if selection < 0:
            if scope == 'addons':
                selected_addon = None
            else:
                scope = None
            continue
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
