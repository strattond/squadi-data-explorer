import re

import numpy as np

from data import Player, PlayerStats, getDivByName


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


def uniquePlayers( data ):
  unique_players = set()

  for division in data:
    for match in division.get( "matches", [] ):
      for player in match[ "match" ].get( "players", [] ):
        unique_players.add( player[ "name" ] )

  return sorted( unique_players )


def sortedDivisions( data ) -> list[ str ]:
  all_divisions = set()

  for division in data:
    all_divisions.add( division[ "div" ][ 'name' ] )

  return sorted( all_divisions, key=mixedDivKey )


def maxMatches( data ):
  return max( len( d.get( "matches", [] ) ) for d in data )


def accumulateStats( data ) -> PlayerStats:

  player_stats = PlayerStats()
  maxRounds = maxMatches( data )
  for division in data:
    divName = division[ "div" ][ 'name' ]
    for matchNum, match in enumerate( division.get( "matches", [] ) ):
      for player in match[ "match" ].get( "players", [] ):
        name = player[ "name" ]
        stats = player_stats.get( name, maxRounds, divName )

        # appearances
        divStats = stats.stats[ divName ]
        divStats.block.appearances[ matchNum ] = 1

        # goals/yellows/reds may not exist on this record
        divStats.block.goals[ matchNum ] = player.get( "goals", 0 )
        divStats.block.yellows[ matchNum ] = player.get( "yellows", 0 )
        divStats.block.reds[ matchNum ] = player.get( "reds", 0 )
        divStats.block.starts[ matchNum ] = player.get( "started", 0 )

  player_stats.accumulate( maxRounds )
  return player_stats


def list_to_dict( listData: list[ tuple[ str, Player ] ] ) -> dict[ str, Player ]:
  rVal = {}
  for i in listData:
    rVal[ i[ 0 ] ] = i[ 1 ]
  return rVal


def getTeamInfographicData( player_stats: list[ tuple[ str, Player ] ], data, div: str ):

  divDetail = getDivByName( data, div )
  if divDetail is None:
    return
  divPlayers = list_to_dict( player_stats )

  # Time to Slice and Dice
  sliced = [ player.slice( div ) for player in divPlayers.values() ]

  cumRounds = len( divDetail[ 'matches' ] )  # maxMatches( data )
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

  for player in sliced:
    print( f"{player.name:<32} {player.goals} {player.yellows} {player.reds}" )

  return {
      "goals": total_goals,
      "yellows": total_yellows,
      "reds": total_reds,
      "uniqueScorers": unique_scorers,
      "uniqueCarders": unique_carders,
      "avgGoalsPerRound": round( avg_goals_per_week, 2 ),
      "highestRound": highest_round + 1,
      "highestRoundGoals": int( highest_round_goals ),
      "numRounds": cumRounds,
      "top_scorer": {
          "name": top_scorer.name,
          "goals": top_scorer.goals
      },
      "top_carder": {
          "name": top_carder.name,
          "cards": top_carder.yellows
      }
  }


def getInfographicData( player_stats: PlayerStats, data ):

  cumRounds = maxMatches( data )
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

  return {
      "goals": total_goals,
      "yellows": total_yellows,
      "reds": total_reds,
      "uniqueScorers": unique_scorers,
      "uniqueCarders": unique_carders,
      "avgGoalsPerRound": round( avg_goals_per_week, 2 ),
      "highestRound": highest_round,
      "highestRoundGoals": int( highest_round_goals ),
      "numRounds": cumRounds,
      "top_scorer": {
          "name": top_scorer[ 1 ].name,
          "goals": int( top_scorer[ 1 ].goals )
      },
      "top_carder": {
          "name": top_carder[ 1 ].name,
          "cards": int( top_carder[ 1 ].yellows )
      }
  }
