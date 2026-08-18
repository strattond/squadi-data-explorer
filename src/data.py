import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

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
  with open( f"{baseFolder}/{filename}", "w" ) as f:
    json.dump( jsonObject, f, indent=2, ensure_ascii=False, default=default )

def loadJson( baseFolder, filename ):
  with open( f"{baseFolder}/{filename}", "r" ) as f:
    return json.load( f )
