#!/usr/bin/env python3
"""Render the public GitHub contribution calendar; leave the old asset on failure."""
import datetime as dt
import json
import os
from pathlib import Path
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'assets' / 'contribution-graph.svg'
QUERY = '''query($login:String!) { user(login:$login) { contributionsCollection {
  contributionCalendar { weeks { contributionDays { date contributionCount contributionLevel } } }
} } }'''
COLORS = {'NONE': '#1b303a', 'FIRST_QUARTILE': '#285c5c',
          'SECOND_QUARTILE': '#3e8580', 'THIRD_QUARTILE': '#64aaa2',
          'FOURTH_QUARTILE': '#a7ddd3'}


def render(payload):
    if payload.get('errors'):
        raise ValueError('GitHub GraphQL returned errors')
    weeks = payload['data']['user']['contributionsCollection']['contributionCalendar']['weeks']
    if not isinstance(weeks, list) or not 52 <= len(weeks) <= 54:
        raise ValueError('Unexpected calendar length')
    cells, dates = [], []
    for col, week in enumerate(weeks):
        days = week['contributionDays']
        if not isinstance(days, list) or not 1 <= len(days) <= 7:
            raise ValueError('Unexpected week')
        for day in days:
            date = dt.date.fromisoformat(day['date'])
            level, count = day['contributionLevel'], day['contributionCount']
            if level not in COLORS or not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ValueError('Unexpected contribution data')
            dates.append(date)
            row = (date.weekday() + 1) % 7
            cells.append(f'<rect x="{48 + col * 20}" y="{83 + row * 20}" width="14" height="14" rx="2" fill="{COLORS[level]}"><title>{date.isoformat()}: {count} contributions</title></rect>')
    # GitHub pads the start of its trailing-year calendar back to Sunday.
    if not 365 <= len(dates) <= 371 or dates != sorted(set(dates)) or (dates[-1] - dates[0]).days + 1 != len(dates):
        raise ValueError(f'Calendar dates are incomplete or unordered: {len(dates)} days, {dates[0]} to {dates[-1]}, {len(set(dates))} unique')
    for i, week in enumerate(weeks):
        week_dates = [dt.date.fromisoformat(day['date']) for day in week['contributionDays']]
        if any((date.weekday() + 1) % 7 != ((week_dates[0].weekday() + 1) % 7) + j for j, date in enumerate(week_dates)):
            raise ValueError('Days cross a week boundary')
        if i and week_dates[0].weekday() != 6:
            raise ValueError('A noninitial week does not start on Sunday')
        if i < len(weeks) - 1 and week_dates[-1].weekday() != 5:
            raise ValueError('A nonfinal week does not end on Saturday')
    if abs((dt.datetime.now(dt.timezone.utc).date() - dates[-1]).days) > 2:
        raise ValueError('Calendar is stale or future-dated')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="300" viewBox="0 0 1200 300" role="img" aria-labelledby="title desc">
<title id="title">GitHub contribution calendar</title><desc id="desc">Daily contribution levels from {dates[0]} to {dates[-1]}. See the linked GitHub profile for the detailed accessible record.</desc>
<rect width="1200" height="300" fill="#0c131b"/><path d="M48 54H1152M48 250H1152" stroke="#35505c"/>
<text x="48" y="37" fill="#82c9c4" font-family="monospace" font-size="13" letter-spacing="2">SOURCE / ACTIVITY</text>
<text x="1152" y="37" text-anchor="end" fill="#9aafb7" font-family="monospace" font-size="12">{dates[0]} — {dates[-1]}</text>
{''.join(cells)}
<text x="48" y="279" fill="#9aafb7" font-family="monospace" font-size="12">GITHUB CONTRIBUTION LEVELS / LESS</text>
{''.join(f'<rect x="{360+i*20}" y="267" width="14" height="14" rx="2" fill="{color}"/>' for i, color in enumerate(COLORS.values()))}
<text x="472" y="279" fill="#9aafb7" font-family="monospace" font-size="12">MORE</text></svg>\n'''


def main():
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        raise RuntimeError('GITHUB_TOKEN is required')
    body = json.dumps({'query': QUERY, 'variables': {'login': 'Sarbajit-Sengupta'}}).encode()
    request = urllib.request.Request('https://api.github.com/graphql', data=body,
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'User-Agent': 'source-profile'})
    with urllib.request.urlopen(request, timeout=30) as response:
        svg = render(json.load(response))
    # Replace only after a complete, validated response and write.
    name = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=TARGET.parent, delete=False) as f:
            name = f.name
            f.write(svg)
        os.replace(name, TARGET)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Activity refresh failed; previous asset preserved: {exc}', file=sys.stderr)
        sys.exit(1)

