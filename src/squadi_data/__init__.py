from pathlib import Path

from . import blended, data, fixed, shared, stats, user


def load_season( output_dir: str | Path ) -> data.SquadiDetails:
  return data.loadSquadiDetails( str( output_dir ), 'matchDetails.json', 'userMatchDetails.json', 'results.json' )


def blend_season( season: data.SquadiDetails ) -> blended.SquadiDetails:
  return blended.blendSquadiDetails( season )


__all__ = [
    "blend_season",
    "blended",
    "data",
    "fixed",
    "load_season",
    "shared",
    "stats",
    "user",
]
