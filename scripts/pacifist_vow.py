"""Original, dependency-free Pacifist's Vow contribution animation generator."""
from __future__ import annotations

from collections import deque
from datetime import date
from copy import deepcopy
from html import escape
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

COLS, ROWS, TILE, PAD, TOP = 53, 7, 21, 28, 80
GRID_BOTTOM = TOP + ROWS * TILE
WIDTH, HEIGHT = COLS * TILE + PAD * 2, GRID_BOTTOM + 91
DT, STEPS, AURA_STEPS, SLEEP_STEPS = .2, 150, 40, 15
START_STEP = 13
AURA_RADIUS = 2.65

PALETTES = {
    'dark': dict(bg='#0d1117', text='#e9eee5', muted='#a0ac9e', line='#2c382d', player='#ffdc72',
                 lime='#c3f36b', wall='#667767', sleepy='#a7b4a2', eye='#101a10',
                 dots=['#19221b', '#29482a', '#477438', '#80ad48', '#b4df64']),
    'light': dict(bg='#f8faf5', text='#273125', muted='#5f6d59', line='#d6dfce', player='#ad7514',
                  lime='#567f29', wall='#91a588', sleepy='#9da68f', eye='#253020',
                  dots=['#e4ebdd', '#c6d9a8', '#a5c47f', '#7da252', '#527a2e']),
}

PLAYER_STYLES = {
    'classic': {'name': 'Classic', 'description': 'Smooth, solid, familiar.'},
    'pixel': {'name': 'Pixel', 'description': 'Chunky edges and a retro chomp.'},
    'outline': {'name': 'Outline', 'description': 'An open, lightweight silhouette.'},
}
CAST_ORDER = tuple(PLAYER_STYLES)


def cycle_visibility(index, duration):
    values = ['1' if slot == index else '0' for slot in range(len(CAST_ORDER))]
    values.append(values[0])
    keys = ';'.join(str(slot / len(CAST_ORDER)) for slot in range(len(CAST_ORDER) + 1))
    return (f'<animate attributeName="opacity" values="{";".join(values)}" keyTimes="{keys}" '
            f'dur="{duration * len(CAST_ORDER):g}s" repeatCount="indefinite" calcMode="discrete"/>')


def matching_cast(draw, skin, animated=True):
    if skin != 'cycle':
        return draw(skin)
    if not animated:
        return draw(CAST_ORDER[0])
    return ''.join(
        f'<g class="cast-variant" data-cast-variant="{name}" opacity="{int(index == 0)}">'
        + cycle_visibility(index, STEPS * DT) + draw(name) + '</g>'
        for index, name in enumerate(CAST_ORDER)
    )


def edge(a, b):
    return tuple(sorted((a, b)))


def make_walls():
    walls = set()
    # Sparse corridors preserve the contribution calendar's column/day layout.
    for y in (1, 5):
        for first, last in ((2, 7), (12, 17), (22, 27), (32, 37), (40, 44), (49, 51)):
            for x in range(first, last):
                walls.add(edge((x, y - 1), (x, y)))
    for x in (9, 19, 29, 39):
        for y in (0, 1, 5, 6):
            walls.add(edge((x - 1, y), (x, y)))
    for y in (3, 4):
        for first, last in ((4, 8), (14, 18), (24, 28), (34, 38)):
            for x in range(first, last):
                walls.add(edge((x, y - 1), (x, y)))
    return walls


WALLS = make_walls()


def neighbors(point):
    x, y = point
    return [(nx, ny) for nx, ny in ((x + 1, y), (x, y - 1), (x, y + 1), (x - 1, y))
            if 0 <= nx < COLS and 0 <= ny < ROWS and edge(point, (nx, ny)) not in WALLS]


def path_to(start, target, avoid=frozenset()):
    queue = deque([start])
    previous = {start: None}
    while queue:
        point = queue.popleft()
        if point == target:
            path = []
            while point is not None:
                path.append(point)
                point = previous[point]
            return path[::-1]
        for candidate in neighbors(point):
            if candidate not in previous and (candidate not in avoid or candidate == target):
                previous[candidate] = point
                queue.append(candidate)
    return []


