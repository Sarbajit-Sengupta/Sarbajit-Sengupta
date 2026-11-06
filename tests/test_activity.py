import datetime as dt
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('activity', ROOT / 'scripts' / 'generate_activity.py')
activity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(activity)


def calendar():
    end = dt.datetime.now(dt.timezone.utc).date()
    dates = [end - dt.timedelta(days=i) for i in range(364, -1, -1)]
    weeks = []
    for day in dates:
        if not weeks or day.weekday() == 6:
            weeks.append({'contributionDays': []})
        weeks[-1]['contributionDays'].append({
            'date': day.isoformat(), 'contributionCount': 0, 'contributionLevel': 'NONE'})
    return {'data': {'user': {'contributionsCollection': {'contributionCalendar': {'weeks': weeks}}}}}


class CalendarTests(unittest.TestCase):
    def test_valid_calendar(self):
        svg = activity.render(calendar())
        root = ET.fromstring(svg)
        self.assertEqual(len(root.findall('.//{http://www.w3.org/2000/svg}rect')) - 6, 365)

    def test_error_and_missing_day_are_rejected(self):
        with self.assertRaises(ValueError):
            activity.render({'errors': [{'message': 'failed'}]})
        payload = calendar()
        payload['data']['user']['contributionsCollection']['contributionCalendar']['weeks'][4]['contributionDays'].pop()
        with self.assertRaises(ValueError):
            activity.render(payload)

    def test_bad_level_and_stale_data_are_rejected(self):
        payload = calendar()
        payload['data']['user']['contributionsCollection']['contributionCalendar']['weeks'][0]['contributionDays'][0]['contributionLevel'] = 'INVALID'
        with self.assertRaises(ValueError):
            activity.render(payload)
        payload = calendar()
        days = payload['data']['user']['contributionsCollection']['contributionCalendar']['weeks']
        for week in days:
            for day in week['contributionDays']:
                day['date'] = (dt.date.fromisoformat(day['date']) - dt.timedelta(days=14)).isoformat()
        with self.assertRaises(ValueError):
            activity.render(payload)

    def test_failure_preserves_asset(self):
        target = ROOT / 'assets' / 'contribution-graph.svg'
        before = target.read_bytes()
        env = dict(os.environ)
        env.pop('GITHUB_TOKEN', None)
        result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'generate_activity.py')],
                                env=env, capture_output=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(target.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()

