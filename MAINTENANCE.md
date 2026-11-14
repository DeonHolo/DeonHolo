# keeping the profile fresh

The profile's Torchlit dungeon uses GitHub's default rolling contribution calendar for the last year. The 60 FPS WebP loops through Dine & Dash, All You Can Eat, and Trapdoor with the janitor ending. The README also offers a still image for reduced motion. Google WebP 1.6.0 encodes the animation with mixed compression, sharp color conversion, quality 85, and effort 6.

The workflow is scheduled to refresh the dungeon's tile colors, month labels, and contribution total daily at 01:23 UTC (09:23 in Singapore and the Philippines). GitHub may start scheduled runs later. Changes to its configuration, renderer, or animation tracks on `main` also trigger a refresh. To refresh on demand, use **Actions → Refresh profile graphics → Run workflow**.

No personal access token or new repository secret is needed. The workflow uses the temporary token GitHub provides for this repository.

To regenerate locally, use Python 3.11 or newer and install the renderer dependencies. Install the [Google WebP 1.6.0 tools](https://developers.google.com/speed/webp/download), then put `img2webp` on PATH or set `DUNGEON_WEBP_ENCODER` to its absolute executable path.

```sh
python -m pip install -r scripts/dungeon-requirements.txt
python scripts/profile.py
```

An optional `GITHUB_TOKEN` raises the API rate limit for api.github.com. The renderer fetches the public contribution calendar without authentication.

To regenerate the earlier banner, stats card and skyline, run `python scripts/profile.py --theme modders-terminal`. The other banner themes are `field-notes` and `holo-lab`.

Repository and star counts cover original public repositories other than this profile repository. The calendar can include anonymized private contribution totals when GitHub's **Private contributions** setting is enabled.

The renderer reads two files in `scripts/dungeon-tracks/`. The first contains the composited dungeon scenes. The second identifies visible pixels by calendar cell throughout the loop, including the moving tiles. Replacing the scene requires exporting both tracks together from the dungeon preview.

If GitHub data cannot be fetched or validated, generation stops before replacing existing graphics.