def calendar_grid(data):
    cells = {}
    days = data['days']
    offset = (date.fromisoformat(days[0]['date']).weekday() + 1) % 7
    for index, day in enumerate(days):
        x, y = divmod(index + offset, 7)
        cells[x, y] = day
    return cells


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def heading_for_motion(start, end, fallback=0):
    delta = (end[0] - start[0], end[1] - start[1])
    return {(1, 0): 0, (-1, 0): 180, (0, -1): 270, (0, 1): 90}.get(delta, fallback)


def advance_ghost(ghost, step, pacman, aura, captures, respawns):
    if step < ghost['sleeping_until']:
        return
    if ghost['sleeping_until'] == step:
        ghost['pos'] = ghost['home']
        if ghost['pos'] == pacman:
            ghost['pos'] = next(point for point in neighbors(ghost['home']) if point != pacman)
        respawns.append({'step': step, 'name': ghost['name'], 'pos': list(ghost['pos']),
                         'inside_aura': aura and distance(ghost['pos'], pacman) <= AURA_RADIUS})
    elif step >= START_STEP:
        path = path_to(ghost['pos'], pacman)
        if len(path) > 1 and path[1] != pacman:
            ghost['pos'] = path[1]
    # Respawn is evaluated in the same tick, with no immunity window.
    if aura and distance(ghost['pos'], pacman) <= AURA_RADIUS:
        ghost['sleeping_until'] = step + SLEEP_STEPS
        captures.append({'step': step, 'name': ghost['name'], 'pos': list(ghost['pos'])})


def simulate(data):
    cells = calendar_grid(data)
    remaining = {position for position, day in cells.items() if day['count']}
    pacman = (43, 3)
    facing = 0
    pickup = (46, 3)
    pickup_step = None
    aura_until = -1
    ghosts = [
        dict(name='blinky', color='#fa7970', pos=(48, 2), home=(42, 1), sleeping_until=-1),
        dict(name='pinky', color='#efa7cc', pos=(48, 4), home=(40, 5), sleeping_until=-1),
        dict(name='inky', color='#83d8e9', pos=(50, 3), home=(39, 2), sleeping_until=-1),
        dict(name='clyde', color='#f4ba73', pos=(45, 0), home=(38, 4), sleeping_until=-1),
    ]
    frames = []
    events = []
    captures = []
    respawns = []

    for step in range(STEPS):
        if step >= START_STEP:
            avoid = {ghost['pos'] for ghost in ghosts}
            if pickup_step is None:
                target = pickup
            elif remaining - avoid:
                # Prefer close dots, with a slight preference for busier days.
                choices = sorted(remaining - avoid, key=lambda p: (abs(p[0] - pacman[0]) + abs(p[1] - pacman[1]) - cells[p]['level'] * .12, p))
                target = choices[0]
            else:
                target = (43, 3)
            path = path_to(pacman, target, avoid)
            if len(path) > 1:
                next_point = path[1]
                if next_point in avoid:
                    alternatives = [p for p in neighbors(pacman) if p not in avoid]
                    next_point = alternatives[0] if alternatives else pacman
                dx, dy = next_point[0] - pacman[0], next_point[1] - pacman[1]
                if dx or dy:
                    facing = heading_for_motion(pacman, next_point, facing)
                pacman = next_point

        if pacman in remaining:
            remaining.remove(pacman)
            events.append({'step': step, 'pos': list(pacman)})
        if pacman == pickup and pickup_step is None:
            pickup_step = step
            aura_until = step + AURA_STEPS

        aura = pickup_step is not None and step < aura_until
        for ghost in ghosts:
            advance_ghost(ghost, step, pacman, aura, captures, respawns)

        frames.append({
            'pacman': list(pacman), 'facing': facing, 'aura': aura,
            'powerup_visible': pickup_step is None, 'pickup': list(pickup),
            'ghosts': [dict(name=ghost['name'], color=ghost['color'], pos=list(ghost['pos']),
                            sleeping=step < ghost['sleeping_until'],
                            hidden=0 < ghost['sleeping_until'] - step <= 2) for ghost in ghosts],
        })

    # Each interpolated segment starts at frame i and travels toward frame i+1.
    for current, following in zip(frames, frames[1:]):
        current['facing'] = heading_for_motion(current['pacman'], following['pacman'], current['facing'])

    # These checks guard the actual behavior, independently of the renderer.
    assert pickup_step is not None
    assert all(not frame['aura'] for frame in frames[:pickup_step])
    assert not frames[pickup_step]['powerup_visible'] and frames[pickup_step]['aura']
    assert sum(frame['aura'] for frame in frames) == AURA_STEPS
    assert captures, 'At least one ghost must visibly enter the aura and fall asleep.'
    for before, after in zip(frames, frames[1:]):
        a, b = tuple(before['pacman']), tuple(after['pacman'])
        assert a == b or b in neighbors(a)
    assert all(frames[event['step']]['aura'] for event in captures)
    assert all(ghost['hidden'] or ghost['pos'] != frame['pacman'] for frame in frames for ghost in frame['ghosts'])
    assert all(ghost['sleeping'] or distance(ghost['pos'], frame['pacman']) > AURA_RADIUS
               for frame in frames if frame['aura'] for ghost in frame['ghosts'])
    for event in captures:
        for frame in frames[event['step']:min(event['step'] + SLEEP_STEPS, len(frames))]:
            assert next(ghost for ghost in frame['ghosts'] if ghost['name'] == event['name'])['sleeping']
        wake = event['step'] + SLEEP_STEPS
        if wake < len(frames) and not any(again['name'] == event['name'] and again['step'] == wake for again in captures):
            assert not next(ghost for ghost in frames[wake]['ghosts'] if ghost['name'] == event['name'])['sleeping']
    return dict(frames=frames, eaten=events, captures=captures, respawns=respawns, pickup_step=pickup_step,
                aura_end=pickup_step + AURA_STEPS, cells=cells)


