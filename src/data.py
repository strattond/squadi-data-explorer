from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
from numpy import ndarray

import blended
import fixed as fx
import shared
import user

pattern = re.compile( r" Div \d{1,2} (Sth|Central|Nth) Men" )


def getMatchingConfig( yearOfInterest: int, config: list[ ConfigEntry ] ) -> ConfigEntry:
  toReturn = next( ( i for i in config if i.organisation.yearId == yearOfInterest ), None )
  if toReturn is not None:
    return toReturn

  print( "Please provide a valid configuration year" )
  sys.exit( 1 )


def getPaths( configMatch: ConfigEntry ):
  outputBase = f"output/{configMatch.organisation.yearId}"
  plotBase = f"plots/{configMatch.organisation.yearId}"

  return ( outputBase, plotBase )


def makeIfMissing( path ):

  folder = Path( path )
  if not folder.exists():
    os.makedirs( folder )


def cleanTeam( team ):
  team = pattern.sub( "", team )
  return team


def sanitiseTeam( team ):
  if team == 'Oxley United':
    return 'Oxley United FC'
  return team


def cleanVenue( homeTeam, venue ):
  rawPattern = f"(.+)\\({homeTeam}.*\\) (.+)"
  pattern = re.compile( rawPattern )
  match = pattern.match( venue )
  if match is not None:
    return match.group( 1 ).rstrip() + ", " + match.group( 2 )
  else:
    return venue


def default( o ):
  if isinstance( o, datetime ):
    return o.isoformat()
  if hasattr( o, "__dataclass_fields__" ):
    return asdict( o )
  raise TypeError


def dumpJson( baseFolder, filename, jsonObject ):
  with open( f"{baseFolder}/{filename}", "w", encoding='utf-8' ) as f:
    json.dump( jsonObject, f, indent=2, ensure_ascii=False, default=default )


def dumpJsonStructured( baseFolder, filename, jsonObject ):
  with open( f"{baseFolder}/{filename}", "w", encoding='utf-8' ) as f:
    json.dump( [ asdict( d ) for d in jsonObject ], f, indent=2, ensure_ascii=False, default=default )


def loadLadder( baseFolder, filename ) -> list[ Ladder ]:
  ladderData = shared.loadJson( baseFolder, filename )
  return [ shared.from_dict( Ladder, d ) for d in ladderData ] if ladderData else []


def loadSquadiDetails( baseFolder, fixedName, userName ) -> SquadiDetails:
  fixedF, fixedD = fx.loadDivisionData( baseFolder, fixedName )
  userF, userD = user.loadDivisionData( baseFolder, userName )
  return SquadiDetails( fixedD, userD, fixedF, userF )


def getDivByName(
    divisions: list[ blended.DivisionData ], match
) -> blended.DivisionData | None:
  if len( divisions ) == 0:
    return None
  return next( ( d for d in divisions if d.div.name == match ), None )


def maskedSum( arrayOfArrays ) -> ndarray:
  clean = [ np.nan_to_num( a, nan=0.0 ) for a in arrayOfArrays ]
  summed = np.sum( clean, axis=0 )

  mask_all_nan = np.all( [ np.isnan( a ) for a in arrayOfArrays ], axis=0 )
  summed[ mask_all_nan ] = np.nan
  return summed


### Competition classes


@dataclass
class SquadiDetails:
  fixedD: fx.SquadiDetails = field( default_factory=fx.SquadiDetails )
  userD: user.SquadiDetails = field( default_factory=user.SquadiDetails )
  fixedFound: bool = False
  userFound: bool = False

@dataclass
class StatBlock:
  appearances: ndarray = field( init=False )
  goals: ndarray = field( init=False )
  yellows: ndarray = field( init=False )
  reds: ndarray = field( init=False )
  fairPlay: ndarray = field( init=False )
  starts: ndarray = field( init=False )

  def initializeFromRounds( self, numRounds ):
    self.appearances = np.full( numRounds, np.nan )
    self.goals = np.full( numRounds, np.nan )
    self.yellows = np.full( numRounds, np.nan )
    self.reds = np.full( numRounds, np.nan )
    self.fairPlay = np.full( numRounds, np.nan )
    self.starts = np.full( numRounds, np.nan )


