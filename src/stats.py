import re

import numpy as np


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


def sortedDivisions( data ):
  all_divisions = set()

  for division in data:
    all_divisions.add( division[ "div" ][ 'name' ] )

  return sorted( all_divisions, key=mixedDivKey )


def maxMatches( data ):
  return max( len( d.get( "matches", [] ) ) for d in data )


def accumulateStats( data ):

  player_stats = {}
  maxRounds = maxMatches( data )
  for division in data:
    divName = division[ "div" ][ 'name' ]
    for matchNum, match in enumerate( division.get( "matches", [] ) ):
      for player in match[ "match" ].get( "players", [] ):
        name = player[ "name" ]
        stats = player_stats.setdefault(
            name, {
                "name": name,
                "appearances": 0,
                "goals": 0,
                "yellows": 0,
                "reds": 0,
                "fairPlay": 0,
                "div": {},  # divName -> count,
                "roundGoals": np.full( maxRounds, np.nan ),
                "roundYellows": np.full( maxRounds, np.nan ),
                "roundReds": np.full( maxRounds, np.nan ),
                "roundFairPlay": np.full( maxRounds, np.nan ),
                "starts": 0
            }
        )

        # appearances
        stats[ "appearances" ] += 1
        divStats = stats[ 'div' ].setdefault( divName, makeDivBlock( maxRounds ) )
        divStats[ 'appearances' ] += 1

        # goals/yellows/reds may not exist on this record
        roundGoals = player.get( "goals", 0 )
        roundYellows = player.get( "yellows", 0 )
        roundReds = player.get( "reds", 0 )
        didStart = player.get( "started", False )
        if didStart:
          stats[ "starts" ] += 1
        stats[ "goals" ] += roundGoals
        stats[ "yellows" ] += roundYellows
        stats[ "reds" ] += roundReds
        stats[ "fairPlay" ] += ( roundYellows + 2*roundReds )

        divStats[ 'goals' ][ matchNum ] = roundGoals
        divStats[ 'yellows' ][ matchNum ] = roundYellows
        divStats[ 'reds' ][ matchNum ] = roundReds
        divStats[ 'fairPlay' ][ matchNum ] = roundYellows + 2*roundReds

        stats[ 'roundGoals' ][ matchNum ] = newEntryValue( stats[ 'roundGoals' ][ matchNum ], roundGoals )
        stats[ 'roundYellows' ][ matchNum ] = newEntryValue( stats[ 'roundYellows' ][ matchNum ], roundYellows )
        stats[ 'roundReds' ][ matchNum ] = newEntryValue( stats[ 'roundReds' ][ matchNum ], roundReds )
        stats[ 'roundFairPlay' ][ matchNum ] = newEntryValue( stats[ 'roundFairPlay' ][ matchNum ], roundYellows + 2*roundReds )

  return player_stats


def getInfographicData( player_stats, data ):
  cumRounds = maxMatches( data )
  total_goals = sum( stats[ "goals" ] for stats in player_stats.values() )
  total_yellows = sum( stats[ "yellows" ] for stats in player_stats.values() )
  total_reds = sum( stats[ "reds" ] for stats in player_stats.values() )
  unique_scorers = sum( 1 for stats in player_stats.values() if stats[ "goals" ] > 0 )
  unique_carders = sum( 1 for stats in player_stats.values() if stats[ "fairPlay" ] > 0 )
  avg_goals_per_week = total_goals / cumRounds if cumRounds else 0
  round_totals = [ 0 ] * cumRounds

  for stats in player_stats.values():
    for i, g in enumerate( stats[ "roundGoals" ] ):
      if not np.isnan( g ):
        round_totals[ i ] += g

  highest_round = max( range( cumRounds ), key=lambda i: round_totals[ i ] )
  highest_round_goals = round_totals[ highest_round ]

  top_scorer = max( player_stats.items(), key=lambda item: item[ 1 ][ "goals" ] )
  top_carder = max( player_stats.items(), key=lambda item: item[ 1 ][ "fairPlay" ] )

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
          "name": top_scorer[ 1 ][ 'name' ],
          "goals": top_scorer[ 1 ][ 'goals' ]
      },
      "top_carder": {
          "name": top_carder[ 1 ][ 'name' ],
          "cards": top_carder[ 1 ][ 'yellows' ]
      }
  }