def animate(attribute, values, length, discrete=True):
    # Run-length compression retains exact transitions, keeping the SVG small.
    transitions = [(0, str(values[0]))]
    for index, value in enumerate(values[1:], 1):
        if str(value) != transitions[-1][1]:
            transitions.append((index, str(value)))
    if transitions[-1][0] != length:
        transitions.append((length, transitions[-1][1]))
    if len({value for _, value in transitions}) == 1:
        return ''
    times = ';'.join(f'{index / length:.5f}' for index, _ in transitions)
    val = ';'.join(value for _, value in transitions)
    mode = 'discrete' if discrete else 'linear'
    if attribute == 'transform':
        val = ';'.join(value.removeprefix('rotate(').removesuffix(')') for _, value in transitions)
        return f'<animateTransform attributeName="transform" type="rotate" values="{val}" keyTimes="{times}" dur="{length * DT:g}s" calcMode="{mode}" repeatCount="indefinite"/>'
    return f'<animate attributeName="{attribute}" values="{val}" keyTimes="{times}" dur="{length * DT:g}s" calcMode="{mode}" repeatCount="indefinite"/>'


def movement(values, length):
    # Movement cannot use run-length compression: it must hold at still frames.
    times = ';'.join(f'{index / length:.5f}' for index in range(length + 1))
    positions = ';'.join(f'{PAD + p[0] * TILE + TILE / 2:g} {TOP + p[1] * TILE + TILE / 2:g}' for p in [*values, values[-1]])
    return f'<animateTransform attributeName="transform" type="translate" values="{positions}" keyTimes="{times}" dur="{length * DT:g}s" repeatCount="indefinite" calcMode="linear"/>'


def pixel_body(angle):
    pieces = []
    for x in range(-8, 8, 2):
        for y in range(-8, 8, 2):
            cx, cy = x + 1, y + 1
            if math.hypot(cx, cy) <= 8.7 and not (cx > 0 and abs(cy) < cx * math.tan(math.radians(angle))):
                pieces.append(f'M{x} {y}h2v2h-2Z')
    return ''.join(pieces)


def pacman_shape(c, skin='classic', animated=True):
    if skin == 'cycle':
        return matching_cast(lambda name: pacman_shape(c, name, animated), skin, animated)
    player = c['player']
    opened = 'M0 0L7.8 -4.5A9 9 0 1 0 7.8 4.5Z'
    closed = 'M0 0L9 -.5A9 9 0 1 0 9 .5Z'
    if skin == 'pixel':
        opening = pixel_body(38)
        closing = pixel_body(4)
        if not animated:
            return f'<path fill="{player}" d="{opening}" shape-rendering="crispEdges"/>'
        return (f'<path fill="{player}" d="{opening}" shape-rendering="crispEdges">'
                '<animate attributeName="opacity" values="1;0;1" keyTimes="0;.5;1" dur=".36s" calcMode="discrete" repeatCount="indefinite"/></path>'
                f'<path fill="{player}" d="{closing}" shape-rendering="crispEdges" opacity="0">'
                '<animate attributeName="opacity" values="0;1;0" keyTimes="0;.5;1" dur=".36s" calcMode="discrete" repeatCount="indefinite"/></path>')
    appearance = f'fill="none" stroke="{player}" stroke-width="2" stroke-linejoin="round"' if skin == 'outline' else f'fill="{player}"'
    motion = f'<animate attributeName="d" values="{opened};{closed};{opened}" dur=".36s" repeatCount="indefinite"/>' if animated else ''
    return f'<path {appearance} d="{opened}">{motion}</path>'


