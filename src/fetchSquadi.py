from datetime import datetime, timezone, timedelta
from pathlib import Path
import re
import json
import argparse

from playwright.sync_api import Page, Playwright, Response, sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument( "--match", action="store_true", help="Run in match detail mode" )

args = parser.parse_args()

print( "Loading configuration" )
with open( "data/config.json", "r" ) as f:
  config = json.load( f )

print( "Starting our squadi fetch" )

orgSetup = config[ 'organisation' ]
divisions = config[ 'divisions' ]

pattern = re.compile( r" Div \d{1,2} (Sth|Central|Nth) Men" )


def cleanTeam( team ):
  global pattern
  team = pattern.sub( "", team )
  if team == 'Oxley United':
    team = 'Oxley United FC'
  return team


def ladderRoot():
  return f"https://registration.squadi.com/livescorePublicLadder?yearId={orgSetup['yearId']}&organisationKey={orgSetup['organisationKey']}&competitionUniqueKey={orgSetup['competitionUniqueKey']}"


def teamFixtureRoot():
  return f"https://registration.squadi.com/liveScoreSeasonFixture?yearId={orgSetup['yearId']}&organisationKey={orgSetup['organisationKey']}&competitionUniqueKey={orgSetup['competitionUniqueKey']}"


def matchRoot():
  # https://registration.squadi.com/matchSummary?matchId=797102&competitionUniqueKey=ed9f3608-81fb-4c60-82b5-7c1ab2149180
  return f"https://registration.squadi.com/matchSummary?competitionUniqueKey={orgSetup['competitionUniqueKey']}"


ladders = []
results = []
matchDetails = []
loadedMatchDetails = False
nexts = []
recents = []
now = datetime.now( timezone.utc )
apis = set()
fileNum = 0


def writeFile( jsonData, url ):
  global fileNum
  filename = f"output/f{fileNum}.json"
  print( f"Saving JSON to {filename}" )
  with open( filename, "w" ) as f:
    json.dump( { "url": url, "data": jsonData}, f, indent=2, ensure_ascii=False )

  fileNum += 1


def calculateWinLoss( json, teamId ):
  for team in json[ 'lastResults' ]:
    if team[ 'teamId' ] == teamId:
      result = ""
      for last in team[ 'last5' ]:
        result += ( last[ 'code' ][ 0 ] if last[ 'code' ] else '-' )
      return result
  return '-----'


def processLadderData( div, json ):
  global ladders

  print( "Processing ladder for", div[ 'name' ] )
  table = []
  for team in json[ 'ladders' ]:
    table.append( {
        'teamId': team[ 'id' ],
        'Rank': int( team[ 'rk' ] ),
        'Team': cleanTeam( team[ 'name' ] ),
        'GamesPlayed': int( team[ 'P' ] ),
        'GamesWon': int( team[ 'W' ] ),
        'GamesDrawn': int( team[ 'D' ] ),
        'GamesLost': int( team[ 'L' ] ),
        'GoalsFor': int( team[ 'F' ] ),
        'GoalsAgainst': int( team[ 'A' ] ),
        'Points': int( team[ 'PTS' ] ),
        'GoalsDiff': int( team[ 'goalDifference' ] ),
        'WinLoss': calculateWinLoss( json, team[ 'id' ] )
    } )
  ladders.append( { 'div': div, 'table': table} )


def parseDateTime( stringValue ):
  return datetime.fromisoformat( stringValue.replace( "Z", "+00:00" ) )


def localTime( dtUTC ):
  return dtUTC.astimezone( timezone( timedelta( hours=10 ) ) )


def displayTime( dtLocal ):
  return dtLocal.strftime( "%a, %b %d %I:%M %p" )


def createMatch( match, startTime ):
  return {
      'id': match[ 'id' ],
      'startTime': startTime,
      'when': displayTime( localTime( startTime ) ),
      'homeId': match[ 'team1Id' ],
      'home': cleanTeam( match[ 'team1' ][ 'name' ] ),
      'goalsHome': match[ "team1Score" ],
      'awayId': match[ 'team2Id' ],
      'away': cleanTeam( match[ 'team2' ][ 'name' ] ),
      'goalsAway': match[ "team2Score" ],
      'ground': ( match[ 'venueCourt' ][ 'venue' ][ 'name' ] + ' ' + match[ 'venueCourt' ][ 'name' ] )
  }


