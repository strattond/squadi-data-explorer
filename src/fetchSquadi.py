import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import Browser, Page, Response, sync_playwright

from data import cleanTeam, cleanVenue, dumpJson, getMatchingConfig, getPaths, loadJson, makeIfMissing, sanitiseTeam

parser = argparse.ArgumentParser(
    prog="Squadi Parser", description="Parses data from squadi into JSON format for further processing"
)
parser.add_argument( "--match", action="store_true", help="Run in match detail mode" )
parser.add_argument( "--summary", action="store_true", help="Run in division summary mode" )
parser.add_argument( "--div", action="store_true", help="Run in division results mode" )
parser.add_argument( "--year", help="The competition year of interest", type=int )

args = parser.parse_args()

print( "Loading configuration" )
with open( "data/config.json", "r" ) as f:
  config = json.load( f )

print( f"Starting our squadi fetch for year {args.year}" )

configMatch = getMatchingConfig( args.year, config )
outputBase, _ = getPaths( configMatch )

makeIfMissing( outputBase )

orgSetup = configMatch[ 'organisation' ]
divisions = configMatch[ 'divisions' ]

pattern = re.compile( r" Div \d{1,2} (Sth|Central|Nth) Men" )


def ladderRoot():
  return f"https://registration.squadi.com/livescorePublicLadder?yearId={orgSetup['yearId']}&organisationKey={orgSetup['organisationKey']}&competitionUniqueKey={orgSetup['competitionUniqueKey']}"


def teamFixtureRoot():
  return f"https://registration.squadi.com/liveScoreSeasonFixture?yearId={orgSetup['yearId']}&organisationKey={orgSetup['organisationKey']}&competitionUniqueKey={orgSetup['competitionUniqueKey']}"


def matchRoot():
  # https://registration.squadi.com/matchSummary?matchId=797102&competitionUniqueKey=ed9f3608-81fb-4c60-82b5-7c1ab2149180
  return f"https://registration.squadi.com/matchSummary?competitionUniqueKey={orgSetup['competitionUniqueKey']}"


ladders = []
results = []
teamMatchDetails = []
divMatchDetails = []
loadedMatchDetails = False
loadedDivMatchDetails = False
nexts = []
recents = []
now = datetime.now( timezone.utc )
fileNum = 0
anyFetched = False


