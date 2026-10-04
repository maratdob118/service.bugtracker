# -*- coding: utf-8 -*-
"""Settings action entry: 'send pending reports now'."""

import sys

import xbmcgui


def _flush():
    xbmcgui.Window(10000).setProperty('service.bugtracker.flush', 'true')
    xbmcgui.Dialog().notification('Bug Tracker', 'flush requested', time=2000)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'flush':
        _flush()
