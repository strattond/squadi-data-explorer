from __future__ import annotations

import json
import sys
from dataclasses import MISSING, dataclass, field
from pathlib import Path
from typing import Any, ForwardRef, Optional, get_args, get_origin


@dataclass
class Organisation:
  yearId: int
  organisationKey: str
  competitionUniqueKey: str


@dataclass
class ConfigEntry:
  organisation: Organisation
  divisions: list[ Division ] = field( default_factory=list )


@dataclass
class Division:
  name: str
  divisionId: int
  teamId: int


@dataclass
class Official:
  name: str
  role: str


def resolve_type( typ, owner_module ):
  if isinstance( typ, str ):
    return eval( typ, sys.modules[ owner_module ].__dict__ )
  if isinstance( typ, ForwardRef ):
    return eval( typ.__forward_arg__, sys.modules[ owner_module ].__dict__ )
  return typ


def from_dict( cls, data ):
  if not isinstance( data, dict ):
    return data

  kwargs = {}
  owner_module = cls.__module__
  for field_name, field_def in cls.__dataclass_fields__.items():
    raw_typ = field_def.type
    typ = resolve_type( raw_typ, owner_module )

    # Field missing in JSON
    if field_name not in data:
      if field_def.default is not MISSING:
        kwargs[ field_name ] = field_def.default
      elif field_def.default_factory is not MISSING:
        kwargs[ field_name ] = field_def.default_factory()
      else:
        kwargs[ field_name ] = None
      continue

    value = data[ field_name ]

    # Optional[T]
    if get_origin( typ ) is Optional:
      inner = get_args( typ )[ 0 ]
      kwargs[ field_name ] = None if value is None else from_dict( inner, value )
      continue

    # Nested dataclass
    if hasattr( typ, "__dataclass_fields__" ):
      kwargs[ field_name ] = from_dict( typ, value )

    # List[T]
    elif getattr( typ, "__origin__", None ) is list:
      inner = typ.__args__[ 0 ]
      kwargs[ field_name ] = [ from_dict( inner, item ) for item in value ]

    # Dict[str, T]
    elif getattr( typ, "__origin__", None ) is dict:
      inner = typ.__args__[ 1 ]
      kwargs[ field_name ] = { k: from_dict( inner, v ) for k, v in value.items() }

    else:
      kwargs[ field_name ] = value

  return cls( **kwargs )


def loadJson( baseFolder, filename ) -> None | Any:
  qualifile = f"{baseFolder}/{filename}"
  target = Path( qualifile )
  if not target.exists():
    return None
  with open( qualifile, "r" ) as f:
    return json.load( f )


def loadConfig() -> list[ ConfigEntry ]:
  with open( "data/config.json", "r" ) as f:
    configData = json.load( f )
    return [ from_dict( ConfigEntry, d ) for d in configData ] if configData else []
  return []


def getMatchingConfig( yearOfInterest: int, config: list[ ConfigEntry ] ) -> ConfigEntry:
  toReturn = next( ( i for i in config if i.organisation.yearId == yearOfInterest ), None )
  if toReturn is not None:
    return toReturn

  print( "Please provide a valid configuration year" )
  sys.exit( 1 )


def getPaths( configMatch: ConfigEntry ):
  outputBase = f"output/{configMatch.organisation.yearId}"
  plotBase = f"plots/{configMatch.organisation.yearId}"

  return ( outputBase, plotBase )
