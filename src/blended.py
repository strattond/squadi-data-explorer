from __future__ import annotations

from dataclasses import dataclass, field

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
  players: list[ Player ] = field( default_factory=list )
  officials: list[ shared.Official ] = field( default_factory=list )


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


def matchUserDiv( fixed: fixed.DivisionData, user: list[ user.DivisionData ] ) -> user.DivisionData | None:
  return next( ( i for i in user if i.div.name == fixed.div.name ), None )


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


def blendFixture( fixed: fixed.FixtureWrapper ) -> FixtureWrapper:
  newMatch = Fixture( fixed.match.id, fixed.match.date, officials=fixed.match.officials )
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


def blendSquadiDetails( fixed: fixed.SquadiDetails, user: user.SquadiDetails ) -> SquadiDetails:

  # So we need to find the matching division ...
  sd = SquadiDetails()
  for division in fixed.data:
    matchedDiv = matchUserDiv( division, user.data )
    # Nothing to blend at the division level
    newDiv = blendDiv( division )
    sd.data.append( newDiv )

    # And then find the matching matches ...
    for match in division.matches:
      matchedMatch = matchUserMatch( match, matchedDiv )
      newMatch = blendFixture( match )
      newDiv.matches.append( newMatch )

      # And then find the matching player ...
      for player in match.match.players:
        matchedPlayer = matchUserPlayer( player, matchedMatch )
        newMatch.match.players.append( blendPlayer( player, matchedPlayer ) )
  return sd
