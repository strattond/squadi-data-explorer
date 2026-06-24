from datetime import datetime, timezone, timedelta
from pathlib import Path
import re
import json
import argparse

from playwright.sync_api import Browser, Page, Playwright, Response, sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument( "--match", action="store_true", help="Run in match detail mode" )
parser.add_argument( "--summary", action="store_true", help="Run in division summary mode" )

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
fileNum = 0
anyFetched = False


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
      pass

  page.on( "response", handle_response )

  # Load the page normally
  page.goto( ladderURL )

  # Wait for JS to finish loading
  page.wait_for_load_state( "networkidle" )


def pushBlankDiv( div ):
  global matchDetails, anyFetched
  added = { "div": div, "matches": []}
  matchDetails.append( added )
  anyFetched = True
  return added[ 'matches' ]


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
    if i[ 'div' ][ 'divisionId' ] == div[ 'divisionId' ]:
      return i[ 'matches' ]

  # If we get to this point, it didn't exist in the cached results, so add a blank one
  return pushBlankDiv( div )


def getDivResults( div ):
  global results
  for i in results:
    if i[ 'div' ][ 'divisionId' ] == div[ 'divisionId' ]:
      return i

  return None

def calculateCards( cards ):
  if len( cards ) == 0:
    return ( 0, 0 )

  yellows = 0
  reds = 0
# { "type": "Y1", "iconName": "YellowCard.png",    "value": 1, "count": 1 },
# { "type": "R7", "iconName": "YellowRedCard.png", "value": 1, "count": 1 }
  for card in cards:
    if 'Yellow' in card['iconName']:
      yellows += card['count']
    else:
      reds += card['count']
    
  return (yellows, reds)


def processFetchedMatchDetails( div, matchId, teamOfInterest, existing, json ):
  global anyFetched
  toAdd = { "match": { 'id': matchId, 'players': []}}
  for player in json[ 'playing' ]:
    if player[ 'teamId' ] == teamOfInterest:
      # Got a player to add!
      yellows, reds = calculateCards( player['cards'] )
      newPlayer = {
          "shirt": int( player[ 'shirt' ] ),
          "name": player[ 'firstName' ] + " " + player[ 'lastName' ],
          "goals": player[ 'goals' ][ 0 ][ 'count' ] if len( player[ 'goals' ] ) > 0 else 0,
          "yellows": yellows,
          "reds": reds,
          "started": False
      }
      toAdd[ 'match' ][ 'players' ].append( newPlayer )

  existing.append( toAdd )
  anyFetched = True

def fetchMatchDetails( div, matchId, teamOfInterest, existing, browser: Browser ):
  with browser.new_page() as page:
    matchURL = f"{matchRoot()}&matchId={str(matchId)}"

    def handle_response( response: Response ) -> None:
      try:
        json = response.json()
        if '/gameSummary' in response.url:
          processFetchedMatchDetails( div, matchId, teamOfInterest, existing, json )
      except Exception as e:
        pass

    page.on( "response", handle_response )

    # Load the page normally
    page.goto( matchURL )

    # Wait for JS to finish loading
    page.wait_for_load_state( "networkidle" )


def fetchNewDetails( div, browser: Browser, existing ):
  global results
  # So, we only care about results, and results -we don't already have-
  divResults = getDivResults( div )
  teamOfInterest = div[ 'teamId' ]
  if divResults is None:
    return

  # These are the divisional results we need answers for
  for round in divResults[ 'rounds' ]:
    for m in round[ 'matches' ]:

      matchId = m[ 'id' ]
      print( ' ..', round[ 'round' ].ljust( 10 ), "Match", str( matchId ), end='' )

      # Firstly, let's see if we've fetched it - if we have, no need to process it!
      alreadyDone = False
      for eligible in existing:
        if int( eligible[ 'match' ][ 'id' ] ) == matchId:
          print( " .. Matched!" )
          alreadyDone = True
          break

      if alreadyDone:
        continue

      print( " .. Fetching match details" )
      fetchMatchDetails( div, matchId, teamOfInterest, existing, browser )


if args.match:
  print( "Loading existing data" )
  with open( "output/ladder.json", "r" ) as f:
    ladders = json.load( f )

  with open( "output/results.json", "r" ) as f:
    results = json.load( f )

  with open( "output/next.json", "r" ) as f:
    nexts = json.load( f )

  with open( "output/recent.json", "r" ) as f:
    recents = json.load( f )

with sync_playwright() as p:
  browser = p.chromium.launch( headless=True )

  for div in divisions:
    print( "Processing", div[ "name" ] )
    if args.summary:
      with browser.new_page() as page:
        fetchDivisionLadderAndResults( div, page )
    if args.match:
      existing = loadExistingDetails( div )
      fetchNewDetails( div, browser, existing )

  browser.close()


def default( o ):
  if isinstance( o, datetime ):
    return o.isoformat()
  raise TypeError


if args.summary:
  with open( "output/ladder.json", "w" ) as f:
    json.dump( ladders, f, indent=2, ensure_ascii=False )

  with open( "output/results.json", "w" ) as f:
    json.dump( results, f, indent=2, ensure_ascii=False, default=default )

  with open( "output/next.json", "w" ) as f:
    json.dump( nexts, f, indent=2, ensure_ascii=False, default=default )

  with open( "output/recent.json", "w" ) as f:
    json.dump( recents, f, indent=2, ensure_ascii=False, default=default )

if args.match and anyFetched:
  with open( "output/matchDetails.json", "w" ) as f:
    json.dump( matchDetails, f, indent=2, ensure_ascii=False, default=default )
