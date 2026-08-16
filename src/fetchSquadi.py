import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import Browser, Page, Response, sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument( "--match", action="store_true", help="Run in match detail mode" )
parser.add_argument( "--summary", action="store_true", help="Run in division summary mode" )
parser.add_argument( "--div", action="store_true", help="Run in division results mode" )

args = parser.parse_args()

print( "Loading configuration" )
with open( "data/config.json", "r" ) as f:
  config = json.load( f )

print( "Starting our squadi fetch" )

orgSetup = config[ 'organisation' ]
divisions = config[ 'divisions' ]

pattern = re.compile( r" Div \d{1,2} (Sth|Central|Nth) Men" )


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
      'id': match[ 'id' ],
      'startTime': startTime,
      'when': displayTime( localTime( startTime ) ),
      'homeId': match[ 'team1Id' ],
      'home': sanitiseTeam( cleanTeam( match[ 'team1' ][ 'name' ] ) ),
      'goalsHome': match[ "team1Score" ],
      'awayId': match[ 'team2Id' ],
      'away': sanitiseTeam( cleanTeam( match[ 'team2' ][ 'name' ] ) ),
      'goalsAway': match[ "team2Score" ],
      'ground': cleanVenue( cleanTeam( match[ 'team1' ][ 'name' ] ), match[ 'venueCourt' ][ 'venue' ][ 'name' ] + ' ' + match[ 'venueCourt' ][ 'name' ] )
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

  # {
  #     "rounds": [
  #         {
  #             "id": 114519,
  #             "name": "Round 1",
  #             "sequence": 0,
  #             "competitionId": 1287,
  #             "divisionId": 9189,
  #             "matches": [

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
      print( e )

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
  p = Path( "output/divMatchDetails.json" )
  if not p.exists():
    return pushBlankFullDiv( div )
  if not loadedDivMatchDetails:
    with open( 'output/divMatchDetails.json', 'r' ) as f:
      divMatchDetails = json.load( f )
    loadedDivMatchDetails = True

  for i in divMatchDetails:
    if i[ 'div' ][ 'divisionId' ] == div[ 'divisionId' ]:
      return i[ 'rounds' ]

  # If we get to this point, it didn't exist in the cached results, so add a blank one
  return pushBlankFullDiv( div )


def loadExistingDetails( div ):
  global loadedMatchDetails, teamMatchDetails
  p = Path( "output/matchDetails.json" )
  if not p.exists():
    return pushBlankDiv( div )
  if not loadedMatchDetails:
    with open( 'output/matchDetails.json', 'r' ) as f:
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
      except Exception as e:
        print( e )

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
      except Exception as e:
        pass

    page.on( "response", handle_response )

    # Load the page normally
    page.goto( resultsURL )

    # Wait for JS to finish loading
    page.wait_for_load_state( "networkidle" )


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
    if args.div:
      existing = loadFullExistingDetails( div )
      fetchDivNewDetails( div, browser, existing )

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
    json.dump( teamMatchDetails, f, indent=2, ensure_ascii=False, default=default )

if args.div:
  with open( "output/divMatchDetails.json", "w" ) as f:
    json.dump( divMatchDetails, f, indent=2, ensure_ascii=False, default=default )
