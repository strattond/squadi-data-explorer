import argparse
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

import data
import fixed
import shared
import user
from charting import drawColourChart, plotRowData, plotStatsData
from stats import (
    accumulatePlayersStats,
    getInfographicData,
    getMatchingUserMatch,
    getTeamInfographicData,
    naturalNameKey,
    sortedDivisions,
    uniquePlayers,
)


def playerPrimaryDivision( stats: data.Player ):
  return max( stats.stats, key=lambda div: np.nansum( stats.stats[ div ].block.appearances ) )


def calcPlayerBorrowStats( stats: data.Player ):
  primary = playerPrimaryDivision( stats )
  return { div: int( np.nansum( count.block.appearances ) ) for div, count in stats.stats.items() if div != primary }


def calcPlayerStats( stats: data.Player ):
  return { div: int( np.nansum( count.block.appearances ) ) for div, count in stats.stats.items() }


def totalBorrowings( stats: data.Player ):
  return sum( calcPlayerBorrowStats( stats ).values() )


def calcAppearanceScore(
    player: fixed.Player | user.Player | None, userPlayer: fixed.Player | user.Player | None
) -> int:
  if player is None or not isinstance( player, fixed.Player ):
    # Can't score goals, can't get carded, can't start or appear
    return 0
  rVal: int = 1
  # Bit 0 (1) - Played
  # Bit 1 (2) - Started
  # Bit 2 (4) - Yellows
  # Bit 3 (8) - Reds
  # Bit 4 (16) - Goals
  # colors = { 0: "black", 1: "lightgreen", 2: "green", 3: 'yellow', 4: 'red' }
  if player.reds > 0:
    rVal |= 8
  if player.yellows > 0:
    if player.yellows > 1:
      rVal |= 8
    else:
      rVal |= 4

  if userPlayer is not None and isinstance( userPlayer, user.Player ) and userPlayer.started:
    rVal |= 2

  if player.goals > 0:
    rVal |= 16

  return rVal


def calculateBorrowings( statsOfInterest: data.PlayerStats, minDivisions=2 ):
  rows = []
  filtered_players = { name: stats for name, stats in statsOfInterest.stats.items() if len( stats.stats ) >= minDivisions }
  # But we only care about "borrowings".  And we can take the punt that a primary team is the one they've appeared in the most
  for name, stats in sorted(
      filtered_players.items(), key=lambda item: ( -totalBorrowings( item[ 1 ] ), naturalNameKey( item[ 0 ] ) )
  ):
    totalBorrow = totalBorrowings( stats )
    if totalBorrow > 1:
      playedStats = calcPlayerStats( stats )
      row = [ name, totalBorrow ] + [ playedStats.get( div, "" ) for div in divisions ] + [ int( stats.appearances ) ]
      rows.append( row )
  return rows


def calcAppearanceMatrix(
    sortedDivPlayers: list[ tuple[ str, data.Player ] ], divDetail: fixed.DivisionData | user.DivisionData,
    userDivDetail: fixed.DivisionData | user.DivisionData | None
):
  playerMatrix = np.zeros( ( len( sortedDivPlayers ), numRounds ), dtype=np.uint32 )
  for i, p in enumerate( sortedDivPlayers ):
    for r in range( numRounds ):
      match = divDetail.matches[ r ].match
      uMatch = getMatchingUserMatch( userDivDetail, match )
      matched = None
      uMatched = None
      for p2 in match.players:
        if p[ 0 ] == p2.name:
          matched = p2
          break
      if uMatch is not None:
        for p2 in uMatch.match.players:
          if p[ 0 ] == p2.name:
            uMatched = p2
            break
      playerMatrix[ i, r ] = calcAppearanceScore( matched, uMatched )
  return playerMatrix


parser = argparse.ArgumentParser(
    prog="Squadi Stats Processor", description="Processes stats data previously retrieved from Squadi"
)
parser.add_argument( "--year", help="The competition year of interest", type=int )

args = parser.parse_args()

print( "Loading configuration" )
configData = data.loadJson( 'data', 'config.json' )
if configData is None:
  print( "Please provide a valid configuration file" )
  sys.exit( 1 )
