from __future__ import annotations

from dataclasses import dataclass, field

import data
import shared


@dataclass
class PlayerUser:
  name: str
  started: bool
  position: str


@dataclass
class FixtureWrapperUser:
  match: FixtureUser


@dataclass
class FixtureUser:
  id: int
  players: list[ PlayerUser ] = field( default_factory=list )


@dataclass
class DivisionDataUser:
  div: shared.Division
  matches: list[ FixtureWrapperUser ] = field( default_factory=list )


@dataclass
class SquadiDetailsUser:
  data: list[ DivisionDataUser ] = field( default_factory=list )


def loadDivisionDataUser( baseFolder, filename ) -> tuple[ bool, SquadiDetailsUser ]:
  tmd = data.loadJson( baseFolder, filename )
  if tmd is None:
    return ( False, SquadiDetailsUser() )
  return ( True, SquadiDetailsUser( data=[ shared.from_dict( DivisionDataUser, d ) for d in tmd ] ) )
