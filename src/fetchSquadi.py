from datetime import datetime, timezone, timedelta
import re
import json

from playwright.sync_api import Page, sync_playwright

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


def processLadderData( div, ladders, json ):

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


def createMatch( match, startTime ):
  return {
      'id': match[ 'id' ],
      'startTime': startTime,
      'homeId': match[ 'team1Id' ],
      'home': cleanTeam( match[ 'team1' ][ 'name' ] ),
      'goalsHome': match[ "team1Score" ],
      'awayId': match[ 'team2Id' ],
      'away': cleanTeam( match[ 'team2' ][ 'name' ] ),
      'goalsAway': match[ "team2Score" ],
      'ground': (match[ 'venueCourt' ][ 'venue' ]['name'] + ' ' + match[ 'venueCourt' ][ 'name' ])
  }


def processResultsData( div, results, json ):
  global nexts, recents, now

  rounds = []
  for round in json[ 'rounds' ]:
    matches = []
    for match in round[ 'matches' ]:
      if match[ "team1Id" ] == div[ 'teamId' ] or match[ 'team2Id' ] == div[ 'teamId' ]:

        startTime = parseDateTime( match[ 'startTime' ] )
        if match[ 'matchStatus' ] == 'ENDED':
          # It's a match for our team, so let's store the result
          matches.append( createMatch( match, startTime ) )
          
          if (now - startTime ) <= timedelta( days=7 ):
            recents.append( { 'div': div, 'match': createMatch( match, startTime )} )

        if match[ 'matchStatus' ] is None and ( startTime - now ) <= timedelta( days=7 ):
          nexts.append( { 'div': div, 'match': createMatch( match, startTime )} )

    if len( matches ) > 0:
      rounds.append( { 'round': round[ 'name' ], 'matches': matches} )
  results.append( { 'div': div, 'rounds': rounds} )


def fetchDivisionLadderAndResults( div, ladders, results, p ):
  # Capture the API response you care about
  ladderURL = f"{ladderRoot()}&divisionId={div['divisionId']}"

  def handle_response( response ):
    try:
      json = response.json()
      #print( "API URL:", response.url )
      apis.add( response.url )
      #writeFile( json, response.url )
      if '/livescores/round/matches' in response.url:
        processResultsData( div, results, json )
      if '/livescores/teams/ladder/v2' in response.url:
        processLadderData( div, ladders, json )
    except:
      pass
      #print( "Non-JSON response" )

  page.on( "response", handle_response )

  # Load the page normally
  page.goto( ladderURL )

  # Wait for JS to finish loading
  page.wait_for_load_state( "networkidle" )


with sync_playwright() as p:
  browser = p.chromium.launch( headless=True )
  page = browser.new_page()

  for div in divisions:
    print( "Processing", div[ "name" ] )
    fetchDivisionLadderAndResults( div, ladders, results, p )

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