def ghost_shape(color, c, sleeping=False, skin='classic', animated=True):
    if skin == 'cycle':
        return matching_cast(lambda name: ghost_shape(color, c, sleeping, name, animated), skin, animated)
    if skin == 'pixel':
        body = '<path shape-rendering="crispEdges" d="M-4 -9H4V-7H6V-5H8V7H4V5H2V7H0V5H-2V7H-4V5H-6V7H-8V-5H-6V-7H-4Z"'
    else:
        body = '<path d="M-8 8V-1A8 8 0 0 1 8 -1V8L4 5L1 8L-2 5L-5 8L-8 5Z"'
    sleep_marks = (f'<text x="6" y="-12" fill="{c["lime"]}" font-size="9" class="mono" font-weight="700">z</text>'
                   f'<text x="11" y="-17" fill="{c["lime"]}" font-size="6" class="mono" opacity=".65">z</text>')
    if sleeping:
        appearance = f' fill="none" stroke="{c["sleepy"]}" stroke-width="1.6" opacity=".85"/>' if skin == 'outline' else f' fill="{c["sleepy"]}" opacity=".75"/>'
        if skin == 'pixel':
            eyes = f'<path d="M-6 -1h2v1h2v-1h1v2h-5ZM1 -1h2v1h2v-1h1v2H1Z" fill="{c["eye"]}" shape-rendering="crispEdges"/>'
        else:
            eye_color = c['sleepy'] if skin == 'outline' else c['eye']
            eyes = f'<path d="M-5 -1Q-3 1 -1 -1M2 -1Q4 1 6 -1" fill="none" stroke="{eye_color}" stroke-width="1.4" stroke-linecap="round"/>'
        return body + appearance + eyes + sleep_marks
    if skin == 'outline':
        return (body + f' fill="none" stroke="{color}" stroke-width="1.6" stroke-linejoin="round"/>'
                f'<rect x="-5.5" y="-4" width="4.6" height="6" rx="2" fill="{c["bg"]}" stroke="{color}" stroke-width=".8"/>'
                f'<rect x="1.5" y="-4" width="4.6" height="6" rx="2" fill="{c["bg"]}" stroke="{color}" stroke-width=".8"/>'
                f'<circle cx="-2" cy="-.5" r="1.1" fill="{color}"/><circle cx="5" cy="-.5" r="1.1" fill="{color}"/>')
    if skin == 'pixel':
        return (body + f' fill="{color}"/>'
                '<path d="M-6 -4h5v6h-5ZM1 -4h5v6H1Z" fill="#fcfdf7" shape-rendering="crispEdges"/>'
                '<path d="M-3 -1h2v2h-2ZM4 -1h2v2H4Z" fill="#243049" shape-rendering="crispEdges"/>')
    return (body + f' fill="{color}"/>'
            '<rect x="-5.5" y="-4" width="4.6" height="6" rx="2" fill="#fcfdf7"/>'
            '<rect x="1.5" y="-4" width="4.6" height="6" rx="2" fill="#fcfdf7"/>'
            '<circle cx="-2" cy="-.5" r="1.4" fill="#243049"/><circle cx="5" cy="-.5" r="1.4" fill="#243049"/>')


