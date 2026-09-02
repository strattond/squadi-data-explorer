from __future__ import annotations

from dataclasses import dataclass, field

import data
import shared


def loadDivisionDataFixed( baseFolder, filename ) -> tuple[ bool, SquadiDetailsFixed ]:
  tmd = data.loadJson( baseFolder, filename )
  if tmd is None:
    return ( False, SquadiDetailsFixed() )
  return ( True, SquadiDetailsFixed( data=[ shared.from_dict( DivisionDataFixed, d ) for d in tmd ] ) )


@dataclass
class PlayerFixed:
  shirt: int
  name: str
  goals: int
  yellows: int
  reds: int


@dataclass
class FixtureFixed:
  id: int
  date: str
  players: list[ PlayerFixed ] = field( default_factory=list )
  officials: list[ shared.Official ] = field( default_factory=list )


@dataclass
class FixtureWrapperFixed:
  match: FixtureFixed


@dataclass
class DivisionDataFixed:
  div: shared.Division
  matches: list[ FixtureWrapperFixed ] = field( default_factory=list )


@dataclass
class SquadiDetailsFixed:
  data: list[ DivisionDataFixed ] = field( default_factory=list )


