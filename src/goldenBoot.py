import argparse
import json
import sys
from pathlib import Path

import numpy as np

from charting import drawColourChart, plotRowData, plotStatsData
from data import getMatchingConfig, getPaths, loadJson, makeIfMissing
from stats import accumulateStats, getInfographicData, naturalNameKey, sortedDivisions, uniquePlayers


def playerPrimaryDivision( stats ):
  return max( stats[ "div" ], key=lambda div: stats[ "div" ][ div ][ 'appearances' ] )


def playerPlayedInDivision( stats, div ):
  return div in stats[ 'div' ] and stats[ 'div' ][ div ][ 'appearances' ] > 0


def calcPlayerBorrowStats( stats ):
  primary = playerPrimaryDivision( stats )
  return { div: count[ 'appearances' ] for div, count in stats[ "div" ].items() if div != primary }


def calcPlayerStats( stats ):
  return { div: count[ 'appearances' ] for div, count in stats[ "div" ].items() }


def totalBorrowings( stats ):
  return sum( calcPlayerBorrowStats( stats ).values() )


def getDiv( data, match ):
  for d in data:
    if d[ 'div' ][ 'name' ] == match:
      return d
  return None


def calcAppearanceScore( player ) -> int:
  if player is None:
    # Can't score goals, can't get carded, can't start or appear
    return 0
  rVal: int = 1
  # Bit 0 (1) - Played
  # Bit 1 (2) - Started
  # Bit 2 (4) - Yellows
  # Bit 3 (8) - Reds
  # Bit 4 (16) - Goals
  # colors = { 0: "black", 1: "lightgreen", 2: "green", 3: 'yellow', 4: 'red' }
  if 'reds' in player and player[ 'reds' ] is not None and player[ 'reds' ] > 0:
    rVal |= 8
  if 'yellows' in player and player[ 'yellows' ] is not None and player[ 'yellows' ] > 0:
    if player[ 'yellows' ] > 1:
      rVal |= 8
    else:
      rVal |= 4
  if 'started' in player and player[ 'started' ] is not None and player[ 'started' ]:
    rVal |= 2

  if 'goals' in player and p2[ 'goals' ] is not None and player[ 'goals' ] > 0:
    rVal |= 16

  return rVal


parser = argparse.ArgumentParser(
    prog="Squadi Stats Processor", description="Processes stats data previously retrieved from Squadi"
)
parser.add_argument( "--year", help="The competition year of interest", type=int )

args = parser.parse_args()

print( "Loading configuration" )
with open( "data/config.json", "r" ) as f:
  config = json.load( f )

print( f"Starting our squadi stats processing for year {args.year}" )

configMatch = getMatchingConfig( args.year, config )
outputBase, plotBase = getPaths( configMatch )

outputFolder = Path( outputBase )
if not outputFolder.exists():
  print( "Please retrieve Squadi data first" )
  sys.exit( 1 )

makeIfMissing( plotBase )

print( "Loading data" )
data = loadJson( outputBase, 'matchDetails.json' )

print( " .. Getting unique players" )
players = uniquePlayers( data )

print( " .. Getting divisions" )
divisions = sortedDivisions( data )
print( "Accumulating stats" )
player_stats = accumulateStats( data )

print( " .. Sorting by Goals" )
topN = sorted( ( ( name, stats ) for name, stats in player_stats.items() if stats[ 'goals' ] > 2 ),
               key=lambda item: item[ 1 ][ "goals" ],
               reverse=True )

topN = topN[ :10 ]

print( "Plotting Golden Boot" )
plotStatsData( data, f"{plotBase}/golden_boot.png", topN, "roundGoals", "goals", "Goals", "Golden Boot Race" )

print( " .. Sorting by Fair Play" )
sorted_stats = sorted( player_stats.items(), key=lambda item: item[ 1 ][ "fairPlay" ], reverse=True )
topN = sorted_stats[ :5 ]

print( "Plotting Golden Card" )
plotStatsData( data, f"{plotBase}/golden_card.png", topN, "roundYellows", "yellows", "Cards", "Golden Card Race" )

infographic = getInfographicData( player_stats, data )

with open( f"{outputBase}/stats.json", "w", encoding="utf-8" ) as f:
  json.dump( infographic, f, indent=2, ensure_ascii=False )

print( "Calculating borrowings" )
rows = []
filtered_players = { name: stats for name, stats in player_stats.items() if len( stats[ "div" ] ) >= 2 }
# But we only care about "borrowings".  And we can take the punt that a primary team is the one they've appeared in the most
for name, stats in sorted(
    filtered_players.items(), key=lambda item: ( -totalBorrowings( item[ 1 ] ), naturalNameKey( item[ 0 ] ) )
):
  totalBorrow = totalBorrowings( stats )
  if totalBorrow > 1:
    playedStats = calcPlayerStats( stats )
    row = [ name, totalBorrow ] + [ playedStats.get( div, "" ) for div in divisions ] + [ stats[ "appearances" ] ]
    rows.append( row )

col_labels = [ "Player", "Borrowed" ] + divisions + [ "Total appearances" ]
col_widths = [ 24, 12 ] + [ 20 ] * len( divisions ) + [ 12 ]
plotRowData( col_labels, rows, f"{plotBase}/borrowings.png", 1280, 960, 1, 72 )

print( "Calculating appearances" )
for div in divisions:
  print( f" .. {div}" )
  divPlayers = { name: stats for name, stats in player_stats.items() if playerPlayedInDivision( stats, div ) }

  sortedDivPlayers = sorted( divPlayers.items(), key=lambda item: ( -item[ 1 ][ "div" ][ div ][ 'appearances' ], item[ 0 ] ) )

  rows = []
  for name, stats in sortedDivPlayers:
    row = [ name, stats[ "div" ][ div ][ 'appearances' ], stats[ 'starts' ] ]
    rows.append( row )

  col_labels = [ "Player", "Appearances", "Starts" ]
  plotRowData( col_labels, rows, f"{plotBase}/teamList.{div}.png", 1280, ( 48 * ( len( rows ) + 1 ) ), 2 )

  sortedDivPlayers = sorted( divPlayers.items(), key=lambda item: item[ 1 ][ "name" ] )
  playerNames = [ p[ 1 ][ 'name' ] for p in sortedDivPlayers ]

  divDetail = getDiv( data, div )
  if divDetail is not None:
    numRounds = len( divDetail[ 'matches' ] )
    playerMatrix = np.zeros( ( len( sortedDivPlayers ), numRounds ), dtype=np.uint32 )
    for i, p in enumerate( sortedDivPlayers ):
      for r in range( numRounds ):
        match = divDetail[ 'matches' ][ r ][ 'match' ]
        matched = None
        for p2 in match[ 'players' ]:
          if p[ 1 ][ 'name' ] == p2[ 'name' ]:
            matched = p2
            break
        playerMatrix[ i, r ] = calcAppearanceScore( matched )

    ## Marker colors for each state
    colors = { 0: "black", 1: "lightgreen", 2: "green", 3: 'yellow', 4: 'red'}

    colLabels = [ str( i + 1 ) for i in range( numRounds ) ]
    rowLabels = [ player[ 1 ][ 'name' ] for i, player in enumerate( sortedDivPlayers ) ]

    drawColourChart(
        colors, numRounds, len( sortedDivPlayers ), colLabels, rowLabels, playerMatrix, f"appearances.{div}", sortedDivPlayers,
        div, plotBase
    )

print( "Complete" )
