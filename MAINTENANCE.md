# keeping the profile fresh

The profile uses local SVGs instead of third-party stat-card servers. The contribution skyline and summary are generated from GitHub's public contribution calendar and public repository API.

The workflow refreshes them daily at 01:23 UTC (09:23 in Singapore and the Philippines), on relevant source changes, or through **Actions → Refresh profile graphics → Run workflow**. Scheduled jobs can be delayed by GitHub. Public repositories with no activity for 60 days can have scheduled workflows disabled; re-enable the workflow in Actions if that happens.

No personal access token or new repository secret is needed. The workflow uses the temporary token GitHub provides for this repository.

To regenerate locally, run `python scripts/profile.py`. Python 3.10+ is enough; no packages are required. An optional `GITHUB_TOKEN` raises the API rate limit. It is sent only to api.github.com. The public contribution page is always fetched without authentication.

Change `theme` in `profile.json` to `modders-terminal`, `field-notes`, or `holo-lab` and run the workflow to change all the artwork. Each theme has separate light and dark assets, selected automatically by GitHub.

Repository and star counts include original public repositories and exclude forks and this profile repository. Primary language counts use each repository's main language, rather than lines of code or a proficiency score. The contribution calendar is the public rolling-year graph, which can include anonymized private contribution totals if the user has enabled them on GitHub. No private repository names are requested or displayed.

Skyline blocks use GitHub's intensity levels and a logarithmic height scale so busy days do not hide the rest. Their SVG tooltips show the exact date and count. The decorative scanner respects reduced-motion preferences.

If GitHub's calendar markup changes or a fetch fails, generation fails before replacing existing graphics. Already committed graphics keep displaying.
