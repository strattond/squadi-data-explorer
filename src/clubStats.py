import argparse
import sys
from pathlib import Path

import numpy as np

from charting import drawColourChart, plotRowData, plotStatsData
from data import (
    Player,
    PlayerStats,
    dumpJson,
    getDivByName,
    getMatchingConfig,
    getPaths,
    getPlayersForDiv,
    loadJson,
    makeIfMissing,
)
from stats import (
    accumulatePlayersStats,
    getInfographicData,
    getTeamInfographicData,
    naturalNameKey,
    sortedDivisions,
    uniquePlayers,
)


def playerPrimaryDivision( stats: Player ):
  return max( stats.stats, key=lambda div: np.nansum( stats.stats[ div ].block.appearances ) )


def calcPlayerBorrowStats( stats: Player ):
  primary = playerPrimaryDivision( stats )
  return { div: int( np.nansum( count.block.appearances ) ) for div, count in stats.stats.items() if div != primary }


def calcPlayerStats( stats: Player ):
  return { div: int( np.nansum( count.block.appearances ) ) for div, count in stats.stats.items() }


def totalBorrowings( stats: Player ):
  return sum( calcPlayerBorrowStats( stats ).values() )


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

  if 'goals' in player and player[ 'goals' ] is not None and player[ 'goals' ] > 0:
    rVal |= 16

  return rVal


def calculateBorrowings( statsOfInterest: PlayerStats, minDivisions=2 ):
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


def calcAppearanceMatrix( sortedDivPlayers: list[ tuple[ str, Player ] ], divDetail ):
  playerMatrix = np.zeros( ( len( sortedDivPlayers ), numRounds ), dtype=np.uint32 )
  for i, p in enumerate( sortedDivPlayers ):
    for r in range( numRounds ):
      match = divDetail[ 'matches' ][ r ][ 'match' ]
      matched = None
      for p2 in match[ 'players' ]:
        if p[ 0 ] == p2[ 'name' ]:
          matched = p2
          break
      playerMatrix[ i, r ] = calcAppearanceScore( matched )
  return playerMatrix


parser = argparse.ArgumentParser(
    prog="Squadi Stats Processor", description="Processes stats data previously retrieved from Squadi"
)
parser.add_argument( "--year", help="The competition year of interest", type=int )

args = parser.parse_args()

print( "Loading configuration" )
config = loadJson( 'data', 'config.json' )

print( f"Starting our squadi stats processing for year {args.year}" )

configMatch = getMatchingConfig( args.year, config )
outputBase, plotBase = getPaths( configMatch )

prevYearConfig = getMatchingConfig( args.year - 1, config )
if prevYearConfig is None:
  print( "Skipping Year on Year, no data" )
  prevYearData = None
  prevLadder = None
else:
  print( "Loading prev year data" )
  prevOutputBase, prevPlotBase = getPaths( prevYearConfig )
  prevYearData = loadJson( prevOutputBase, 'matchDetails.json' )
  prevLadder = loadJson( prevOutputBase, 'ladder.json' )

outputFolder = Path( outputBase )
if not outputFolder.exists():
  print( "Please retrieve Squadi data first" )
  sys.exit( 1 )

makeIfMissing( plotBase )

print( "Loading data" )
divisionData = loadJson( outputBase, 'matchDetails.json' )
ladder = loadJson( outputBase, 'ladder.json' )

print( " .. Getting unique players" )
players = uniquePlayers( divisionData )

print( " .. Getting divisions" )
divisions = sortedDivisions( divisionData )
print( "Accumulating stats" )
player_stats = accumulatePlayersStats( divisionData )

print( " .. Sorting by Goals" )
topN = sorted( ( ( name, player.cumStats.goals ) for name, player in player_stats.stats.items() if player.goals > 2 ),
               key=lambda item: player_stats.stats[ item[ 0 ] ].goals,
               reverse=True )

topN = topN[ :10 ]
topName = topN[ 0 ][ 0 ]
topValue = player_stats.stats[ topName ].goals