@dataclass
class PlayerDivision:
  numRounds: int
  block: StatBlock = field( init=False )

  def __post_init__( self ):
    self.block = StatBlock()
    self.block.initializeFromRounds( self.numRounds )

  def calculateFairPlay( self ):
    yellow_pts = np.where( np.isnan( self.block.yellows ), 0.0, 1.0 )
    red_pts = np.where( np.isnan( self.block.reds ), 0.0, 2.0 )
    self.block.fairPlay = yellow_pts + red_pts
    self.block.fairPlay[ ( np.isnan( self.block.yellows ) & np.isnan( self.block.reds ) ) ] = np.nan


@dataclass
class PlayerDivView:
  name: str
  div: str
  stats: StatBlock = field( init=False )
  appearances: int = 0
  goals: int = 0
  yellows: int = 0
  reds: int = 0
  fairPlay: int = 0
  starts: int = 0

  def accumulate( self ):
    self.appearances = int( np.nansum( self.stats.appearances ) )
    self.goals = int( np.nansum( self.stats.goals ) )
    self.yellows = int( np.nansum( self.stats.yellows ) )
    self.reds = int( np.nansum( self.stats.reds ) )
    self.fairPlay = int( np.nansum( self.stats.fairPlay ) )
    self.starts = int( np.nansum( self.stats.starts ) )


@dataclass
class Player:
  name: str
  stats: dict[ str, PlayerDivision ] = field( default_factory=dict )
  roundStats: StatBlock = field( init=False )
  cumStats: StatBlock = field( init=False )
  appearances: int = 0
  goals: int = 0
  yellows: int = 0
  reds: int = 0
  fairPlay: int = 0
  starts: int = 0

  def slice( self, divName ) -> PlayerDivView:
    exDiv = self.stats.get( divName )
    rVal = PlayerDivView( self.name, divName )
    if not exDiv is None:
      rVal.stats = exDiv.block
      rVal.accumulate()
    return rVal

  def checkDiv( self, maxRounds, divName ):
    exDiv = self.stats.get( divName )
    if exDiv is None:
      self.stats[ divName ] = PlayerDivision( maxRounds )

  def accumulate( self, maxRounds ):
    self.roundStats = StatBlock()
    self.roundStats.initializeFromRounds( maxRounds )
    self.cumStats = StatBlock()
    self.cumStats.initializeFromRounds( maxRounds )

    for pd in self.stats.values():
      pd.calculateFairPlay()

    self.roundStats.appearances = maskedSum( [ p.block.appearances for p in self.stats.values() ] )
    self.roundStats.goals = maskedSum( [ p.block.goals for p in self.stats.values() ] )
    self.roundStats.yellows = maskedSum( [ p.block.yellows for p in self.stats.values() ] )
    self.roundStats.reds = maskedSum( [ p.block.reds for p in self.stats.values() ] )
    self.roundStats.fairPlay = maskedSum( [ p.block.fairPlay for p in self.stats.values() ] )
    self.roundStats.starts = maskedSum( [ p.block.starts for p in self.stats.values() ] )

    self.appearances = np.nansum( self.roundStats.appearances )
    self.goals = np.nansum( self.roundStats.goals )
    self.yellows = np.nansum( self.roundStats.yellows )
    self.reds = np.nansum( self.roundStats.reds )
    self.fairPlay = np.nansum( self.roundStats.fairPlay )
    self.starts = np.nansum( self.roundStats.starts )

    self.cumStats.goals = np.nancumsum( self.roundStats.goals )
    self.cumStats.goals[ np.isnan( self.roundStats.goals ) ] = np.nan
    self.cumStats.yellows = np.nancumsum( self.roundStats.yellows )
    self.cumStats.yellows[ np.isnan( self.roundStats.yellows ) ] = np.nan
    self.cumStats.reds = np.nancumsum( self.roundStats.reds )
    self.cumStats.reds[ np.isnan( self.roundStats.reds ) ] = np.nan


@dataclass
class PlayerStats:
  stats: dict[ str, Player ] = field( default_factory=dict )

  def get( self, name: str, maxRounds: int, divName: str ):

    rVal = self.stats.get( name )
    if rVal is None:
      rVal = self.stats.setdefault( name, Player( name ) )

    rVal.checkDiv( maxRounds, divName )
    return rVal

  def accumulate( self, maxRounds ):
    for player in self.stats.values():
      player.accumulate( maxRounds )


@dataclass
class TopStat:
  name: str = ""
  value: int = 0


