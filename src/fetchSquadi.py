import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import Browser, Page, Response, sync_playwright
from tqdm import tqdm

import data
import shared
from fixed import DivisionData, Fixture, FixtureWrapper, Player, SquadiDetails

parser = argparse.ArgumentParser(
    prog="Squadi Parser", description="Parses data from squadi into JSON format for further processing"
)
parser.add_argument( "--match", action="store_true", help="Run in match detail mode" )
parser.add_argument( "--summary", action="store_true", help="Run in division summary mode" )
parser.add_argument( "--div", action="store_true", help="Run in division results mode" )
parser.add_argument( "--year", help="The competition year of interest", type=int )
parser.add_argument( "--recent", help="The number of days considered recent", type=int, default=7 )
parser.add_argument( "--next", help="The number of days in the future we want to get details", type=int, default=7 )

args = parser.parse_args()

if not args.match and not args.summary:
  print( "Fetching must be at summary or match level" )
  sys.exit( 1 )

print( "Loading configuration" )
config: list[ data.ConfigEntry ] = []
with open( "data/config.json", "r" ) as f:
  configData = json.load( f )
  config = [ shared.from_dict( data.ConfigEntry, d ) for d in configData ] if configData else []

print( f"Starting our squadi fetch for year {args.year}" )

configMatch = data.getMatchingConfig( args.year, config )
outputBase, _ = data.getPaths( configMatch )

data.makeIfMissing( outputBase )

orgSetup = configMatch.organisation
divisions = configMatch.divisions

pattern = re.compile( r" Div \d{1,2} (Sth|Central|Nth) Men" )


def ladderRoot():
  return f"https://registration.squadi.com/livescorePublicLadder?yearId={orgSetup.yearId}&organisationKey={orgSetup.organisationKey}&competitionUniqueKey={orgSetup.competitionUniqueKey}"


def teamFixtureRoot():
  return f"https://registration.squadi.com/liveScoreSeasonFixture?yearId={orgSetup.yearId}&organisationKey={orgSetup.organisationKey}&competitionUniqueKey={orgSetup.competitionUniqueKey}"


def matchRoot():
  # https://registration.squadi.com/matchSummary?matchId=797102&competitionUniqueKey=ed9f3608-81fb-4c60-82b5-7c1ab2149180
  return f"https://registration.squadi.com/matchSummary?competitionUniqueKey={orgSetup.competitionUniqueKey}"


ladders: list[ data.Ladder ] = []
results: list[ data.DivisionResults ] = []
teamMatchDetails = SquadiDetails()
divMatchDetails = []
loadedMatchDetails = False
loadedDivMatchDetails = False
nexts: list[ data.HighLevelDivisionFixture ] = []
recents: list[ data.HighLevelDivisionFixture ] = []
now = datetime.now( timezone.utc )
anyFetched = False


def calculateWinLoss( json, teamId ):
  for team in json[ 'lastResults' ]:
    if team[ 'teamId' ] == teamId:
      result = ""
      for last in team[ 'last5' ]:
        result += ( last[ 'code' ][ 0 ] if last[ 'code' ] else '-' )
      return result
  return '-----'


def processLadderData( div: shared.Division, json ):

  table: list[ data.LadderEntry ] = []
  for team in json[ 'ladders' ]:
    table.append(
        data.LadderEntry(
            teamId=team[ 'id' ],
            Rank=int( team[ 'rk' ] ),
            Team=data.sanitiseTeam( data.cleanTeam( team[ 'name' ] ) ),
            GamesPlayed=int( team[ 'P' ] ),
            GamesWon=int( team[ 'W' ] ),
            GamesDrawn=int( team[ 'D' ] ),
            GamesLost=int( team[ 'L' ] ),
            GoalsFor=int( team[ 'F' ] ),
            GoalsAgainst=int( team[ 'A' ] ),
            Points=int( team[ 'PTS' ] ),
            GoalsDiff=int( team[ 'goalDifference' ] ),
            WinLoss=calculateWinLoss( json, team[ 'id' ] )
        )
    )
  ladders.append( data.Ladder( div=div, table=table ) )


def parseDateTime( stringValue ):
  return datetime.fromisoformat( stringValue.replace( "Z", "+00:00" ) )


def localTime( dtUTC ):
  return dtUTC.astimezone( timezone( timedelta( hours=10 ) ) )


def displayTime( dtLocal ):
  return dtLocal.strftime( "%a, %b %d %I:%M %p" )


def noDelimTime( dtLocal ):
  return dtLocal.strftime( "%Y%m%d%H%M" )