config = [ shared.from_dict( data.ConfigEntry, d ) for d in configData ] if configData else []

print( f"Starting our squadi stats processing for year {args.year}" )

ladder: list[ data.Ladder ] = []
prevLadder: list[ data.Ladder ] = []

configMatch = data.getMatchingConfig( args.year, config )
outputBase, plotBase = data.getPaths( configMatch )

prevYearConfig = data.getMatchingConfig( args.year - 1, config )
if prevYearConfig is None:
  print( "Skipping Year on Year, no data" )
  unfilteredSquadiData = data.SquadiDetails( fixed.SquadiDetails(), user.SquadiDetails() )
else:
  print( "Loading prev year data" )
  prevOutputBase, prevPlotBase = data.getPaths( prevYearConfig )
  unfilteredSquadiData = data.loadSquadiDetails( prevOutputBase, 'matchDetails.json', 'userMatchDetails.json' )
  prevLadder = data.loadLadder( prevOutputBase, 'ladder.json' )

outputFolder = Path( outputBase )
if not outputFolder.exists():
  print( "Please retrieve Squadi data first" )
  sys.exit( 1 )

data.makeIfMissing( plotBase )

print( "Loading data" )
squadiData = data.loadSquadiDetails( outputBase, 'matchDetails.json', 'userMatchDetails.json' )
if squadiData.fixedFound is False:
  print( "No match data available" )
  sys.exit( 1 )

ladder = data.loadLadder( outputBase, 'ladder.json' )

print( " .. Getting unique players" )
players = uniquePlayers( squadiData.fixed )

print( " .. Getting divisions" )
divisions = sortedDivisions( squadiData.fixed )
print( "Accumulating stats" )
player_stats = accumulatePlayersStats( squadiData )

print( " .. Sorting by Goals" )
topN = sorted( ( ( name, player.cumStats.goals ) for name, player in player_stats.stats.items() if player.goals > 2 ),
               key=lambda item: player_stats.stats[ item[ 0 ] ].goals,
               reverse=True )

topN = topN[ :10 ]
topName = topN[ 0 ][ 0 ]
topValue = player_stats.stats[ topName ].goals

print( "Plotting Golden Boot" )
plotStatsData( squadiData, f"{plotBase}/golden_boot.png", topN, int( topValue ), "Goals", "Golden Boot Race" )

print( " .. Sorting by Fair Play" )
sorted_stats = sorted( ( ( name, player.cumStats.yellows ) for name, player in player_stats.stats.items() ),
                       key=lambda item: player_stats.stats[ item[ 0 ] ].yellows,
                       reverse=True )

topN = sorted_stats[ :5 ]
topName = sorted_stats[ 0 ][ 0 ]
topValue = player_stats.stats[ topName ].yellows

print( "Plotting Golden Card" )
plotStatsData( squadiData, f"{plotBase}/golden_card.png", topN, int( topValue ), "Yellow Cards", "Golden Card Race" )

diff: dict[ str, data.InfoStats ] = {}
year: dict[ str, data.InfoStats ] = {}
print( "Calculating Club Infographic" )
print( " .. This year" )
infographic = getInfographicData( player_stats, squadiData.fixed, ladder )
if infographic is not None:
  year[ 'overall' ] = infographic
if prevYearConfig is not None:
  prevYearSquadiData = unfilteredSquadiData.slice( divisions )
  prev_player_stats = accumulatePlayersStats( prevYearSquadiData )
  print( " .. Last year" )
  prev_infographic = getInfographicData( prev_player_stats, prevYearSquadiData.fixed, prevLadder )
  if infographic is not None and prev_infographic is not None:
    diff[ 'overall' ] = infographic - prev_infographic
    ufStats = accumulatePlayersStats( unfilteredSquadiData )
    crNames = [ p for p in player_stats.stats ]
    ppNames = [ p for p in ufStats.stats ]
    lstPlayers = [ name for name in ppNames if name not in crNames ]
    newPlayers = [ name for name in crNames if name not in ppNames ]
    diff[ 'overall' ].lostPlayers = len( lstPlayers )
    diff[ 'overall' ].newPlayers = len( newPlayers )
