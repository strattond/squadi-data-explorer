# Editor for the data

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, ColumnsAutoSizeMode, GridOptionsBuilder

import blended
import data
import shared
from stats import sortedDivisions


@st.cache_data
def loadConfig():
  return shared.loadConfig()


@st.cache_data
def loadDataSources( outputBase ) -> data.SquadiDetails:
  return data.loadSquadiDetails( outputBase, 'matchDetails.json', 'userMatchDetails.json', 'results.json' )


@st.cache_data
def loadBlendedData( combSquadiData: data.SquadiDetails ) -> blended.SquadiDetails:
  return blended.blendSquadiDetails( combSquadiData )


def comboString( m: blended.FixtureWrapper ) -> str:
  return m.match.toComboString()


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
squadiData = loadBlendedData( dataSources )
if 'user' not in st.session_state:
  st.session_state.user = dataSources.userD

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
      #print( "Update fired" )
      ed = grid_response[ 'event_data' ]
      row = ed[ 'rowIndex' ]
      colId = ed[ 'column' ][ 'colId' ]
      oldValue = ed.get( 'oldValue', None )
      newValue = ed.get( 'newValue', None )
      print( f"[{row},{colId}]: {oldValue} => {newValue}" )