def render(data, sim, mode='dark', closeup=False, skin='cycle'):
    c = PALETTES[mode]
    frames = sim['frames']
    length = len(frames)
    viewbox = f'880 {TOP-30} 270 190' if closeup else f'0 0 {WIDTH} {HEIGHT}'
    width, height = (810, 570) if closeup else (WIDTH, HEIGHT)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="{viewbox}" role="img" aria-labelledby="title desc" data-player-style="{skin}" data-ghost-style="{skin}" data-round-duration="{length * DT:g}">',
             '<title id="title">DeonHolo\'s Pac-Man contribution graph</title>',
             f'<desc id="desc">{data["total"]:,} contributions and {data["active_days"]} active days in the public rolling-year calendar. Pac-Man must eat the lime power-up before his aura activates. Nearby ghosts fall asleep and later respawn. Respawning inside the active aura immediately puts a ghost back to sleep. The power-up effect expires after eight seconds. Matching Classic, Pixel and Outline casts cycle on successive replays. Updated {data["updated"]} UTC.</desc>',
             '<style>text{font-family:Segoe UI,Arial,sans-serif}.mono{font-family:Consolas,Menlo,monospace}.still,.reduced-camera{display:none}@media(prefers-reduced-motion:reduce){.motion,.moving-camera{display:none}.still,.reduced-camera{display:inline}}</style>',
             f'<rect x="0" y="0" width="{WIDTH}" height="{HEIGHT}" fill="{c["bg"]}" rx="12"/>']
    if not closeup:
        parts.extend([
            f'<text x="28" y="32" class="mono" font-size="10" letter-spacing="1.6" fill="{c["muted"]}">DEONHOLO / MODDED CONTRIBUTIONS</text>',
            f'<text x="{WIDTH-28}" y="33" text-anchor="end" class="mono" font-size="12" fill="{c["lime"]}">{data["total"]:,} contributions / last year</text>',
        ])
        if skin == 'cycle':
            parts.append('<g class="motion">' + matching_cast(
                lambda name: f'<text x="28" y="50" class="mono" font-size="9" letter-spacing="1" fill="{c["lime"]}">{PLAYER_STYLES[name]["name"].upper()} CAST / AUTO CYCLE</text>', skin) + '</g>')
            parts.append(f'<text class="still" x="28" y="50" font-size="9" fill="{c["lime"]}">CLASSIC CAST</text>')
        else:
            parts.append(f'<text x="28" y="50" class="mono" font-size="9" letter-spacing="1" fill="{c["lime"]}">{PLAYER_STYLES[skin]["name"].upper()} CAST</text>')

    def grid(animated):
        items = []
        for x in range(COLS):
            for y in range(ROWS):
                day = sim['cells'].get((x, y))
                level = day['level'] if day else 0
                color = c['dots'][level]
                values = [color] * length
                for event in sim['eaten']:
                    if event['pos'] == [x, y]:
                        values[event['step']:] = [c['dots'][0]] * max(0, length - event['step'])
                initial = values[0]
                title = f'{day["date"]}: {day["count"]} contributions' if day else 'Outside the current contribution calendar'
                items.append(f'<rect x="{PAD+x*TILE+1}" y="{TOP+y*TILE+1}" width="{TILE-3}" height="{TILE-3}" rx="4" fill="{initial}"><title>{escape(title)}</title>')
                if animated:
                    items.append(animate('fill', values, length))
                items.append('</rect>')
        return ''.join(items)

    # Real dates and intensity levels remain inspectable independently of motion.
    parts.append('<g class="motion">' + grid(True) + '</g>')
    parts.append('<g class="still">' + grid(False) + '</g>')
    last_month = None
    for (x, y), day in sorted(sim['cells'].items()):
        month = date.fromisoformat(day['date']).strftime('%b')
        if month != last_month and y == 0:
            parts.append(f'<text x="{PAD+x*TILE+2}" y="{TOP-10}" font-size="10" fill="{c["muted"]}" class="mono">{month}</text>')
            last_month = month
    for a, b in sorted(WALLS):
        x, y = a
        nx, ny = b
        if x == nx:
            x1, y1 = PAD + x * TILE + 1, TOP + max(y, ny) * TILE - 1
            x2, y2 = x1 + TILE - 2, y1
        else:
            x1, y1 = PAD + max(x, nx) * TILE - 1, TOP + y * TILE + 1
            x2, y2 = x1, y1 + TILE - 2
        parts.append(f'<path d="M{x1} {y1}L{x2} {y2}" stroke="{c["wall"]}" stroke-width="1.5" stroke-linecap="round" opacity=".65"/>')

    parts.append('<g class="motion">')
    pickup = frames[0]['pickup']
    px, py = PAD + pickup[0] * TILE + TILE / 2, TOP + pickup[1] * TILE + TILE / 2
    parts.append(f'<g id="power-pellet" transform="translate({px} {py})">')
    parts.append(animate('opacity', ['1' if frame['powerup_visible'] else '0' for frame in frames], length))
    parts.append(f'<circle r="8.5" fill="{c["bg"]}" stroke="{c["lime"]}" stroke-width="1"/>')
    parts.append(f'<circle r="5.4" fill="{c["lime"]}"/><circle r="2" fill="#f0ffca"/>')
    parts.append(f'<circle r="10.5" fill="none" stroke="{c["lime"]}" opacity=".45"><animate attributeName="r" values="9;12;9" dur="1.2s" repeatCount="indefinite"/><animate attributeName="opacity" values=".65;.1;.65" dur="1.2s" repeatCount="indefinite"/></circle></g>')

    # Aura and Pac-Man share one position track; it can only appear after pickup.
    start = frames[0]['pacman']
    parts.append(f'<g id="pacman" transform="translate({PAD+start[0]*TILE+TILE/2} {TOP+start[1]*TILE+TILE/2})">')
    parts.append(movement([frame['pacman'] for frame in frames], length))
    parts.append('<g id="pacifying-aura" opacity="0">' + animate('opacity', ['1' if frame['aura'] else '0' for frame in frames], length))
    parts.append(f'<circle r="{AURA_RADIUS*TILE:g}" fill="{c["lime"]}" fill-opacity=".075" stroke="{c["lime"]}" stroke-width="1.2" stroke-opacity=".65"/>')
    parts.append(f'<circle r="{AURA_RADIUS*TILE-7:g}" fill="none" stroke="{c["lime"]}" stroke-width=".65" stroke-dasharray="2 7" opacity=".45"><animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="12s" repeatCount="indefinite"/></circle>')
    parts.append(f'<circle r="17" fill="none" stroke="{c["lime"]}" opacity=".4"><animate attributeName="r" values="12;22;12" dur="1.6s" repeatCount="indefinite"/><animate attributeName="opacity" values=".45;.05;.45" dur="1.6s" repeatCount="indefinite"/></circle></g>')
    parts.append('<g id="pacman-heading" transform="rotate(0)">' + animate('transform', [f'rotate({frame["facing"]})' for frame in frames], length))
    parts.append(pacman_shape(c, skin) + '</g></g>')

    for index in range(4):
        positions = [frame['ghosts'][index]['pos'] for frame in frames]
        ghost = frames[0]['ghosts'][index]
        gx, gy = PAD + positions[0][0] * TILE + TILE / 2, TOP + positions[0][1] * TILE + TILE / 2
        parts.append(f'<g id="ghost-{ghost["name"]}" transform="translate({gx} {gy})">' + movement(positions, length))
        parts.append(animate('opacity', ['0' if frame['ghosts'][index]['hidden'] else '1' for frame in frames], length))
        parts.append('<g>' + animate('opacity', ['0' if frame['ghosts'][index]['sleeping'] else '1' for frame in frames], length))
        parts.append(ghost_shape(ghost['color'], c, skin=skin) + '</g>')
        parts.append(f'<g id="sleep-{ghost["name"]}" opacity="0">' + animate('opacity', ['1' if frame['ghosts'][index]['sleeping'] else '0' for frame in frames], length))
        parts.append(ghost_shape(ghost['color'], c, True, skin) + '</g></g>')
    parts.append('</g>')

    # Still fallback is a genuine post-pickup state, with sleepy ghosts visible.
    still = frames[min(sim['pickup_step'] + 2, length - 1)]
    sx, sy = PAD + still['pacman'][0] * TILE + TILE / 2, TOP + still['pacman'][1] * TILE + TILE / 2
    parts.append(f'<g class="still"><circle cx="{sx}" cy="{sy}" r="{AURA_RADIUS*TILE:g}" fill="{c["lime"]}" fill-opacity=".075" stroke="{c["lime"]}" stroke-opacity=".65"/>')
    still_skin = CAST_ORDER[0] if skin == 'cycle' else skin
    parts.append(f'<g transform="translate({sx} {sy}) rotate({still["facing"]})">' + pacman_shape(c, still_skin, False) + '</g>')
    for ghost in still['ghosts']:
        gx, gy = PAD + ghost['pos'][0] * TILE + TILE / 2, TOP + ghost['pos'][1] * TILE + TILE / 2
        parts.append(f'<g transform="translate({gx} {gy})">' + ghost_shape(ghost['color'], c, ghost['sleeping'], still_skin, False) + '</g>')
    parts.append('</g>')
    if not closeup:
        legend_y = GRID_BOTTOM + 53
        parts.append(f'<path d="M28 {GRID_BOTTOM+28}H{WIDTH-28}" stroke="{c["line"]}"/>')
        parts.append(f'<circle cx="34" cy="{legend_y}" r="5" fill="{c["lime"]}"/><circle cx="34" cy="{legend_y}" r="8" fill="none" stroke="{c["lime"]}" opacity=".5"/>')
        parts.append(f'<text x="50" y="{legend_y+4}" font-size="12" fill="{c["muted"]}">eat the power-up</text>')
        parts.append(f'<circle cx="237" cy="{legend_y}" r="8" fill="{c["lime"]}" fill-opacity=".09" stroke="{c["lime"]}" opacity=".8"/>')
        parts.append(f'<text x="254" y="{legend_y+4}" font-size="12" fill="{c["muted"]}">aura on · 8 seconds</text>')
        parts.append(f'<g class="motion" transform="translate(457 {legend_y})">' + ghost_shape('#efa7cc', c, True, skin) + '</g>')
        parts.append(f'<g class="still" transform="translate(457 {legend_y})">' + ghost_shape('#efa7cc', c, True, still_skin, False) + '</g>')
        parts.append(f'<text x="475" y="{legend_y+4}" font-size="12" fill="{c["muted"]}">ghosts nap, then respawn</text>')
        parts.append(f'<text x="{WIDTH-28}" y="{legend_y+4}" text-anchor="end" class="mono" font-size="10" fill="{c["muted"]}">{data["active_days"]} ACTIVE DAYS · {data["original_public_repos"]} ORIGINAL REPOS · {data["stars"]} STARS</text>')
    parts.append('</svg>')
    art = ''.join(parts)
    if closeup:
        # A preview-only camera follows the exact same animation and timeline.
        namespace = 'http://www.w3.org/2000/svg'
        ET.register_namespace('', namespace)
        svg = ET.fromstring(art)
        children = list(svg)
        scene = children[4:]
        camera = ET.Element(f'{{{namespace}}}g', {'class': 'moving-camera'})
        positions = [frame['pacman'] for frame in frames]
        offsets = [(1015 - (PAD + p[0] * TILE + TILE / 2), 65 - (p[1] * TILE + TILE / 2)) for p in positions]
        camera.set('transform', f'translate({offsets[0][0]:g} {offsets[0][1]:g})')
        ET.SubElement(camera, f'{{{namespace}}}animateTransform', {
            'attributeName': 'transform', 'type': 'translate',
            'values': ';'.join(f'{x:g} {y:g}' for x, y in [*offsets, offsets[-1]]),
            'keyTimes': ';'.join(f'{index / length:.5f}' for index in range(length + 1)),
            'dur': f'{length * DT:g}s', 'repeatCount': 'indefinite',
        })
        still_index = min(sim['pickup_step'] + 2, length - 1)
        fallback = ET.Element(f'{{{namespace}}}g', {'class': 'reduced-camera',
            'transform': f'translate({offsets[still_index][0]:g} {offsets[still_index][1]:g})'})
        for element in scene:
            static = deepcopy(element)
            def strip_motion(parent):
                for child in list(parent):
                    if child.tag.rsplit('}', 1)[-1].startswith('animate') or child.get('class') == 'motion':
                        parent.remove(child)
                    else:
                        strip_motion(child)
            strip_motion(static)
            if static.get('class') != 'motion':
                fallback.append(static)
            svg.remove(element)
            camera.append(element)
        svg.append(camera)
        svg.append(fallback)
        art = ET.tostring(svg, encoding='unicode')
    return art



def write_assets(destination, data, skin='cycle'):
    if skin not in (*CAST_ORDER, 'cycle'):
        raise ValueError(f'Unknown player style: {skin}')
    assets = Path(destination) / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    simulation = simulate(data)
    for mode in PALETTES:
        (assets / f'pacman-{mode}.svg').write_text(render(data, simulation, mode, skin=skin), encoding='utf-8')
