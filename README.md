# Bug Tracker for Kodi

Collects Kodi error messages, Python tracebacks and crash reports into a local
SQLite database. Repeating signatures share a group and an occurrence counter.

## Open reports on the TV

Open **Add-ons → Program add-ons → Bug Tracker**. Choose **Add-ons**, **System**,
**Kodi**, or **All groups**. Add-ons opens a list of source add-on IDs, then
their grouped reports. Source attribution is inferred from the log text and
traceback file paths, so the existing database can be browsed without migration.
Shared requests/urllib modules are attributed to their caller when possible.
The list shows occurrence
counts and group titles. Select a group to read its signature, type, collection
timestamps, sample and GitHub issue number, if one has been assigned.

Use **Sort / filter** to show the most frequent or latest groups, errors,
Python tracebacks or crash reports. **Refresh groups** reloads the database.
The browser only reads the database; the background service keeps collecting.

**Settings** and **Send pending reports now** are available from the same menu.
GitHub sending is off by default and requires a token configured on the device.
Local collection and browsing do not require GitHub credentials. New-group
notifications are off by default to avoid interrupting playback.

Reports are stored in
`special://profile/addon_data/service.bugtracker/reports.db`.
Counts represent captured log messages, not independent failures. Collection
timestamps indicate when the tracker recorded a message, not necessarily when
the original failure happened. Version 0.2.0 retains the initial collector;
crash recovery after a restart and more robust grouping remain follow-up work.
