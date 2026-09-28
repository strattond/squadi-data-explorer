# Editor for the data

import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, ColumnsAutoSizeMode, GridOptionsBuilder

import blended
import data
import shared
import user
from stats import sortedDivisions


@st.cache_data
def loadConfig():
  return shared.loadConfig()


@st.cache_data
def loadDataSources( outputBase ) -> data.SquadiDetails:
  return data.loadSquadiDetails( outputBase, 'matchDetails.json', 'userMatchDetails.json', 'results.json' )


def comboString( m: blended.FixtureWrapper ) -> str:
  return m.match.toComboString()


def updateUserMatchDetails(
    userDetails: user.SquadiDetails,
    div: shared.Division,
    matchId: int,
    playerName: str,
    colId: str,
    newValue: object,
    positions: list[ str ]
) -> None:
  if colId not in ( "started", "position" ):
    return

  startedValue: bool | None = None
  positionValue: str | None = None
  if colId == "started":
    if not isinstance( newValue, bool ):
      raise ValueError( f"Expected a boolean value for started, got {newValue!r}" )
    startedValue = newValue
  else:
    if newValue is not None and ( not isinstance( newValue, str ) or newValue not in positions ):
      raise ValueError( f"Invalid position value: {newValue!r}" )
    positionValue = newValue

  userDivision = next( ( item for item in userDetails.data if item.div.name == div.name ), None )
  if userDivision is None:
    userDivision = user.DivisionData( div=div )
    userDetails.data.append( userDivision )

  userMatch = next( ( item for item in userDivision.matches if item.match.id == matchId ), None )
  if userMatch is None:
    userMatch = user.FixtureWrapper( match=user.Fixture( id=matchId ) )
    userDivision.matches.append( userMatch )

  userPlayer = next( ( item for item in userMatch.match.players if item.name == playerName ), None )
  if userPlayer is None:
    userPlayer = user.Player( name=playerName, started=False, position=None )
    userMatch.match.players.append( userPlayer )

  if colId == "started":
    assert startedValue is not None
    userPlayer.started = startedValue
  else:
    userPlayer.position = positionValue


def saveUserMatchDetails( outputBase: str, userDetails: user.SquadiDetails ) -> Path | None:
  data.makeIfMissing( outputBase )
  target = Path( outputBase ) / "userMatchDetails.json"
  backup = None
  if target.exists():
    timestamp = datetime.now().strftime( "%Y%m%d%H%M%S" )
    backup = target.with_name( f"userMatchDetails_{timestamp}.json" )
    if backup.exists():
      raise FileExistsError( f"Refusing to overwrite existing backup: {backup}" )
    shutil.copy2( target, backup )

  serialized = [ asdict( division ) for division in userDetails.data ]
  for division in serialized:
    for fixture in division[ "matches" ]:
      for player in fixture[ "match" ][ "players" ]:
        if player[ "position" ] is None:
          player.pop( "position" )
  data.dumpJson( outputBase, target.name, serialized )
  return backup


additionalCSS = """
<style>
.ag-cell.danger {
    background-color: rgba(255, 0, 0, 0.25) !important;  /* 25% red tint */
}
.ag-cell.success {
    background-color: rgba(0, 255, 0, 0.25) !important;  /* 25% green tint */
}
iframe {
        width: 100% !important;
    }
    .main, .block-container {
        max-width: 1800px;
    }
</style>
"""

additionalCSS2 = {
    ".ag-cell.danger": {
        "background-color": "rgba(255, 0, 0, 0.25) !important"
    },
    ".ag-cell.huzzah": {
        "background-color": "rgba(0, 255, 0, 0.25) !important"
    }
}

st.markdown( additionalCSS, unsafe_allow_html=True )

st.title( "Data modifications for Squadi" )

config = loadConfig()
# Get years and let user select
years = sorted( { entry.organisation.yearId + 2018 for entry in config } )
selectedYear = st.selectbox( "Competition year", years )

# Filter based on selected year.  It *should* only be 1
configForYear = [ entry for entry in config if entry.organisation.yearId == selectedYear - 2018 ]

outputBase, plotBase = shared.getPaths( configForYear[ 0 ] )

dataSources = loadDataSources( outputBase )
userDataKey = f"userMatchDetails_{selectedYear}"
if userDataKey not in st.session_state:
  st.session_state[ userDataKey ] = dataSources.userD
userDetails: user.SquadiDetails = st.session_state[ userDataKey ]
dataSources.userD = userDetails
squadiData = blended.blendSquadiDetails( dataSources )

# Now get the divisions for the year
possibleDivs = sortedDivisions( squadiData )

# Let the user pick a division
selectedDivName = st.selectbox( "Competition division", possibleDivs )

# And get it's data
selectedDiv = next( d for d in squadiData.data if d.div.name == selectedDivName )

# Position options
positions = [ "", "GK", "LB", "RB", "CB", "LCB", "RCB", "LM", "RM", "CDM", "CM", "LCM", "RCM", "LW", "RW", "ST" ]
if selectedDiv is not None:
  matches = selectedDiv.matches
  selectedMatch = st.selectbox( "Match", matches, format_func=comboString )
  with st.expander( "Edit match details" ):
    players = selectedMatch.match.players

    # Convert dataclass list → dict list for AgGrid
    rows = [ {
        "shirt": p.shirt,
        "name": p.name,
        "goals": p.goals,
        "yellows": p.yellows,
        "reds": p.reds,
        "started": p.started,
        "position": p.position,
    } for p in players ]

    df = pd.DataFrame( rows )
    gob = GridOptionsBuilder.from_dataframe( df )
    gob.configure_grid_options( singleClickEdit=True )
    gob.configure_column( "shirt", editable=False )
    gob.configure_column( "name", editable=False, resizeable=True )
    gob.configure_column(
        "goals", editable=False, cellClassRules={
            "huzzah": "x > 0",
        }
    )
    gob.configure_column(
        "yellows", editable=False, cellClassRules={
            "danger": "x > 0",
        }
    )
    gob.configure_column(
        "reds", editable=False, cellClassRules={
            "danger": "x > 0",
        }
    )
    gob.configure_column( "started", editable=True )
    gob.configure_column( "position", editable=True, cellEditor="agSelectCellEditor", cellEditorParams={ "values": positions} )

    go = gob.build()

    grid_response = AgGrid(
        df,
        gridOptions=go,
        update_mode="MODEL_CHANGED",
        custom_css=additionalCSS2,
        columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS
    )
    if (
        grid_response is not None and grid_response[ 'event_data' ] is not None
        and grid_response[ 'event_data' ][ 'type' ] == 'cellValueChanged'
    ):
      ed = grid_response[ 'event_data' ]
      colId = ed[ 'column' ][ 'colId' ]
      oldValue = ed.get( 'oldValue', None )
      newValue = ed.get( 'newValue', None )
      if colId in ( "started", "position" ):
        playerName = ed[ 'data' ][ 'name' ]
        player = next( ( item for item in players if item.name == playerName ), None )
        if player is None:
          st.error( f"Could not find player {playerName!r} in the selected match." )
        else:
          updateUserMatchDetails(
              userDetails,
              selectedDiv.div,
              selectedMatch.match.id,
              playerName,
              colId,
              newValue,
              positions
          )
          if colId == "started":
            player.started = newValue
          else:
            player.position = newValue

if st.button( "Save", key=f"save_user_match_details_{selectedYear}" ):
  backup = saveUserMatchDetails( outputBase, userDetails )
  if backup is None:
    st.success( "Saved user match details." )
  else:
    st.success( f"Saved user match details. Previous file preserved as {backup.name}." )