def processResultsData( div, json ):
  global nexts, results, recents, now

  rounds = []
  for round in json[ 'rounds' ]:
    matches = []
    for match in round[ 'matches' ]:
      if match[ "team1Id" ] == div[ 'teamId' ] or match[ 'team2Id' ] == div[ 'teamId' ]:

        startTime = parseDateTime( match[ 'startTime' ] )
        # print( match[ 'id' ], startTime, now, match['matchStatus' ], (startTime > now), (now - startTime), (startTime < now), (startTime - now) )
        #      866118 2026-06-05 09:30:00+00:00 2026-06-10 08:54:15.206473+00:00 None False 4 days, 23:24:15.206473 True -5 days, 0:35:44.793527
        if match[ 'matchStatus' ] == 'ENDED':
          # It's a match for our team, so let's store the result
          matches.append( createMatch( match, startTime ) )

          if startTime < now and ( now - startTime ) <= timedelta( days=7 ):
            recents.append( { 'div': div, 'match': createMatch( match, startTime )} )

        if match[ 'matchStatus' ] is None and startTime > now and ( startTime - now ) <= timedelta( days=7 ):
          nexts.append( { 'div': div, 'match': createMatch( match, startTime )} )

    if len( matches ) > 0:
      rounds.append( { 'round': round[ 'name' ], 'matches': matches} )
  results.append( { 'div': div, 'rounds': rounds} )


def fetchDivisionLadderAndResults( div, page: Page ):
  # Capture the API response you care about
  ladderURL = f"{ladderRoot()}&divisionId={div['divisionId']}"

  def handle_response( response: Response ) -> None:
    try:
      json = response.json()
      if '/livescores/round/matches' in response.url:
        processResultsData( div, json )
      if '/livescores/teams/ladder/v2' in response.url:
        processLadderData( div, json )
    except Exception as e:
      #print( f"How exceptional {e} type {type(e)}" )
      pass
      #print( "Non-JSON response" )

  page.on( "response", handle_response )

  # Load the page normally
  page.goto( ladderURL )

  # Wait for JS to finish loading
  page.wait_for_load_state( "networkidle" )

  page.close()

def pushBlankDiv( div ):
  global matchDetails
  added = { "div": div, "details": [] }
  matchDetails.append( added )
  return added['details']  

def loadExistingDetails( div ):
  global loadedMatchDetails, matchDetails
  p = Path( "output/matchDetails.json" )
  if not p.exists():
    return pushBlankDiv( div )
  if not loadedMatchDetails:
    with open( 'output/matchDetails.json', 'r' ) as f:
      matchDetails = json.load( f )
    loadedMatchDetails = True

  for i in matchDetails:
    if i['div']['divisionId'] == div['divisionId']:
      return i['details']

  # If we get to this point, it didn't exist in the cached results, so add a blank one
  return pushBlankDiv( div )

def getDivResults( div ):
  global results
  for i in results:
    if i['div']['divisionId'] == div['divisionId']:
      return i

  return None
  

def fetchNewDetails( div, p: Playwright, existing ):
  global results
  # So, we only care about results, and results -we don't already have-
  divResults = getDivResults( div )
  teamOfInterest = div['teamId']
  if divResults is None:
    return

  # These are the divisional results we need answers for
  for round in divResults['rounds' ]:
    for m in round['matches']:
      matchId = m['id']

      # Firstly, let's see if we've fetched it - if we have, no need to process it!
      
      page = browser.new_page()
      pass
      
with sync_playwright() as p:
  browser = p.chromium.launch( headless=True )

  for div in divisions:
    print( "Processing", div[ "name" ] )
    page = browser.new_page()
    fetchDivisionLadderAndResults( div, page )
    if args.match:
      existing = loadExistingDetails( div )
      fetchNewDetails( div, p, existing )

  browser.close()

for uri in sorted( apis ):
  print( uri )


def default( o ):
  if isinstance( o, datetime ):
    return o.isoformat()
  raise TypeError


with open( "output/ladder.json", "w" ) as f:
  json.dump( ladders, f, indent=2, ensure_ascii=False )

with open( "output/results.json", "w" ) as f:
  json.dump( results, f, indent=2, ensure_ascii=False, default=default )

with open( "output/next.json", "w" ) as f:
  json.dump( nexts, f, indent=2, ensure_ascii=False, default=default )

with open( "output/recent.json", "w" ) as f:
  json.dump( recents, f, indent=2, ensure_ascii=False, default=default )

if args.match:
  with open( "output/matchDetails.json", "w" ) as f:
    json.dump( matchDetails, f, indent=2, ensure_ascii=False, default=default )
