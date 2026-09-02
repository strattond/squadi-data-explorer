import sys
from dataclasses import MISSING, dataclass
from typing import ForwardRef, Optional, get_args, get_origin


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
