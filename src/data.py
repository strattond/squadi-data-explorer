import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from numpy import ndarray

pattern = re.compile( r" Div \d{1,2} (Sth|Central|Nth) Men" )


def getMatchingConfig( yearOfInterest, config ) -> Any:
  configMatch = None
  for comp in config:
    if comp[ 'organisation' ][ 'yearId' ] == yearOfInterest:
      return comp

  if configMatch is None:
    print( "Please provide a valid configuration year" )
    sys.exit( 1 )


def getPaths( configMatch ):
  outputBase = f"output/{configMatch['organisation']['yearId']}"
  plotBase = f"plots/{configMatch['organisation']['yearId']}"

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
  raise TypeError


def dumpJson( baseFolder, filename, jsonObject ):
  with open( f"{baseFolder}/{filename}", "w", encoding='utf-8' ) as f:
    json.dump( jsonObject, f, indent=2, ensure_ascii=False, default=default )


def loadJson( baseFolder, filename ):
  with open( f"{baseFolder}/{filename}", "r" ) as f:
    return json.load( f )


def getDivByName( divisions, match ):
  for d in divisions:
    if d[ 'div' ][ 'name' ] == match:
      return d
  return None


def maskedSum( arrayOfArrays ) -> ndarray:
  clean = [ np.nan_to_num( a, nan=0.0 ) for a in arrayOfArrays ]
  summed = np.sum( clean, axis=0 )

  mask_all_nan = np.all( [ np.isnan( a ) for a in arrayOfArrays ], axis=0 )
  summed[ mask_all_nan ] = np.nan
  return summed


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

  def get( self, name, maxRounds, divName ):

    rVal = self.stats.get( name )
    if rVal is None:
      rVal = self.stats.setdefault( name, Player( name ) )

    rVal.checkDiv( maxRounds, divName )
    return rVal

  def accumulate( self, maxRounds ):
    for player in self.stats.values():
      player.accumulate( maxRounds )


def playerPlayedInDivision( stats: Player, div ):
  return div in stats.stats and np.any( ~np.isnan( stats.stats[ div ].block.appearances ) )


def getPlayersForDiv( player_stats: PlayerStats, div: str ) -> list[ tuple[ str, Player ] ]:
  divPlayers = { name: player for name, player in player_stats.stats.items() if playerPlayedInDivision( player, div ) }
  return sorted( divPlayers.items(), key=lambda item: ( -np.nansum( item[ 1 ].stats[ div ].block.appearances ), item[ 0 ] ) )