def writeFile( jsonData, url ):
  global fileNum
  filename = f"{outputBase}/f{fileNum}.json"
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

  print( "Processing ladder for", div[ 'name' ] )
  table = []
  for team in json[ 'ladders' ]:
    table.append( {
        'teamId': team[ 'id' ],
        'Rank': int( team[ 'rk' ] ),
        'Team': sanitiseTeam( cleanTeam( team[ 'name' ] ) ),
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


def noDelimTime( dtLocal ):
  return dtLocal.strftime( "%Y%m%d%H%M" )


def createMatch( match, startTime ):
  return {
      'id':
          match[ 'id' ],
      'startTime':
          startTime,
      'when':
          displayTime( localTime( startTime ) ),
      'homeId':
          match[ 'team1Id' ],
      'home':
          sanitiseTeam( cleanTeam( match[ 'team1' ][ 'name' ] ) ),
      'goalsHome':
          match[ "team1Score" ],
      'awayId':
          match[ 'team2Id' ],
      'away':
          sanitiseTeam( cleanTeam( match[ 'team2' ][ 'name' ] ) ),
      'goalsAway':
          match[ "team2Score" ],
      'ground':
          cleanVenue(
              cleanTeam( match[ 'team1' ][ 'name' ] ),
              match[ 'venueCourt' ][ 'venue' ][ 'name' ] + ' ' + match[ 'venueCourt' ][ 'name' ]
          )
  }


def processResultsData( div, json ):

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


def getMatchingRound( round, existing ):
  global anyFetched

  rid = round[ 'id' ]
  for exRound in existing:
    if exRound[ 'id' ] == rid:
      return exRound

  added = { "id": rid, "name": round[ 'name' ], "matches": []}
  print( f" .. Creating round {round['name']}" )
  existing.append( added )
  anyFetched = True
  return added


def getMatchingMatch( match, existing ):
  rid = match[ 'id' ]
  for exMatch in existing:
    if exMatch[ 'id' ] == rid:
      return exMatch

  return None


def processFullResultsData( div, json, existing ):
  global anyFetched

  for fetchedRound in json[ 'rounds' ]:
    matchingRound = getMatchingRound( fetchedRound, existing )
    for fetchedMatch in fetchedRound[ 'matches' ]:
      if fetchedMatch[ 'matchStatus' ] == 'ENDED':
        matchingMatch = getMatchingMatch( fetchedMatch, matchingRound[ 'matches' ] )
        if matchingMatch is None:

          startTime = parseDateTime( fetchedMatch[ 'startTime' ] )
          # It's a match for our team, so let's store the result
          matchingRound[ 'matches' ].append( createMatch( fetchedMatch, startTime ) )
          anyFetched = True
          print( f"   .. Adding {fetchedMatch['id']}" )


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
    except Exception:
      pass

  page.on( "response", handle_response )

  # Load the page normally
  page.goto( ladderURL )

  # Wait for JS to finish loading
  page.wait_for_load_state( "networkidle" )


def pushBlankDiv( div ):
  global anyFetched
  added = { "div": div, "matches": []}
  teamMatchDetails.append( added )
  anyFetched = True
  return added[ 'matches' ]


def pushBlankFullDiv( div ):
  global anyFetched
  added = { "div": div, "rounds": []}
  divMatchDetails.append( added )
  anyFetched = True
  return added[ 'rounds' ]


def loadFullExistingDetails( div ):
  global divMatchDetails, loadedDivMatchDetails
  p = Path( f"{outputBase}/divMatchDetails.json" )
  if not p.exists():
    return pushBlankFullDiv( div )
  if not loadedDivMatchDetails:
    with open( f"{outputBase}/divMatchDetails.json", 'r' ) as f:
      divMatchDetails = json.load( f )
    loadedDivMatchDetails = True

  for i in divMatchDetails:
    if i[ 'div' ][ 'divisionId' ] == div[ 'divisionId' ]:
      return i[ 'rounds' ]

  # If we get to this point, it didn't exist in the cached results, so add a blank one
  return pushBlankFullDiv( div )


def loadExistingDetails( div ):
  global loadedMatchDetails, teamMatchDetails
  p = Path( f"{outputBase}/matchDetails.json" )
  if not p.exists():
    return pushBlankDiv( div )
  if not loadedMatchDetails:
    with open( f"{outputBase}/matchDetails.json", 'r' ) as f:
      teamMatchDetails = json.load( f )
    loadedMatchDetails = True

  for i in teamMatchDetails:
    if i[ 'div' ][ 'divisionId' ] == div[ 'divisionId' ]:
      return i[ 'matches' ]

  # If we get to this point, it didn't exist in the cached results, so add a blank one
  return pushBlankDiv( div )


def getDivResults( div ):
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
    if 'Yellow' in card[ 'iconName' ]:
      yellows += card[ 'count' ]
    else:
      reds += card[ 'count' ]

  return ( yellows, reds )


def processFetchedMatchDetails( div, matchId, teamOfInterest, existing, json ):
  global anyFetched
  toAdd = { "match": { 'id': matchId, 'players': []}}
  for player in json[ 'playing' ]:
    if player[ 'teamId' ] == teamOfInterest:
      # Got a player to add!
      yellows, reds = calculateCards( player[ 'cards' ] )
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
      except Exception:
        pass

    page.on( "response", handle_response )

    # Load the page normally
    page.goto( matchURL )

    # Wait for JS to finish loading
    page.wait_for_load_state( "networkidle" )


def fetchNewDetails( div, browser: Browser, existing ):
  global anyFetched
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
          # But let's check ...
          if 'date' not in eligible[ 'match' ]:
            # Copy the date!
            eligible[ 'match' ][ 'date' ] = noDelimTime( localTime( parseDateTime( m[ 'startTime' ] ) ) )
            anyFetched = True
          break

      if alreadyDone:
        continue

      print( " .. Fetching match details" )
      fetchMatchDetails( div, matchId, teamOfInterest, existing, browser )


def fetchDivNewDetails( div, browser: Browser, existing ):
  # So, we only care about results, and results -we don't already have-
  resultsURL = f"{teamFixtureRoot()}&divisionId={div['divisionId']}"

  with browser.new_page() as page:

    def handle_response( response: Response ) -> None:
      try:
        json = response.json()
        # https://api.squadi.com/livescores/round/matches?competitionId=1287&divisionId=9189&teamIds=&ignoreStatuses=[1]
        if '/livescores/round/matches' in response.url:
          processFullResultsData( div, json, existing )
      except Exception:
        pass

    page.on( "response", handle_response )

    # Load the page normally
    page.goto( resultsURL )

    # Wait for JS to finish loading
    page.wait_for_load_state( "networkidle" )


if args.match:
  print( "Loading existing data" )
  ladders = loadJson( outputBase, 'ladder.json' )
  results = loadJson( outputBase, 'results.json' )
  nexts = loadJson( outputBase, 'next.json' )
  recents = loadJson( outputBase, 'recent.json' )

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
    if args.div:
      existing = loadFullExistingDetails( div )
      fetchDivNewDetails( div, browser, existing )

  browser.close()

if args.summary:
  dumpJson( outputBase, 'ladder.json', ladders )
  dumpJson( outputBase, 'results.json', results )
  dumpJson( outputBase, 'next.json', nexts )
  dumpJson( outputBase, 'recent.json', recents )

if args.match and anyFetched:
  dumpJson( outputBase, 'matchDetails.json', teamMatchDetails )

if args.div:
  dumpJson( outputBase, 'divMatchDetails.json', divMatchDetails )
