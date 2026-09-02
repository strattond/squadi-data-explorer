import re

import numpy as np

import fixed
import user
from data import (
    InfoStats,
    Ladder,
    Player,
    PlayerStats,
    SquadiDetails,
    TeamStats,
    getDivByName,
)


def makeDivBlock( numRounds ):
  return {
      "appearances": 0,
      "goals": np.full( numRounds, np.nan ),
      "yellows": np.full( numRounds, np.nan ),
      "reds": np.full( numRounds, np.nan ),
      "fairPlay": np.full( numRounds, np.nan ),
  }


def newEntryValue( stat, value ):
  return np.nan_to_num( stat, nan=0.0 ) + value


def naturalDivKey( divName ):
  # Extract leading integer (division number)
  m = re.match( r"(\d+)", divName )
  return int( m.group( 1 ) ) if m else float( 'inf' )


def mixedDivKey( divName ):
  # Extract leading integer (division number)
  m = re.match( r"\D*(\d+)\D*", divName )
  return int( m.group( 1 ) ) if m else float( 'inf' )


def naturalNameKey( playerName ):
  # Extract names
  m = re.match( r"(\w+) (\w+)", playerName )
  if m is not None:
    return m.group( 2 ) + " " + m.group( 1 )
  else:
    return ''


def uniquePlayers( data: fixed.SquadiDetailsFixed ) -> list[ fixed.PlayerFixed ]:
  unique_players = set()

  for division in data.data:
    for match in division.matches:
      for player in match.match.players:
        unique_players.add( player.name )

  return sorted( unique_players )


def sortedDivisions( data: fixed.SquadiDetailsFixed ) -> list[ str ]:
  all_divisions = set()

  for division in data.data:
    all_divisions.add( division.div.name )

  return sorted( all_divisions, key=mixedDivKey )


def maxMatches( data: fixed.SquadiDetailsFixed | user.SquadiDetailsUser ):
  return max( len( d.matches ) for d in data.data )


def getMatchingUserMatch( userDivData: fixed.DivisionDataFixed | user.DivisionDataUser | None, match ):
  if userDivData is None:
    return None
  return next( ( uMatch for uMatch in userDivData.matches if uMatch.match.id == match ), None )


def getMatchingPlayer( name, userMatchNum: fixed.FixtureWrapperFixed | user.FixtureWrapperUser | None ):
  if userMatchNum is None:
    return None
  return next( ( userPlayer for userPlayer in userMatchNum.match.players if userPlayer.name == name ), None )


def accumulatePlayersStats( data: SquadiDetails ) -> PlayerStats:

  player_stats = PlayerStats()
  maxRounds = maxMatches( data.fixed )
  for division in data.fixed.data:
    divName = division.div.name
    print( f" .. Processing {divName}" )
    userDivData = getDivByName( data.user.data, divName )
    for matchNum, match in enumerate( division.matches ):
      userMatchNum = getMatchingUserMatch( userDivData, match.match.id )
      for player in match.match.players:
        name = player.name
        stats = player_stats.get( name, maxRounds, divName )

        # appearances
        divStats = stats.stats[ divName ]
        divStats.block.appearances[ matchNum ] = 1

        # goals/yellows/reds may not exist on this record
        divStats.block.goals[ matchNum ] = player.goals
        divStats.block.yellows[ matchNum ] = player.yellows
        divStats.block.reds[ matchNum ] = player.reds
        userPlayer = getMatchingPlayer( name, userMatchNum )
        if userPlayer is not None and isinstance( userPlayer, user.PlayerUser ):
          # player.get( "started", 0 )
          didStart = userPlayer.started
          divStats.block.starts[ matchNum ] = 0 if not didStart else 1
        else:
          divStats.block.starts[ matchNum ] = 0  # No matching user data says we have no start

  player_stats.accumulate( maxRounds )
  return player_stats


def list_to_dict( listData: list[ tuple[ str, Player ] ] ) -> dict[ str, Player ]:
  rVal = {}
  for i in listData:
    rVal[ i[ 0 ] ] = i[ 1 ]
  return rVal


