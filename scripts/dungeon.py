"""Refresh the calendar in the rendered three-run dungeon animation."""

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageSequence

from pacifist_vow import COLS, ROWS


TRACKS = Path(__file__).with_name('dungeon-tracks')
PALETTE = np.array([
    (36, 35, 44), (61, 55, 68), (100, 84, 99), (167, 120, 89), (237, 184, 117),
], dtype=np.uint16)


def calendar_layout(data):
    days = data['days']
    year = data.get('calendar_year', int(max(day['date'] for day in days)[:4]))
    first = date(year, 1, 1)
    last = date(year, 12, 31)
    offset = (first.weekday() + 1) % ROWS
    if (last - first).days + offset >= COLS * ROWS:
        # A leap year starting on Saturday fits the board with Monday-start weeks.
        offset = first.weekday()

    levels = [0] * (COLS * ROWS)
    total = active_days = 0
    for day in days:
        day_date = date.fromisoformat(day['date'])
        if day_date.year == year:
            levels[(day_date - first).days + offset] = day['level']
            total += day['count']
            active_days += day['count'] > 0

    month_starts = [date(year, month, 1) for month in range(1, 13)]
    months = [(((start - first).days + offset) // ROWS, start.strftime('%b'))
              for start in month_starts]
    return {'year': year, 'total': total, 'active_days': active_days, 'levels': levels, 'months': months}


def timed_frames(image):
    end = 0
    for frame in ImageSequence.Iterator(image):
        frame.load()
        duration = frame.info.get('duration', 0)
        if duration <= 0:
            raise ValueError('A dungeon track frame is missing its timing.')
        end += duration
        yield end, np.asarray(frame.convert('RGB'), dtype=np.uint16)


def paired_frames(base_image, map_image):
    """Match the two tracks even when WebP combines identical frames."""
    base_frames = timed_frames(base_image)
    map_frames = timed_frames(map_image)
    base = next(base_frames, None)
    tile_map = next(map_frames, None)
    start = 0
    while base is not None and tile_map is not None:
        end = min(base[0], tile_map[0])
        yield end - start, base[1], tile_map[1]
        start = end
        if base[0] == end:
            base = next(base_frames, None)
        if tile_map[0] == end:
            tile_map = next(map_frames, None)
    if base is not None or tile_map is not None:
        raise ValueError('The dungeon tracks have different durations.')


def labels(width, calendar):
    scale = width / 1165
    overlay = Image.new('RGBA', (width, round(72 * scale)))
    draw = ImageDraw.Draw(overlay)
    count_font = ImageFont.load_default(size=round(12 * scale))
    month_font = ImageFont.load_default(size=round(10 * scale))
    draw.text((1139 * scale, 31 * scale), f'{calendar["total"]:,} contributions in {calendar["year"]}',
              font=count_font, anchor='rs', fill='#f1c98e')
    for column, month in calendar['months']:
        draw.text(((28 + 21 * column) * scale, 68 * scale), month,
                  font=month_font, anchor='ls', fill='#c2b4c1')
    return overlay


def write_assets(destination, data):
    calendar = calendar_layout(data)
    # Map value zero marks pixels outside the contribution tiles.
    levels = [0] + calendar['levels']
    colors = PALETTE[levels] - PALETTE[0]
    frames, durations = [], []
    with (Image.open(TRACKS / 'dungeon-template.webp') as base_image,
          Image.open(TRACKS / 'dungeon-tile-map.webp') as map_image):
        if base_image.size != map_image.size:
            raise ValueError('The dungeon tracks have different dimensions.')
        overlay = labels(base_image.width, calendar)
        for duration, base, tile_map in paired_frames(base_image, map_image):
            ids = tile_map[..., 0] + (tile_map[..., 1] << 8)
            coverage = tile_map[..., 2, None]
            added = (colors[ids] * coverage + 127) // 255
            frame = Image.fromarray(np.minimum(base + added, 255).astype(np.uint8))
            frame.paste(overlay, (0, 0), overlay)
            frames.append(frame)
            durations.append(duration)
    if not frames:
        raise ValueError('The dungeon animation has no frames.')

    assets = destination / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=assets) as staging:
        animated = Path(staging) / 'dungeon.webp'
        still = Path(staging) / 'dungeon-still.png'
        frames[0].save(animated, save_all=True, append_images=frames[1:], duration=durations,
                       loop=0, quality=91, method=4, allow_mixed=True, minimize_size=True)
        frames[0].save(still, optimize=True)
        animated.replace(assets / animated.name)
        still.replace(assets / still.name)
    return calendar
