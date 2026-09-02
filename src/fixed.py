from __future__ import annotations

from dataclasses import dataclass, field

import shared


def loadDivisionData( baseFolder, filename ) -> tuple[ bool, SquadiDetails ]:
  tmd = shared.loadJson( baseFolder, filename )
  if tmd is None:
    return ( False, SquadiDetails() )
  return ( True, SquadiDetails( data=[ shared.from_dict( DivisionData, d ) for d in tmd ] ) )


@dataclass
class Player:
  shirt: int
  name: str
  goals: int
  yellows: int
  reds: int


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