print( "Plotting Golden Boot" )
plotStatsData( divisionData, f"{plotBase}/golden_boot.png", topN, int( topValue ), "Goals", "Golden Boot Race" )

print( " .. Sorting by Fair Play" )
sorted_stats = sorted( ( ( name, player.cumStats.yellows ) for name, player in player_stats.stats.items() ),
                       key=lambda item: player_stats.stats[ item[ 0 ] ].yellows,
                       reverse=True )

topN = sorted_stats[ :5 ]
topName = sorted_stats[ 0 ][ 0 ]
topValue = player_stats.stats[ topName ].yellows

print( "Plotting Golden Card" )
plotStatsData( divisionData, f"{plotBase}/golden_card.png", topN, int( topValue ), "Yellow Cards", "Golden Card Race" )

diff = {}
print( "Calculating Club Infographic" )
print( " .. This year" )
infographic = getInfographicData( player_stats, divisionData, ladder )
if prevYearConfig is not None and prevYearData is not None and prevLadder is not None:
  prev_player_stats = accumulatePlayersStats( prevYearData )
  prev_infographic = getInfographicData( prev_player_stats, prevYearData, prevLadder )
  diff[ 'overall' ] = {
      'players': infographic[ 'players' ] - prev_infographic[ 'players' ],
      'goals': infographic[ 'goals' ] - prev_infographic[ 'goals' ],
      'yellows': infographic[ 'yellows' ] - prev_infographic[ 'yellows' ],
      'reds': infographic[ 'reds' ] - prev_infographic[ 'reds' ],
      'uniqueScorers': infographic[ 'uniqueScorers' ] - prev_infographic[ 'uniqueScorers' ],
      'uniqueCarders': infographic[ 'uniqueCarders' ] - prev_infographic[ 'uniqueCarders' ],
      'avgGoalsPerRound': infographic[ 'avgGoalsPerRound' ] - prev_infographic[ 'avgGoalsPerRound' ],
      'highestRoundGoals': infographic[ 'highestRoundGoals' ] - prev_infographic[ 'highestRoundGoals' ],
      'numRounds': infographic[ 'numRounds' ] - prev_infographic[ 'numRounds' ],
      'top_scorer': {
          "goals": infographic[ 'top_scorer' ][ 'goals' ] - prev_infographic[ 'top_scorer' ][ 'goals' ]
      },
      "top_carder": {
          "cards": infographic[ 'top_carder' ][ 'cards' ] - prev_infographic[ 'top_carder' ][ 'cards' ]
      },
      "teams": {
          "wins": infographic[ 'teams' ][ 'wins' ] - prev_infographic[ 'teams' ][ 'wins' ],
          "draws": infographic[ 'teams' ][ 'draws' ] - prev_infographic[ 'teams' ][ 'draws' ],
          "losses": infographic[ 'teams' ][ 'losses' ] - prev_infographic[ 'teams' ][ 'losses' ],
          "gf": infographic[ 'teams' ][ 'gf' ] - prev_infographic[ 'teams' ][ 'gf' ],
          "ga": infographic[ 'teams' ][ 'ga' ] - prev_infographic[ 'teams' ][ 'ga' ],
          "avgRank": infographic[ 'teams' ][ 'avgRank' ] - prev_infographic[ 'teams' ][ 'avgRank' ],
      }
  }
else:
  prev_player_stats = None

dumpJson( outputBase, 'stats.json', infographic )

print( "Calculating borrowings" )
rows = calculateBorrowings( player_stats, 2 )

col_labels = [ "Player", "Borrowed" ] + divisions + [ "Total appearances" ]
col_widths = [ 24, 12 ] + [ 20 ] * len( divisions ) + [ 12 ]
plotRowData( col_labels, rows, f"{plotBase}/borrowings.png", 1280, 960, 1, 72 )