def getTeamInfographicData(
    player_stats: list[ tuple[ str, Player ] ], data: SquadiDetails, div: str, ladders: list[ Ladder ]
) -> InfoStats | None:

  divDetail = getDivByName( data.fixed.data, div )
  if divDetail is None:
    return None
  divPlayers = list_to_dict( player_stats )

  # Time to Slice and Dice
  sliced = [ player.slice( div ) for player in divPlayers.values() ]

  cumRounds = len( divDetail.matches )  # maxMatches( data )
  total_goals = sum( player.goals for player in sliced )
  total_yellows = sum( player.yellows for player in sliced )
  total_reds = sum( player.reds for player in sliced )
  unique_scorers = sum( 1 for stats in sliced if stats.goals > 0 )
  unique_carders = sum( 1 for stats in sliced if stats.yellows > 0 or stats.reds > 0 )
  avg_goals_per_week = total_goals / cumRounds if cumRounds else 0
  round_totals = [ 0 ] * cumRounds

  for player in sliced:
    for i, g in enumerate( player.stats.goals ):
      if not np.isnan( g ):
        round_totals[ i ] += g

  highest_round = max( range( cumRounds ), key=lambda i: round_totals[ i ] )
  highest_round_goals = round_totals[ highest_round ]

  top_scorer = max( sliced, key=lambda item: item.goals )
  top_carder = max( sliced, key=lambda item: ( item.yellows + item.reds ) )

  teamIDs = [ divDetail.div.teamId ]
  totals = getTotalsForTeams( ladders, teamIDs )

  rVal = InfoStats()
  rVal.players = len( divPlayers )
  rVal.goals = total_goals
  rVal.yellows = total_yellows
  rVal.reds = total_reds
  rVal.uniqueScorers = unique_scorers
  rVal.uniqueCarders = unique_carders
  rVal.avgGoalsPerRound = round( avg_goals_per_week, 2 )
  rVal.highestRound = highest_round + 1
  rVal.highestRoundGoals = int( highest_round_goals )
  rVal.numRounds = cumRounds
  rVal.top_scorer.name = top_scorer.name
  rVal.top_scorer.value = int( top_scorer.goals )

  rVal.top_carder.name = top_carder.name
  rVal.top_carder.value = int( top_carder.yellows + top_carder.reds )

  rVal.teams = totals
  return rVal


def getTotalsForTeams( ladders: list[ Ladder ], teamIDs: list[ int ] ) -> TeamStats:
  totals = TeamStats()
  for ladder in ladders:
    for row in ladder.table:
      if row.teamId in teamIDs:
        totals.add( row )

  return totals


def getInfographicData(
    player_stats: PlayerStats, divisionData: fixed.SquadiDetailsFixed, ladders: list[ Ladder ]
) -> InfoStats | None:

  cumRounds = maxMatches( divisionData )
  total_goals = int( sum( stats.goals for stats in player_stats.stats.values() ) )
  total_yellows = int( sum( stats.yellows for stats in player_stats.stats.values() ) )
  total_reds = int( sum( stats.reds for stats in player_stats.stats.values() ) )
  unique_scorers = sum( 1 for stats in player_stats.stats.values() if stats.goals > 0 )
  unique_carders = sum( 1 for stats in player_stats.stats.values() if stats.yellows > 0 or stats.reds > 0 )
  avg_goals_per_week = total_goals / cumRounds if cumRounds else 0
  round_totals = [ 0 ] * cumRounds

  for stats in player_stats.stats.values():
    for i, g in enumerate( stats.roundStats.goals ):
      if not np.isnan( g ):
        round_totals[ i ] += g

  highest_round = max( range( cumRounds ), key=lambda i: round_totals[ i ] )
  highest_round_goals = round_totals[ highest_round ]

  top_scorer = max( player_stats.stats.items(), key=lambda item: item[ 1 ].goals )
  top_carder = max( player_stats.stats.items(), key=lambda item: ( item[ 1 ].yellows + item[ 1 ].reds ) )

  teamIDs = [ div.div.teamId for div in divisionData.data ]
  totals = getTotalsForTeams( ladders, teamIDs )

  avg_rank = totals.avgRank / len( teamIDs ) if len( teamIDs ) else 0

  rVal = InfoStats()
  rVal.players = len( player_stats.stats )
  rVal.goals = total_goals
  rVal.yellows = total_yellows
  rVal.reds = total_reds
  rVal.uniqueScorers = unique_scorers
  rVal.uniqueCarders = unique_carders
  rVal.avgGoalsPerRound = round( avg_goals_per_week, 2 )
  rVal.highestRound = highest_round + 1
  rVal.highestRoundGoals = int( highest_round_goals )
  rVal.numRounds = cumRounds
  rVal.top_scorer.name = top_scorer[ 1 ].name
  rVal.top_scorer.value = int( top_scorer[ 1 ].goals )
  rVal.top_carder.name = top_carder[ 1 ].name
  rVal.top_carder.value = int( top_carder[ 1 ].yellows + top_carder[ 1 ].reds )
  rVal.teams = totals
  rVal.teams.avgRank = round( avg_rank, 1 )
  return rVal
