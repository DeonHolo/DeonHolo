"""Generate GitHub profile art from public GitHub data; Python standard library only."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
from html import escape
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import re
import urllib.request


THEMES = {
    'modders-terminal': {
        'name': "Modder's Terminal", 'accent': '#c3f36b', 'light_accent': '#446821',
        'surface': '#10170f', 'light_surface': '#f3f7ee',
        'dots': ['#192319', '#304329', '#536f35', '#82aa47', '#c3f36b'],
        'light_dots': ['#e0e8d7', '#c6d7ae', '#9fbf7a', '#6e9748', '#446821'],
    },
    'field-notes': {
        'name': 'Field Notes', 'accent': '#e8ac7f', 'light_accent': '#a94b2e',
        'surface': '#201f1b', 'light_surface': '#f3eddf',
        'dots': ['#302c25', '#614431', '#98603d', '#c77f50', '#e8ac7f'],
        'light_dots': ['#e6decf', '#e2bd9e', '#d89469', '#bf6942', '#a94b2e'],
    },
    'holo-lab': {
        'name': 'Holo Lab', 'accent': '#86e0e4', 'light_accent': '#216c7c',
        'surface': '#0e1620', 'light_surface': '#edf3f6',
        'dots': ['#1a2833', '#294855', '#3b7180', '#58a7b4', '#86e0e4'],
        'light_dots': ['#d8e4eb', '#b3d4dc', '#82b6c3', '#4b91a3', '#216c7c'],
    },
}


class CalendarParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cells = {}
        self.tip_id = None
        self.tip_text = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == 'td' and 'data-date' in attrs:
            self.cells[attrs['id']] = {
                'date': attrs['data-date'], 'level': int(attrs['data-level']), 'count': None,
            }
        if tag == 'tool-tip':
            self.tip_id = attrs.get('for')
            self.tip_text = []

    def handle_data(self, content):
        if self.tip_id:
            self.tip_text.append(content)

    def handle_endtag(self, tag):
        if tag == 'tool-tip' and self.tip_id:
            text = ''.join(self.tip_text).strip()
            if self.tip_id in self.cells:
                match = re.match(r'([\d,]+) contributions? on ', text)
                if match:
                    self.cells[self.tip_id]['count'] = int(match.group(1).replace(',', ''))
                elif text.startswith('No contributions on '):
                    self.cells[self.tip_id]['count'] = 0
            self.tip_id = None
            self.tip_text = []


def parse_calendar(html):
    parser = CalendarParser()
    parser.feed(html)
    days = sorted(parser.cells.values(), key=lambda day: day['date'])
    if len(days) < 350 or any(day['count'] is None for day in days):
        raise ValueError('Incomplete public contribution calendar; keeping existing graphics.')
    match = re.search(r'([\d,]+)\s+contributions?\s+in the last year', html)
    total = sum(day['count'] for day in days)
    if match and total != int(match.group(1).replace(',', '')):
        raise ValueError('Calendar total does not match its cells; keeping existing graphics.')
    return days


def request(url, is_json=False):
    headers = {'User-Agent': 'DeonHolo-profile-readme'}
    if is_json:
        headers['Accept'] = 'application/vnd.github+json'
        token = os.environ.get('GITHUB_TOKEN')
        if token:
            headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=35) as response:
        text = response.read().decode('utf-8')
    return json.loads(text) if is_json else text


def fetch_snapshot(user):
    repos = []
    page = 1
    while True:
        batch = request(f'https://api.github.com/users/{user}/repos?type=owner&per_page=100&page={page}', True)
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    days = parse_calendar(request(f'https://github.com/users/{user}/contributions'))
    return make_snapshot(user, repos, days)


def make_snapshot(user, repos, days):
    # The profile repository and forks do not represent original project work.
    originals = [repo for repo in repos if not repo['fork'] and not repo.get('private')
                 and repo['name'].lower() != user.lower()]
    counts = Counter(repo['language'] for repo in originals if repo['language'])
    return {
        'user': user, 'updated': datetime.now(timezone.utc).date().isoformat(),
        'source': f'https://github.com/{user}', 'days': days,
        'total': sum(day['count'] for day in days),
        'active_days': sum(day['count'] > 0 for day in days),
        'original_public_repos': len(originals),
        'stars': sum(repo['stargazers_count'] for repo in originals),
        'languages': dict(counts.most_common()),
    }


def palette(theme, mode):
    light = mode == 'light'
    return {
        'bg': theme['light_surface'] if light else theme['surface'],
        'text': '#242b26' if light else '#eff3ec',
        'muted': '#586352' if light else '#a1ab9d',
        'line': '#d2dccb' if light else '#30402d',
        'accent': theme['light_accent'] if light else theme['accent'],
        'dots': theme['light_dots'] if light else theme['dots'],
    }


def svg_start(width, height, title, description, colors):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
            f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>',
            '<style>text{font-family:Segoe UI,Arial,sans-serif}.mono{font-family:Consolas,Menlo,monospace}.serif{font-family:Georgia,serif}@media(prefers-reduced-motion:reduce){.scan{display:none}}</style>',
            f'<rect width="{width}" height="{height}" rx="14" fill="{colors["bg"]}"/>']


def txt(parts, x, y, text, size, fill, extra=''):
    parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" {extra}>{escape(str(text))}</text>')


def banner(theme_name, mode):
    theme = THEMES[theme_name]
    c = palette(theme, mode)
    parts = svg_start(1000, 310, 'deon holo — i like modding stuff',
                      'Agentic coding, Spec-Driven Development, game and software mods, and useful little tools.', c)
    if theme_name == 'modders-terminal':
        txt(parts, 38, 36, 'dh_', 20, c['accent'], 'class="mono" font-weight="700"')
        txt(parts, 94, 35, 'DEONHOLO / PERSONAL WORKSPACE', 12, c['muted'], 'class="mono" letter-spacing="1.3"')
        parts.append(f'<path d="M38 54H962" stroke="{c["line"]}"/>')
        txt(parts, 38, 128, 'i like', 67, c['text'], 'font-weight="700" letter-spacing="-3"')
        txt(parts, 38, 205, 'modding stuff.', 70, c['accent'], 'font-weight="700" letter-spacing="-3"')
        txt(parts, 40, 265, 'games. software. the way things work.', 17, c['muted'])
        parts.append(f'<rect x="663" y="83" width="298" height="167" rx="9" fill="none" stroke="{c["line"]}"/>')
        txt(parts, 682, 111, '~/deon', 12, c['muted'], 'class="mono"')
        parts.append(f'<path d="M663 126H961" stroke="{c["line"]}"/>')
        txt(parts, 682, 160, '> edit the rules', 18, c['accent'], 'class="mono"')
        txt(parts, 682, 189, 'spec / build / test / tweak', 13, c['text'], 'class="mono"')
        txt(parts, 682, 221, 'there is probably a mod for that_', 11, c['muted'], 'class="mono"')
        txt(parts, 961, 287, 'ALWAYS TINKERING', 11, c['muted'], 'class="mono" text-anchor="end" letter-spacing="1"')
    elif theme_name == 'field-notes':
        txt(parts, 40, 35, 'DEON HOLO', 13, c['text'], 'font-weight="600" letter-spacing="2.5"')
        txt(parts, 960, 35, 'FIELD NOTES / 001', 11, c['muted'], 'class="mono" text-anchor="end"')
        parts.append(f'<path d="M40 53H960" stroke="{c["line"]}"/>')
        txt(parts, 36, 130, 'what if it', 71, c['text'], 'class="serif" letter-spacing="-2.5"')
        txt(parts, 36, 207, 'worked my way?', 71, c['text'], 'class="serif" letter-spacing="-2.5" font-style="italic"')
        txt(parts, 40, 270, 'games, software, and a habit of changing things.', 16, c['muted'])
        parts.append(f'<circle cx="818" cy="155" r="68" fill="none" stroke="{c["accent"]}" stroke-width="1.5"/>')
        parts.append(f'<ellipse cx="818" cy="155" rx="92" ry="25" transform="rotate(-28 818 155)" fill="none" stroke="{c["accent"]}"/>')
        txt(parts, 818, 168, 'dh.', 45, c['accent'], 'class="serif" font-style="italic" text-anchor="middle"')
        txt(parts, 708, 78, 'an idea', 12, c['muted'], 'class="mono"')
        txt(parts, 919, 181, 'a mod', 12, c['muted'], 'class="mono"')
        txt(parts, 768, 257, 'another idea', 12, c['muted'], 'class="mono"')
        parts.append(f'<path d="M766 87Q835 57 881 97M901 197Q897 239 856 247M734 207Q698 152 734 107" fill="none" stroke="{c["accent"]}" stroke-dasharray="3 5"/>')
        parts.append(f'<path d="M40 290H200" stroke="{c["accent"]}" stroke-width="3"/>')
    else:
        txt(parts, 40, 38, 'DEON // HOLO', 12, c['muted'], 'class="mono" letter-spacing="2"')
        txt(parts, 38, 137, 'deon.holo', 83, c['text'], 'font-weight="650" letter-spacing="-5"')
        txt(parts, 42, 193, 'small changes.', 28, c['text'], 'letter-spacing="-0.5"')
        txt(parts, 42, 229, 'new possibilities.', 28, c['accent'], 'letter-spacing="-0.5"')
        txt(parts, 43, 280, 'AGENTIC CODING / MODS / EXPERIMENTS', 11, c['muted'], 'class="mono" letter-spacing="1"')
        for index in range(-4, 5):
            radius = 94 * math.sqrt(1 - (index / 5) ** 2)
            parts.append(f'<ellipse cx="805" cy="{155 + index * 20}" rx="{radius:.2f}" ry="{radius * .23:.2f}" fill="none" stroke="{c["accent"]}" opacity="{.28 + .09 * (4 - abs(index)):.2f}"/>')
        for angle in (-65, -30, 0, 30, 65):
            parts.append(f'<ellipse cx="805" cy="155" rx="35" ry="100" transform="rotate({angle} 805 155)" fill="none" stroke="{c["accent"]}" opacity=".46"/>')
        parts.append(f'<path d="M657 155H953M805 12V296" stroke="{c["line"]}" stroke-dasharray="3 6"/>')
        parts.append(f'<circle cx="895" cy="112" r="5" fill="{c["accent"]}"/><circle cx="728" cy="211" r="3" fill="{c["accent"]}"/>')
        txt(parts, 958, 283, 'KEEP EXPERIMENTING ↗', 11, c['muted'], 'class="mono" text-anchor="end"')
    return ''.join(parts) + '</svg>\n'


def summary(theme_name, mode, data):
    c = palette(THEMES[theme_name], mode)
    description = (f'{data["total"]:,} contributions and {data["active_days"]} active days in the public rolling-year calendar. '
                   f'{data["original_public_repos"]} original public repositories with {data["stars"]} total stars; forks and this profile repository excluded. '
                   f'Primary languages by repository count: {data["languages"]}. Updated {data["updated"]} UTC.')
    parts = svg_start(1000, 196, 'github / a few numbers', description, c)
    txt(parts, 28, 31, 'GITHUB / A FEW NUMBERS', 12, c['muted'], 'class="mono" letter-spacing="1.5"')
    metrics = [
        (f'{data["total"]:,}', 'contributions / last year'),
        (str(data['active_days']), 'active days / last year'),
        (str(data['original_public_repos']), 'original public repos'),
        (str(data['stars']), 'stars / original repos'),
    ]
    for index, (value, label) in enumerate(metrics):
        x = 28 + index * 247
        txt(parts, x, 88, value, 41, c['accent'] if index == 0 else c['text'], 'font-weight="650" letter-spacing="-1"')
        txt(parts, x, 114, label, 13, c['muted'])
        if index:
            parts.append(f'<path d="M{x - 20} 53V116" stroke="{c["line"]}"/>')
    parts.append(f'<path d="M28 137H972" stroke="{c["line"]}"/>')
    languages = '  /  '.join(f'{name} {count}' for name, count in data['languages'].items())
    txt(parts, 28, 161, languages, 12, c['text'], 'class="mono"')
    txt(parts, 28, 183, 'primary language by repo count · forks and this profile excluded', 11, c['muted'])
    txt(parts, 971, 183, data['updated'] + ' UTC', 10, c['muted'], 'class="mono" text-anchor="end"')
    return ''.join(parts) + '</svg>\n'


def shade(color, factor):
    return '#' + ''.join(f'{round(int(color[i:i+2], 16) * factor):02x}' for i in (1, 3, 5))


def skyline(theme_name, mode, data):
    c = palette(THEMES[theme_name], mode)
    days = data['days']
    first, last = date.fromisoformat(days[0]['date']), date.fromisoformat(days[-1]['date'])
    start_offset = (first.weekday() + 1) % 7
    description = (f'Public contribution calendar from {first.isoformat()} to {last.isoformat()}: '
                   f'{data["total"]:,} contributions. Each block is one day. Height is logarithmic in that day\'s contribution count; color follows GitHub\'s intensity levels. Updated {data["updated"]} UTC.')
    parts = svg_start(1000, 302, 'a year of tinkering', description, c)
    txt(parts, 28, 34, 'a year of tinkering', 22, c['text'], 'font-weight="600" letter-spacing="-.5"')
    txt(parts, 28, 58, 'one block, one day. every little change adds up.', 13, c['muted'])
    txt(parts, 970, 34, f'{data["total"]:,} contributions', 13, c['accent'], 'class="mono" text-anchor="end"')
    txt(parts, 970, 57, f'{first:%b %Y} — {last:%b %Y}', 11, c['muted'], 'class="mono" text-anchor="end"')
    blocks = []
    for index, day in enumerate(days):
        week, weekday = divmod(index + start_offset, 7)
        x = 44 + week * 16.4 + weekday * 6.4
        y = 153 + weekday * 11 + week * .68
        height = 2 if not day['count'] else 4 + math.log2(day['count'] + 1) * 10
        color = c['dots'][day['level']]
        front = f'{x:.2f},{y-height:.2f} {x+7:.2f},{y-height+3.5:.2f} {x+7:.2f},{y+3.5:.2f} {x:.2f},{y:.2f}'
        side = f'{x+7:.2f},{y-height+3.5:.2f} {x+14:.2f},{y-height:.2f} {x+14:.2f},{y:.2f} {x+7:.2f},{y+3.5:.2f}'
        top = f'{x:.2f},{y-height:.2f} {x+7:.2f},{y-height-3.5:.2f} {x+14:.2f},{y-height:.2f} {x+7:.2f},{y-height+3.5:.2f}'
        block = (f'<g><title>{day["date"]}: {day["count"]} contributions</title>'
                 f'<polygon points="{front}" fill="{shade(color, .66)}"/>'
                 f'<polygon points="{side}" fill="{shade(color, .82)}"/>'
                 f'<polygon points="{top}" fill="{color}"/></g>')
        blocks.append((y, block))
    parts.extend(block for _, block in sorted(blocks, key=lambda item: item[0]))
    parts.append(f'<path d="M28 267H972" stroke="{c["line"]}"/>')
    parts.append(f'<circle class="scan" r="2" fill="{c["accent"]}" aria-hidden="true"><animateMotion path="M28 267H972" dur="18s" repeatCount="indefinite"/></circle>')
    txt(parts, 28, 289, 'PUBLIC ACTIVITY · HEIGHT = DAILY CONTRIBUTIONS (LOG SCALE)', 9, c['muted'], 'class="mono" letter-spacing=".5"')
    txt(parts, 970, 289, 'UPDATED ' + data['updated'] + ' UTC', 9, c['muted'], 'class="mono" text-anchor="end"')
    return ''.join(parts) + '</svg>\n'


def render(destination, theme, data):
    assets = Path(destination) / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    for mode in ('dark', 'light'):
        for name, function in (('banner', banner), ('stats', summary), ('activity', skyline)):
            art = function(theme, mode) if name == 'banner' else function(theme, mode, data)
            (assets / f'{name}-{mode}.svg').write_text(art, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=Path, help='Use saved public data instead of making network requests.')
    parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--theme', choices=THEMES, default=None)
    arguments = parser.parse_args()
    config = json.loads((arguments.out / 'profile.json').read_text(encoding='utf-8'))
    theme = arguments.theme or config['theme']
    data = json.loads(arguments.snapshot.read_text(encoding='utf-8')) if arguments.snapshot else fetch_snapshot(config['user'])
    render(arguments.out, theme, data)
    print(f'Generated {THEMES[theme]["name"]}: {data["total"]:,} contributions, '
          f'{data["active_days"]} active days, {data["original_public_repos"]} original public repos.')


if __name__ == '__main__':
    main()