print( "Calculating per-team details" )
for div in divisions:
  print( f" .. {div}" )

  sortedDivPlayers = getPlayersForDiv( player_stats, div )

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
  divDetail = getDivByName( divisionData, div )
  if divDetail is not None:
    numRounds = len( divDetail[ 'matches' ] )
    playerMatrix = calcAppearanceMatrix( sortedDivPlayers, divDetail )

    ## Marker colors for each state
    colors = { 0: "black", 1: "lightgreen", 2: "green", 3: 'yellow', 4: 'red'}

    colLabels = [ str( i + 1 ) for i in range( numRounds ) ]
    rowLabels = [ player[ 0 ] for i, player in enumerate( sortedDivPlayers ) ]

    drawColourChart(
        colors, numRounds, len( sortedDivPlayers ), colLabels, rowLabels, playerMatrix, f"appearances.{div}", sortedDivPlayers,
        div, plotBase
    )

  print( "   .. Team Infographics" )
  infographic = getTeamInfographicData( sortedDivPlayers, divisionData, div, ladder )
  dumpJson( outputBase, f"stats.{div}.json", infographic )

  if prevYearConfig is not None and prevYearData is not None and prevLadder is not None and prev_player_stats is not None:
    print( "   .. Year on Year" )
    prevYearDiv = getDivByName( prevYearData, div )
    if prevYearDiv is not None:
      prevSortedDivPlayers = getPlayersForDiv( prev_player_stats, div )
      prevSortedDivPlayers = sorted( prevSortedDivPlayers, key=lambda item: item[ 0 ] )
      prevPlayerNames = [ p[ 0 ] for p in prevSortedDivPlayers ]
      prev_infographic = getTeamInfographicData( prevSortedDivPlayers, prevYearData, div, prevLadder )
      if infographic is not None and prev_infographic is not None:
        diff[ div ] = {
            'players': infographic[ 'players' ] - prev_infographic[ 'players' ],
            'goals': infographic[ 'goals' ] - prev_infographic[ 'goals' ],
            'yellows': infographic[ 'yellows' ] - prev_infographic[ 'yellows' ],
            'reds': infographic[ 'reds' ] - prev_infographic[ 'reds' ],
            'uniqueScorers': infographic[ 'uniqueScorers' ] - prev_infographic[ 'uniqueScorers' ],
            'uniqueCarders': infographic[ 'uniqueCarders' ] - prev_infographic[ 'uniqueCarders' ],
            'avgGoalsPerRound': infographic[ 'avgGoalsPerRound' ] - prev_infographic[ 'avgGoalsPerRound' ],
            'highestRoundGoals': infographic[ 'highestRoundGoals' ] - prev_infographic[ 'highestRoundGoals' ],
            'numRounds': infographic[ 'numRounds' ] - prev_infographic[ 'numRounds' ],
            'top_scorer': {
                "goals": infographic[ 'top_scorer' ][ 'goals' ] - prev_infographic[ 'top_scorer' ][ 'goals' ]
            },
            "top_carder": {
                "cards": infographic[ 'top_carder' ][ 'cards' ] - prev_infographic[ 'top_carder' ][ 'cards' ]
            },
            "teams": {
                "wins": infographic[ 'teams' ][ 'wins' ] - prev_infographic[ 'teams' ][ 'wins' ],
                "draws": infographic[ 'teams' ][ 'draws' ] - prev_infographic[ 'teams' ][ 'draws' ],
                "losses": infographic[ 'teams' ][ 'losses' ] - prev_infographic[ 'teams' ][ 'losses' ],
                "gf": infographic[ 'teams' ][ 'gf' ] - prev_infographic[ 'teams' ][ 'gf' ],
                "ga": infographic[ 'teams' ][ 'ga' ] - prev_infographic[ 'teams' ][ 'ga' ],
                "avgRank": infographic[ 'teams' ][ 'avgRank' ] - prev_infographic[ 'teams' ][ 'avgRank' ],
            }
        }
    else:
      print( "     .. Skipped! No team in that division last year" )

if diff is not None:
  dumpJson( outputBase, 'diff.json', diff )
print( "Complete" )