@dataclass
class TeamStats:
  wins: int = 0
  draws: int = 0
  losses: int = 0
  gf: int = 0
  ga: int = 0
  avgRank: float = 0.0

  def __sub__( self, other ):
    if not isinstance( other, TeamStats ):
      return NotImplemented
    rVal = TeamStats()
    rVal.wins = self.wins - other.wins
    rVal.draws = self.draws - other.draws
    rVal.losses = self.losses - other.losses
    rVal.gf = self.gf - other.gf
    rVal.ga = self.ga - other.ga
    rVal.avgRank = round( self.avgRank - other.avgRank, 1 )
    return rVal

  def add( self, other: LadderEntry ):  # Mutate in place
    self.wins += other.GamesWon
    self.draws += other.GamesDrawn
    self.losses += other.GamesLost
    self.gf += other.GoalsFor
    self.ga += other.GoalsAgainst
    self.avgRank += other.Rank


@dataclass
class InfoStats:
  players: int = 0
  newPlayers: int = 0
  lostPlayers: int = 0
  goals: int = 0
  yellows: int = 0
  reds: int = 0
  uniqueScorers: int = 0
  uniqueCarders: int = 0
  avgGoalsPerRound: float = 0
  highestRound: int = 0
  highestRoundGoals: int = 0
  numRounds: int = 0
  top_scorer: TopStat = field( default_factory=TopStat )
  top_carder: TopStat = field( default_factory=TopStat )
  teams: TeamStats = field( default_factory=TeamStats )

  def __sub__( self, other ):
    if not isinstance( other, InfoStats ):
      return NotImplemented
    rVal = InfoStats()
    rVal.players = self.players - other.players
    rVal.goals = self.goals - other.goals
    rVal.yellows = self.yellows - other.yellows
    rVal.reds = self.reds - other.reds
    rVal.uniqueScorers = self.uniqueScorers - other.uniqueScorers
    rVal.uniqueCarders = self.uniqueCarders - other.uniqueCarders
    rVal.avgGoalsPerRound = round( self.avgGoalsPerRound - other.avgGoalsPerRound, 2 )
    rVal.highestRoundGoals = self.highestRoundGoals - other.highestRoundGoals
    rVal.numRounds = self.numRounds - other.numRounds
    rVal.top_scorer.value = int( self.top_scorer.value - other.top_scorer.value )
    rVal.top_carder.value = int( self.top_carder.value - other.top_carder.value )
    rVal.teams = self.teams - other.teams
    return rVal


### Ladder stuff


@dataclass
class LadderEntry:
  teamId: int
  Rank: int
  Team: str
  GamesPlayed: int
  GamesWon: int
  GamesDrawn: int
  GamesLost: int
  GoalsFor: int
  GoalsAgainst: int
  Points: int
  GoalsDiff: int
  WinLoss: str


@dataclass
class Ladder:
  div: shared.Division
  table: list[ LadderEntry ] = field( default_factory=list )


### Results stuff


@dataclass
class HighLevelFixture:
  id: int
  startTime: str
  when: str
  homeId: int
  home: str
  goalsHome: int
  awayId: int
  away: str
  goalsAway: int
  ground: str


@dataclass
class FixtureRound:
  name: str
  id: int
  sequence: int


@dataclass
class HighLevelDivisionFixture:
  div: shared.Division
  match: HighLevelFixture


@dataclass
class HighLevelRoundFixtures:
  round: FixtureRound
  matches: list[ HighLevelFixture ] = field( default_factory=list )


@dataclass
class DivisionResults:
  div: shared.Division
  rounds: list[ HighLevelRoundFixtures ] = field( default_factory=list )


### Config stuff


@dataclass
class Organisation:
  yearId: int
  organisationKey: str
  competitionUniqueKey: str


@dataclass
class ConfigEntry:
  organisation: Organisation
  divisions: list[ shared.Division ] = field( default_factory=list )


def playerPlayedInDivision( stats: Player, div ):
  return div in stats.stats and np.any( ~np.isnan( stats.stats[ div ].block.appearances ) )


def getPlayersForDiv( player_stats: PlayerStats, div: str ) -> list[ tuple[ str, Player ] ]:
  divPlayers = { name: player for name, player in player_stats.stats.items() if playerPlayedInDivision( player, div ) }
  return sorted( divPlayers.items(), key=lambda item: ( -np.nansum( item[ 1 ].stats[ div ].block.appearances ), item[ 0 ] ) )
