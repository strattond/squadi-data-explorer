# Copilot instructions for squadi-data-explorer

## Project overview

This is a Python 3.13 project for collecting and analysing football registration data from Squadi. It has three user-facing flows:

- `src/fetchSquadi.py` uses Playwright to load Squadi pages, intercept the relevant API responses, and cache normalized JSON under `output/<yearId>/`.
- `src/clubStats.py` loads the cached data, calculates player/team statistics, and writes PNG charts plus JSON summaries under `plots/<yearId>/` and `output/<yearId>/`.
- `src/editor.py` is a Streamlit app for reviewing/editing user match metadata such as starters and positions.

The data model is deliberately split into source schemas:

- `fixed.py` represents fetched match/player participation data.
- `user.py` represents user-maintained match metadata.
- `data.py` owns shared persisted models, JSON serialization/deserialization, statistics accumulation, ladder/results models, and filesystem helpers.
- `blended.py` joins fixed data, user data, and high-level results by division, match ID, and player name. Downstream statistics code should generally consume this blended model.
- `shared.py` contains configuration models and the generic dataclass-from-JSON loader.
- `stats.py` calculates player aggregates, division ordering, and infographic inputs.
- `charting.py` renders matplotlib/Pillow output consumed by `clubStats.py`.

## Setup and commands

The README documents UV and Playwright. From the repository root in PowerShell:

```powershell
uv venv
.\.venv\Scripts\Activate.ps1
uv sync
playwright install
```

The repository currently declares runtime packages in `requirements.txt` and does not contain a `pyproject.toml` or `uv.lock`. If `uv sync` is unavailable in a fresh checkout, install the declared requirements into the active environment instead:

```powershell
uv pip install -r requirements.txt
```

Run the ingestion pipeline with a year present in `data/config.json`:

```powershell
python .\src\fetchSquadi.py --summary --year 8
python .\src\fetchSquadi.py --match --year 8
```

Use `--div` together with the required `--summary` or `--match` mode when division-level match data is needed. `--recent DAYS` controls the recent-results window; `--next DAYS` is accepted for future-match handling.

Generate statistics after the required cached data exists:

```powershell
python .\src\clubStats.py --year 8
```

Start the Streamlit editor from the repository root so its relative `data/`, `output/`, and `plots/` paths resolve correctly:

```powershell
streamlit run .\src\editor.py
```

## Testing and linting

No test files are currently tracked, so there is no repository test suite or project-specific test command. When tests are added, run one test with the standard pytest node syntax, for example:

```powershell
pytest .\tests\test_stats.py::test_name
```

`setup.cfg` contains the YAPF formatting configuration (128-column limit, two-space indentation, and spaces inside brackets). The recommended VS Code extensions also include Ruff, but there is no Ruff configuration or scripted lint task in the repository. Use the configured formatter when formatting Python:

```powershell
yapf --recursive --diff .\src
yapf --recursive --in-place .\src
```

## Configuration and generated data

`data/config.json` is a JSON list of organisation entries. Each entry has an `organisation` object (`yearId`, `organisationKey`, `competitionUniqueKey`) and a `divisions` list containing `name`, `divisionId`, and `teamId`. Add or update configuration before fetching a new season.

The fetcher writes cached files such as `ladder.json`, `results.json`, `next.json`, `recent.json`, `matchDetails.json`, `userMatchDetails.json`, and optionally `divMatchDetails.json` below the year-specific output directory. Statistics writes `stats.json`, `diff.json`, and generated plots. These files are the pipeline’s interchange format; preserve field names and dataclass shapes when changing models.

Most code assumes it is launched from the repository root and uses relative paths. Keep that working-directory contract when adding commands or tests. `output/`, virtual environments, caches, and Streamlit secrets are ignored by Git; do not add generated fetch results or local secrets to commits.

## Code conventions specific to this repository

- Match the existing YAPF style: two-space indentation, spaces inside brackets, and the spacing shown in `setup.cfg`. Keep imports compatible with scripts being launched directly from `src/`.
- Use the existing dataclasses and `shared.from_dict`/`data.default` serialization path for persisted data rather than introducing a second JSON schema or ad-hoc dictionaries.
- Preserve the source/blended boundary. Add source-specific fields to `fixed.py` or `user.py`; add cross-source joins and presentation-facing fields to `blended.py`; keep aggregate calculations in `stats.py` or `data.py`.
- Division identity is based on `divisionId`/team IDs when joining fetched records, while user-facing sorting and selection use the division `name`. Match identity is the Squadi match ID, and player identity in blending is the player name.
- Statistics use NumPy arrays with `NaN` to represent a round where a player has no data. Use the existing `maskedSum`, `np.nansum`, and cumulative-stat patterns so missing rounds are not treated as appearances.
- Fetching is incremental: existing JSON is loaded, new rounds/matches are merged, and files are rewritten only for the modes that ran. Avoid replacing this with a destructive full refresh unless the behavior is intentional.
- Playwright response handlers intentionally inspect Squadi API URLs rather than scraping rendered HTML. Changes to fetch logic should preserve the response interception and `networkidle` synchronization.
- Chart output depends on the current relative asset path for `ball.png` and on the year-specific plot directory. Create output directories with the existing `data.makeIfMissing`/`shared.getPaths` helpers.
- `editor.py` runs as a Streamlit script, not as an importable library module. Streamlit caching is used around configuration, source loading, and blending; preserve those boundaries when changing the UI.