def createMatch( match, startTime ) -> data.HighLevelFixture:
  clean1 = data.cleanTeam( match[ 'team1' ][ 'name' ] )
  clean2 = data.cleanTeam( match[ 'team2' ][ 'name' ] )
  return data.HighLevelFixture(
      id=int( match[ 'id' ] ),
      startTime=startTime,
      when=displayTime( localTime( startTime ) ),
      homeId=int( match[ 'team1Id' ] ),
      home=data.sanitiseTeam( clean1 ),
      goalsHome=int( match[ "team1Score" ] ),
      awayId=int( match[ 'team2Id' ] ),
      away=data.sanitiseTeam( clean2 ),
      goalsAway=int( match[ "team2Score" ] ),
      ground=data.cleanVenue( clean1, match[ 'venueCourt' ][ 'venue' ][ 'name' ] + ' ' + match[ 'venueCourt' ][ 'name' ] )
  )


def processResultsData( div: shared.Division, json ):

  rounds = []
  for round in json[ 'rounds' ]:
    matches: list[ data.HighLevelFixture ] = []
    for match in round[ 'matches' ]:
      if match[ "team1Id" ] == div.teamId or match[ 'team2Id' ] == div.teamId:

        startTime = parseDateTime( match[ 'startTime' ] )
        if match[ 'matchStatus' ] == 'ENDED':
          # It's a match for our team, so let's store the result
          newMatch = createMatch( match, startTime )
          matches.append( newMatch )

          if startTime < now and ( now - startTime ) <= timedelta( days=args.recent ):
            recents.append( data.HighLevelDivisionFixture( div, newMatch ) )

        if match[ 'matchStatus' ] is None and startTime > now and ( startTime - now ) <= timedelta( days=7 ):
          nexts.append( data.HighLevelDivisionFixture( div, createMatch( match, startTime ) ) )

    if len( matches ) > 0:
      rounds.append(
          data.HighLevelRoundFixtures(
              data.FixtureRound( name=round[ 'name' ], id=int( round[ 'id' ] ), sequence=int( round[ 'sequence' ] ) ), matches
          )
      )
  results.append( data.DivisionResults( div, rounds ) )


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


def processFullResultsData( json, existing ):
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


def fetchDivisionLadderAndResults( div: shared.Division, page: Page ):
  # Capture the API response you care about
  ladderURL = f"{ladderRoot()}&divisionId={div.divisionId}"

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


def pushBlankDiv( div: shared.Division ) -> list[ FixtureWrapper ]:
  global anyFetched
  added = DivisionData( div=div )
  teamMatchDetails.data.append( added )
  anyFetched = True
  return added.matches


def pushBlankFullDiv( div: shared.Division ):
  global anyFetched
  added = { "div": div, "rounds": []}
  divMatchDetails.append( added )
  anyFetched = True
  return added[ 'rounds' ]


def loadFullExistingDetails( div: shared.Division ):
  global divMatchDetails, loadedDivMatchDetails
  p = Path( f"{outputBase}/divMatchDetails.json" )
  if not p.exists():
    return pushBlankFullDiv( div )
  if not loadedDivMatchDetails:
    with open( f"{outputBase}/divMatchDetails.json", 'r' ) as f:
      divMatchDetails = json.load( f )
    loadedDivMatchDetails = True

  for i in divMatchDetails:
    if i[ 'div' ][ 'divisionId' ] == div.divisionId:
      return i[ 'rounds' ]

  # If we get to this point, it didn't exist in the cached results, so add a blank one
  return pushBlankFullDiv( div )


def loadExistingDetails( div: shared.Division ) -> list[ FixtureWrapper ]:
  global loadedMatchDetails, teamMatchDetails
  p = Path( f"{outputBase}/matchDetails.json" )
  if not p.exists():
    return pushBlankDiv( div )
  if not loadedMatchDetails:
    tmd = None
    with open( f"{outputBase}/matchDetails.json", 'r' ) as f:
      tmd = json.load( f )
    loadedMatchDetails = True
    teamMatchDetails = SquadiDetails( data=[ shared.from_dict( DivisionData, d ) for d in tmd ] )

  for i in teamMatchDetails.data:
    if i.div.divisionId == div.divisionId:
      return i.matches

  # If we get to this point, it didn't exist in the cached results, so add a blank one
  return pushBlankDiv( div )


def getDivResults( div: shared.Division ) -> data.DivisionResults | None:
  return next( ( i for i in results if i.div.divisionId == div.divisionId ), None )


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


def processFetchedMatchDetails( matchId, teamOfInterest, existing: list[ FixtureWrapper ], json, startTime ):
  global anyFetched
  toAdd = FixtureWrapper(
      match=Fixture( id=matchId, date=noDelimTime( localTime( parseDateTime( startTime ) ) ) )
  )
  for player in json[ 'playing' ]:
    if player[ 'teamId' ] == teamOfInterest:
      # Got a player to add!
      yellows, reds = calculateCards( player[ 'cards' ] )
      newPlayer = Player(
          shirt=int( player[ 'shirt' ] ),
          name=player[ 'firstName' ] + " " + player[ 'lastName' ],
          goals=player[ 'goals' ][ 0 ][ 'count' ] if len( player[ 'goals' ] ) > 0 else 0,
          yellows=yellows,
          reds=reds
      )
      toAdd.match.players.append( newPlayer )
  for official in json[ 'teamOfficials' ]:
    if official[ 'teamId' ] == teamOfInterest:
      newOfficial = shared.Official( role=official[ 'role' ], name=official[ 'firstName' ] + " " + official[ 'lastName' ] )
      toAdd.match.officials.append( newOfficial )

  existing.append( toAdd )
  anyFetched = True


