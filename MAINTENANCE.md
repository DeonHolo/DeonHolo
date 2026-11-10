# keeping the profile fresh

The profile's SVG animation uses GitHub's public contribution calendar and public repository counts. Both the light and dark versions are stored in this repository.

The workflow refreshes both images daily at 01:23 UTC (09:23 in Singapore and the Philippines) and when `profile.json` or `scripts/profile.py` changes on `main`. To refresh after changing only the animation renderer, use **Actions → Refresh profile graphics → Run workflow**. GitHub can delay scheduled jobs or disable them after 60 days of repository inactivity.

No personal access token or new repository secret is needed. The workflow uses the temporary token GitHub provides for this repository.

To regenerate locally, run `python scripts/profile.py`. Python 3.10+ is enough; no packages are required. An optional `GITHUB_TOKEN` raises the API rate limit. It is sent only to api.github.com. The public contribution page is always fetched without authentication.

To regenerate the earlier banner, stats card and skyline, run `python scripts/profile.py --theme modders-terminal`. The other banner themes are `field-notes` and `holo-lab`.

Repository and star counts cover original public repositories other than this profile repository. The rolling year calendar can include anonymized private contribution totals when GitHub's **Private contributions** setting is enabled.

The contribution game is generated as a self-contained SVG. Its dates and contribution intensity levels come from the public calendar. Pac-Man eats a separate lime power-up before gaining an eight-second aura. Ghosts within range fall asleep for three seconds, fade briefly, and respawn. Respawned ghosts are checked immediately and fall asleep again if they return inside the active aura. Pac-Man faces the direction of the segment currently being travelled. Those character states are decorative and do not change the underlying calendar totals. Reduced-motion preferences show a still post-pickup scene.

With `player_style: cycle`, matching Classic, Pixel and Outline casts rotate at each 30-second replay. Pac-Man and the awake/sleeping ghosts switch together. The 90-second appearance cycle is built into the SVG, so it works inside a GitHub README without page JavaScript. Reduced motion uses a still Classic cast. Set `player_style` to `classic`, `pixel`, or `outline` to pin one matching cast instead.

The Python simulation checks that the aura cannot activate before pickup, expires on time, sleeping ghosts wake, and characters stay within valid paths. The layout and ghost drawings are original vector artwork. The arcade contribution idea was inspired by [abozanona/pacman-contribution-graph](https://github.com/abozanona/pacman-contribution-graph); the non-lethal power-up is inspired by [DeonHolo/Pacifists-Vow](https://github.com/DeonHolo/Pacifists-Vow).

If GitHub data cannot be fetched or validated, generation stops before replacing existing graphics.
