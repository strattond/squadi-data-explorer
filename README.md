# squadi-data-explorer
Explores the Squadi football registration site

## Setting up

### Pre-requisites

* Install a compatible version of Python (tested at 3.13.14)
* Install a compatible version of UV (tested at 0.12.3)

### Code

Clone the github repository as you ordinarily would.

Create the virtual environment it will run under, then install the application extras:

```
uv venv
./.venv/Scripts/activate.ps1
uv sync --extra fetch --extra stats --extra editor
```

And ensure that you install the playwright browsers before attempting to run the program.

```
playwright install
```

### Data

Firstly, you need a `data/config.json` file that contains the organisation as well as team information you need.

For an organisation, you need the year, organisation key and competition unique key.

For a team, you need a name, division ID and team ID.

An example:

```json
[
  {
    "organisation": {
      "yearId": 8,
      "organisationKey": "45ba5d3f-a4de-4c4f-ad1b-3e474777bc64",
      "competitionUniqueKey": "ed9f3608-81fb-4c60-82b5-7c1ab2149180"
    },
    "divisions": [
      {
        "name": "Metro 5 South",
        "divisionId": "9177",
        "teamId": 95328
      }
    ]
  }
]
```

## Running it

To get overall information for the season
```
python .\src\fetchSquadi.py --summary --year 8
```

To get detailed match information on completed matches (requires overall information first)
```
python .\src\fetchSquadi.py --match --year 8
```

To generate statistics and plots from the data
```
python .\src\clubStats.py --year 8
```

## Reusing the data library

The `squadi_data` package contains the persisted models, JSON loaders, blending helpers, and statistics functions. Install this repository into another local uv project as an editable dependency by adding the following to that project's `pyproject.toml`:

```toml
[project]
dependencies = [
  "squadi-data-explorer",
]

[tool.uv.sources]
squadi-data-explorer = { path = "../github/squadi-data-explorer", editable = true }
```

Adjust the relative path to this checkout, then run `uv sync`. The core library requires NumPy; install this project's `fetch`, `stats`, or `editor` extras only when using those features.

Load the cached season data by passing the year-specific output directory:

```python
from pathlib import Path
from squadi_data import blend_season, load_season

season = load_season( Path( "D:/Projects/github/squadi-data-explorer/output/8" ) )
blended_season = blend_season( season )
for division in blended_season.data:
  for fixture in division.matches:
    print( division.div.name, fixture.match.id, len( fixture.match.players ) )
```

`load_season` reads `matchDetails.json`, `userMatchDetails.json`, and `results.json` from the given directory. For ladder data, use `squadi_data.data.loadLadder(output_dir, "ladder.json")`. Fetching and chart generation remain command-line workflows in this repository; run the fetch commands from this repository root to use its `data/config.json` and year-specific `output/` paths.