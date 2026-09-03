from __future__ import annotations

from dataclasses import dataclass, field

import data
import fixed
import shared
import user


@dataclass
class Player:
  shirt: int
  name: str
  goals: int
  yellows: int
  reds: int
  started: bool = False
  position: str = ""


@dataclass
class Fixture:
  id: int
  date: str
  result: data.HighLevelFixture | None = field( default=None )
  round: data.FixtureRound | None = field( default=None )
  players: list[ Player ] = field( default_factory=list )
  officials: list[ shared.Official ] = field( default_factory=list )

  def toComboString( self ) -> str:
    if self.result is None and self.round is None:
      return f"{self.id} - {self.date}"
    rVal = ""
    if self.round is not None:
      rVal += f"{self.round.name} "
    if self.result is not None:
      rVal += f"{self.result.home} ({self.result.goalsHome}) vs {self.result.away} ({self.result.goalsAway})"
    rVal += f" ({self.date})"
    return rVal


@dataclass
class FixtureWrapper:
  match: Fixture


@dataclass
class DivisionData:
  div: shared.Division
  matches: list[ FixtureWrapper ] = field( default_factory=list )


@dataclass
class SquadiDetails:
  data: list[ DivisionData ] = field( default_factory=list )

  def slice( self, divisions: list[ str ] ):

    slicedF = [ div for div in self.data if div.div.name in divisions ]
    return SquadiDetails( data=slicedF )


def matchResultDiv( fixed: fixed.DivisionData, results: list[ data.DivisionResults ] ) -> data.DivisionResults | None:
  return next( ( i for i in results if i.div.name == fixed.div.name ), None )


def matchUserDiv( fixed: fixed.DivisionData, user: list[ user.DivisionData ] ) -> user.DivisionData | None:
  return next( ( i for i in user if i.div.name == fixed.div.name ), None )


def matchResultMatch(
    fixed: fixed.FixtureWrapper, user: data.DivisionResults | None
) -> tuple[ data.HighLevelFixture, data.HighLevelRoundFixtures ] | tuple[ None, None ]:
  if user is None:
    return ( None, None )
  return next( ( ( m, i ) for i in user.rounds for m in i.matches if m.id == fixed.match.id ), ( None, None ) )


def matchUserMatch( fixed: fixed.FixtureWrapper, user: user.DivisionData | None ) -> user.FixtureWrapper | None:
  if user is None:
    return None
  return next( ( i for i in user.matches if i.match.id == fixed.match.id ), None )


def matchUserPlayer( player: fixed.Player, user: user.FixtureWrapper | None ) -> user.Player | None:
  if user is None:
    return None
  return next( ( i for i in user.match.players if i.name == player.name ), None )


def blendDiv( fixed: fixed.DivisionData ) -> DivisionData:
  return DivisionData( div=fixed.div )


def blendFixture(
    fixed: fixed.FixtureWrapper, match: data.HighLevelFixture | None, round: data.HighLevelRoundFixtures | None
) -> FixtureWrapper:
  newMatch = Fixture(
      fixed.match.id,
      fixed.match.date,
      officials=fixed.match.officials,
      result=match,
      round=( round.round if round is not None else None )
  )
  return FixtureWrapper( match=newMatch )


def blendPlayer( player: fixed.Player, userPlayer: user.Player | None ) -> Player:
  if userPlayer is None:
    return Player( shirt=player.shirt, name=player.name, goals=player.goals, yellows=player.yellows, reds=player.reds )
  return Player(
      shirt=player.shirt,
      name=player.name,
      goals=player.goals,
      yellows=player.yellows,
      reds=player.reds,
      started=userPlayer.started,
      position=userPlayer.position
  )


def blendSquadiDetails( data: data.SquadiDetails ) -> SquadiDetails:

  fixed = data.fixedD
  user = data.userD
  results = data.results

  # So we need to find the matching division ...
  sd = SquadiDetails()
  for division in fixed.data:
    matchedUDiv = matchUserDiv( division, user.data )
    matchedRDiv = matchResultDiv( division, results )
    # Nothing to blend at the division level
    newDiv = blendDiv( division )
    sd.data.append( newDiv )

    # And then find the matching matches ...
    for match in division.matches:
      matchedUMatch = matchUserMatch( match, matchedUDiv )
      matchedRMatch, matchedRound = matchResultMatch( match, matchedRDiv )
      newMatch = blendFixture( match, matchedRMatch, matchedRound )
      newDiv.matches.append( newMatch )

      # And then find the matching player ...
      for player in match.match.players:
        matchedPlayer = matchUserPlayer( player, matchedUMatch )
        newMatch.match.players.append( blendPlayer( player, matchedPlayer ) )
  return sd


def getDivByName( divisions: list[ DivisionData ], match ) -> DivisionData | None:
  if len( divisions ) == 0:
    return None
  return next( ( d for d in divisions if d.div.name == match ), None )