else:
  prevYearSquadiData = data.SquadiDetails()
  prev_player_stats = None

print( "Calculating borrowings" )
rows = calculateBorrowings( player_stats, 2 )

col_labels = [ "Player", "Borrowed" ] + divisions + [ "Total appearances" ]
col_widths = [ 24, 12 ] + [ 20 ] * len( divisions ) + [ 12 ]
plotRowData( col_labels, rows, f"{plotBase}/borrowings.png", 1280, 960, 1, 72 )

print( "Calculating per-team details" )
for div in divisions:
  print( f" .. {div}" )

  sortedDivPlayers = data.getPlayersForDiv( player_stats, div )

  rows = []
  for name, stats in sortedDivPlayers:
    row = [
        name,
        int( np.nansum( stats.stats[ div ].block.appearances ) ),
        int( np.nansum( stats.stats[ div ].block.starts ) )
    ]
    rows.append( row )

  print( "   .. Appearances" )
  col_labels = [ "Player", "Appearances", "Starts" ]
  plotRowData( col_labels, rows, f"{plotBase}/teamList.{div}.png", 1280, ( 48 * ( len( rows ) + 1 ) ), 2 )

  sortedDivPlayers = sorted( sortedDivPlayers, key=lambda item: item[ 0 ] )
  playerNames = [ p[ 0 ] for p in sortedDivPlayers ]

  print( "   .. Player Matrix" )
  divDetail = data.getDivByName( squadiData.fixed.data, div )
  userDivDetail = data.getDivByName( squadiData.user.data, div )
  if divDetail is not None:
    numRounds = len( divDetail.matches )
    playerMatrix = calcAppearanceMatrix( sortedDivPlayers, divDetail, userDivDetail )

    ## Marker colors for each state
    colors = { 0: "black", 1: "lightgreen", 2: "green", 3: 'yellow', 4: 'red'}

    colLabels = [ str( i + 1 ) for i in range( numRounds ) ]
    rowLabels = [ player[ 0 ] for i, player in enumerate( sortedDivPlayers ) ]

    drawColourChart(
        colors, numRounds, len( sortedDivPlayers ), colLabels, rowLabels, playerMatrix, f"appearances.{div}", sortedDivPlayers,
        div, plotBase
    )

  print( "   .. Team Infographics" )
  infographic = getTeamInfographicData( sortedDivPlayers, squadiData, div, ladder )
  if infographic is not None:
    year[ div ] = infographic
    data.dumpJson( outputBase, f"stats.{div}.json", asdict( infographic ) )

  if prevYearConfig is not None and unfilteredSquadiData.fixedFound and prevLadder is not None and prev_player_stats is not None:
    print( "   .. Year on Year" )
    prevYearDiv = data.getDivByName( prevYearSquadiData.fixed.data, div )
    if prevYearDiv is not None:
      prevSortedDivPlayers = data.getPlayersForDiv( prev_player_stats, div )
      prevSortedDivPlayers = sorted( prevSortedDivPlayers, key=lambda item: item[ 0 ] )
      prevPlayerNames = [ p[ 0 ] for p in prevSortedDivPlayers ]
      prev_infographic = getTeamInfographicData( prevSortedDivPlayers, prevYearSquadiData, div, prevLadder )
      if infographic is not None and prev_infographic is not None:
        diff[ div ] = infographic - prev_infographic

        lstPlayers = [ name for name in prevPlayerNames if name not in playerNames ]
        newPlayers = [ name for name in playerNames if name not in prevPlayerNames ]
        diff[ div ].lostPlayers = len( lstPlayers )
        diff[ div ].newPlayers = len( newPlayers )
    else:
      print( "     .. Skipped! No team in that division last year" )

if diff is not None:
  data.dumpJson( outputBase, 'diff.json', diff )
if year is not None and len( year ) > 0:
  data.dumpJson( outputBase, 'stats.json', year )

print( "Complete" )
