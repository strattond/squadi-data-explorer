# squadi-data-explorer
Explores the Squadi football registration site

## Setting up

### Pre-requisites

* Install a compatible version of Python (tested at 3.13.14)
* Install a compatible version of UV (tested at 0.12.3)

### Code

Clone the github repository as you ordinarily would.

Create the virtual environment it will run under, then sync the packages e.g. 

```
uv venv
./.venv/Scripts/activate.ps1
uv sync
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