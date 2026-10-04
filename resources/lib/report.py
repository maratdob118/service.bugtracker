# -*- coding: utf-8 -*-
"""File grouped problems as GitHub issues, with server-side dedup."""

import datetime
import json

try:
    from urllib.request import Request, build_opener, ProxyHandler
    from urllib.error import HTTPError
except ImportError:  # Python 2
    from urllib2 import Request, build_opener, ProxyHandler, HTTPError

API = 'https://api.github.com'
PROXY = 'http://127.0.0.1:1080'


def _openers(token):
    headers = {'Authorization': 'token %s' % token,
               'Accept': 'application/vnd.github+json',
               'User-Agent': 'kodi-bugtracker'}
    direct = build_opener(ProxyHandler({}))
    via_proxy = build_opener(ProxyHandler({'http': PROXY, 'https': PROXY}))
    return headers, (via_proxy, direct)


def _request(method, path, token, payload=None):
    headers, openers = _openers(token)
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    last_error = None
    for opener in openers:
        try:
            request = Request(API + path, data=data, headers=headers, method=method)
            with opener.open(request, timeout=20) as response:
                body = response.read().decode('utf-8', 'replace')
                return response.status, json.loads(body or '{}')
        except HTTPError as exc:
            try:
                detail = exc.read().decode('utf-8', 'replace')[:300]
            except Exception:
                detail = ''
            if exc.code in (401, 403, 404, 422):
                raise RuntimeError('GitHub API %s: %s' % (exc.code, detail))
            last_error = exc
        except Exception as exc:
            last_error = exc
    raise RuntimeError('GitHub unreachable: %s' % last_error)


def find_issue(repo, sig, token):
    """Return open issue number already filed for SIG, or None."""
    status, data = _request(
        'GET', '/search/issues?q=%s+in:body+state:open+repo:%s' % ('sig:' + sig, repo.replace('/', '%2F')),
        token)
    items = data.get('items') or []
    return items[0].get('number') if items else None


def file_issue(repo, title, body, token):
    _status, data = _request(
        'POST', '/repos/%s/issues' % repo,
        token, {'title': title[:220], 'body': body})
    return data.get('number')


def comment_issue(repo, number, body, token):
    _request('POST', '/repos/%s/issues/%s/comments' % (repo, number), token, {'body': body})


def render_body(box, sig, kind, sample, count, first_seen, last_seen):
    stamp = lambda ts: datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
    lines = sample.splitlines()[:60]
    return (
        'Automated report from Kodi box `%s`.\n\n'
        '- Signature: `sig:%s`\n'
        '- Kind: %s\n'
        '- Occurrences: %d (first %s, last %s)\n\n'
        '<details><summary>Sample</summary>\n\n```\n%s\n```\n</details>\n'
        % (box, sig, kind, count, stamp(first_seen), stamp(last_seen), '\n'.join(lines)))