def fetchMatchDetails( matchId, teamOfInterest, existing: list[ FixtureWrapper ], browser: Browser, startTime ):
  with browser.new_page() as page:
    matchURL = f"{matchRoot()}&matchId={matchId}"

    def handle_response( response: Response ) -> None:
      try:
        json = response.json()
        if '/gameSummary' in response.url:
          processFetchedMatchDetails( matchId, teamOfInterest, existing, json, startTime )
      except Exception:
        pass

    page.on( "response", handle_response )

    # Load the page normally
    page.goto( matchURL )

    # Wait for JS to finish loading
    page.wait_for_load_state( "networkidle" )


def fetchNewDetails( div: shared.Division, browser: Browser, existing: list[ FixtureWrapper ] ):
  global anyFetched
  # So, we only care about results, and results -we don't already have-
  divResults = getDivResults( div )
  teamOfInterest = div.teamId
  if divResults is None:
    return

  # These are the divisional results we need answers for
  for round in divResults.rounds:
    for m in round.matches:

      matchId = m.id
      print( f" .. {round.round.name.ljust( 10 )} Match {matchId}", end='' )

      # Firstly, let's see if we've fetched it - if we have, no need to process it!
      alreadyDone = False
      for eligible in existing:
        if eligible.match.id == matchId:
          print( " .. Matched!" )
          alreadyDone = True
          # But let's check ...
          if eligible.match.date == '':
            # Copy the date!
            eligible.match.date = noDelimTime( localTime( parseDateTime( m.startTime ) ) )
            anyFetched = True
          break

      if alreadyDone:
        continue

      print( " .. Fetching match details" )
      fetchMatchDetails( matchId, teamOfInterest, existing, browser, m.startTime )


def fetchDivNewDetails( div: shared.Division, browser: Browser, existing ):
  # So, we only care about results, and results -we don't already have-
  resultsURL = f"{teamFixtureRoot()}&divisionId={div.divisionId}"

  with browser.new_page() as page:

    def handle_response( response: Response ) -> None:
      try:
        json = response.json()
        # https://api.squadi.com/livescores/round/matches?competitionId=1287&divisionId=9189&teamIds=&ignoreStatuses=[1]
        if '/livescores/round/matches' in response.url:
          processFullResultsData( json, existing )
      except Exception:
        pass

    page.on( "response", handle_response )

    # Load the page normally
    page.goto( resultsURL )

    # Wait for JS to finish loading
    page.wait_for_load_state( "networkidle" )


if args.match:
  print( "Loading existing data" )
  laddersData = shared.loadJson( outputBase, 'ladder.json' )
  ladders = [ shared.from_dict( data.Ladder, d ) for d in laddersData ] if laddersData else []
  resultsData = shared.loadJson( outputBase, 'results.json' ) or []
  results = [ shared.from_dict( data.DivisionResults, d ) for d in resultsData ] if resultsData else []
  nextsData = shared.loadJson( outputBase, 'next.json' )
  nexts = [ shared.from_dict( data.HighLevelDivisionFixture, d ) for d in nextsData ] if nextsData else []
  recentsData = shared.loadJson( outputBase, 'recent.json' ) or []
  recents = [ shared.from_dict( data.HighLevelDivisionFixture, d ) for d in recentsData ] if recentsData else []

with sync_playwright() as p:
  browser = p.chromium.launch( headless=True )

  with tqdm( total=len( divisions ) ) as pbar:
    for div in divisions:
      pbar.set_description( f"Processing {div.name}" )
      with tqdm( total=3 ) as pbar2:
        if args.summary:
          pbar2.set_description( "Ladder + Results" )
          with browser.new_page() as page:
            fetchDivisionLadderAndResults( div, page )
        pbar2.update()
        if args.match:
          pbar2.set_description( "Matches" )
          existing = loadExistingDetails( div )
          fetchNewDetails( div, browser, existing )
        pbar2.update()
        if args.div:
          pbar2.set_description( "Division Detail" )
          existing = loadFullExistingDetails( div )
          fetchDivNewDetails( div, browser, existing )
        pbar2.update()
      pbar.update()

  browser.close()

if args.summary:
  data.dumpJsonStructured( outputBase, 'ladder.json', ladders )
  data.dumpJsonStructured( outputBase, 'results.json', results )
  data.dumpJsonStructured( outputBase, 'next.json', nexts )
  data.dumpJsonStructured( outputBase, 'recent.json', recents )

if args.match and anyFetched:
  data.dumpJsonStructured( outputBase, 'matchDetails.json', teamMatchDetails.data )

if args.div:
  data.dumpJson( outputBase, 'divMatchDetails.json', divMatchDetails )
