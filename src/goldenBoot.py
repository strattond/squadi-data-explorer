import argparse
import json
import os
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def figure_for_resolution( width_px, height_px, dpi=100 ):
  return plt.subplots( figsize=( width_px / dpi, height_px / dpi ), dpi=dpi )


def uniquePlayers( data ):
  unique_players = set()

  for division in data:
    for match in division.get( "matches", [] ):
      for player in match[ "match" ].get( "players", [] ):
        unique_players.add( player[ "name" ] )

  return sorted( unique_players )


def naturalDivKey( divName ):
  # Extract leading integer (division number)
  m = re.match( r"(\d+)", divName )
  return int( m.group( 1 ) ) if m else float( 'inf' )


def mixedDivKey( divName ):
  # Extract leading integer (division number)
  m = re.match( r"\D*(\d+)\D*", divName )
  return int( m.group( 1 ) ) if m else float( 'inf' )


def naturalNameKey( playerName ):
  # Extract names
  m = re.match( r"(\w+) (\w+)", playerName )
  if m is not None:
    return m.group( 2 ) + " " + m.group( 1 )
  else:
    return ''


def sortedDivisions( data ):
  all_divisions = set()

  for division in data:
    all_divisions.add( division[ "div" ][ 'name' ] )

  return sorted( all_divisions, key=mixedDivKey )


def maxMatches( data ):
  return max( len( d.get( "matches", [] ) ) for d in data )


def newEntryValue( stat, value ):
  return np.nan_to_num( stat, nan=0.0 ) + value


def makeDivBlock( numRounds ):
  return {
      "appearances": 0,
      "goals": np.full( numRounds, np.nan ),
      "yellows": np.full( numRounds, np.nan ),
      "reds": np.full( numRounds, np.nan ),
      "fairPlay": np.full( numRounds, np.nan ),
  }


def accumulateStats( data ):

  player_stats = {}
  maxRounds = maxMatches( data )
  for division in data:
    divName = division[ "div" ][ 'name' ]
    for matchNum, match in enumerate( division.get( "matches", [] ) ):
      for player in match[ "match" ].get( "players", [] ):
        name = player[ "name" ]
        stats = player_stats.setdefault(
            name, {
                "name": name,
                "appearances": 0,
                "goals": 0,
                "yellows": 0,
                "reds": 0,
                "fairPlay": 0,
                "div": {},  # divName -> count,
                "roundGoals": np.full( maxRounds, np.nan ),
                "roundYellows": np.full( maxRounds, np.nan ),
                "roundReds": np.full( maxRounds, np.nan ),
                "roundFairPlay": np.full( maxRounds, np.nan ),
                "starts": 0
            }
        )

        # appearances
        stats[ "appearances" ] += 1
        divStats = stats[ 'div' ].setdefault( divName, makeDivBlock( maxRounds ) )
        divStats[ 'appearances' ] += 1

        # goals/yellows/reds may not exist on this record
        roundGoals = player.get( "goals", 0 )
        roundYellows = player.get( "yellows", 0 )
        roundReds = player.get( "reds", 0 )
        didStart = player.get( "started", False )
        if didStart:
          stats[ "starts" ] += 1
        stats[ "goals" ] += roundGoals
        stats[ "yellows" ] += roundYellows
        stats[ "reds" ] += roundReds
        stats[ "fairPlay" ] += ( roundYellows + 2*roundReds )

        divStats[ 'goals' ][ matchNum ] = roundGoals
        divStats[ 'yellows' ][ matchNum ] = roundYellows
        divStats[ 'reds' ][ matchNum ] = roundReds
        divStats[ 'fairPlay' ][ matchNum ] = roundYellows + 2*roundReds

        stats[ 'roundGoals' ][ matchNum ] = newEntryValue( stats[ 'roundGoals' ][ matchNum ], roundGoals )
        stats[ 'roundYellows' ][ matchNum ] = newEntryValue( stats[ 'roundYellows' ][ matchNum ], roundYellows )
        stats[ 'roundReds' ][ matchNum ] = newEntryValue( stats[ 'roundReds' ][ matchNum ], roundReds )
        stats[ 'roundFairPlay' ][ matchNum ] = newEntryValue( stats[ 'roundFairPlay' ][ matchNum ], roundYellows + 2*roundReds )

  return player_stats


def plotStatsData( data, filename, sorted_stats, property, maxProp, labelY, title, withStep=False ):
  fig, ax = figure_for_resolution( 6000, 4000, dpi=100 )

  # Transparent backgrounds
  fig.patch.set_alpha( 0 )
  ax.patch.set_alpha( 0 )

  cumRounds = maxMatches( data )
  for i, ( name, value ) in enumerate( sorted_stats ):
    jitter = i * 0.03
    color = ax._get_lines.get_next_color()
    rangeData = range( 1, cumRounds + 1 )
    cumulative = np.nancumsum( np.nan_to_num( value[ property ] ) )
    cumulative[ np.isnan( value[ property ] ) ] = np.nan
    if withStep:
      ax.step( rangeData, [ g + jitter for g in cumulative ], where="post", linewidth=25, color=color )
    ax.plot( rangeData, [ g + jitter for g in cumulative ], marker="o", markersize=50, linewidth=15, label=name, color=color )

  cumRounds = maxMatches( data )
  rangeData = range( 1, cumRounds + 1 )
  maxStat = ( sorted_stats[ 0 ][ 1 ] )[ maxProp ]
  maxStatRange = range( maxStat + 1 )
  ax.set_title( title, fontsize=320, color="white" )
  ax.set_xlabel( "Round", fontsize=56, color="white" )
  ax.set_ylabel( labelY, fontsize=56, color="white" )
  ax.set_ybound( 0, maxStat + 1 )
  ax.grid( True, linestyle="--", alpha=0.4 )
  ax.legend( title="Player", fontsize=56 )
  ax.set_xticks( rangeData )
  ax.set_xticklabels( [ str( r ) for r in rangeData ], fontsize=56 )
  ax.set_yticks( maxStatRange )
  ax.set_yticklabels( [ str( r ) for r in maxStatRange ], fontsize=56 )
  ax.tick_params( colors="white" )

  plt.tight_layout()
  plt.savefig( filename, dpi=100, transparent=True )


def plotRowData( col_labels, rows, filename, width=3000, height=2000, vScale=4, fontsize=24 ):
  fig, ax = figure_for_resolution( width, height, dpi=100 )

  # Transparent backgrounds
  fig.patch.set_alpha( 0 )
  ax.patch.set_alpha( 0 )
  ax.axis( "off" )

  table = ax.table(
      cellText=rows,
      colLabels=col_labels,
      loc="center",
      cellLoc="center",
  )

  # Clean infographic look
  for ( row, col ), cell in table.get_celld().items():
    cell.set_edgecolor( "none" )
    # Left-align the Player column (column index 0)
    if col == 0:  # first column
      cell.get_text().set_horizontalalignment( "left" )
      cell.set_text_props( ha="left" )

  table.auto_set_font_size( True )
  table.set_fontsize( fontsize )
  table.scale( 1, vScale )

  plt.tight_layout()
  plt.savefig( filename, dpi=100, transparent=True )


def getInfographicData( player_stats ):
  cumRounds = maxMatches( data )
  total_goals = sum( stats[ "goals" ] for stats in player_stats.values() )
  total_yellows = sum( stats[ "yellows" ] for stats in player_stats.values() )
  total_reds = sum( stats[ "reds" ] for stats in player_stats.values() )
  unique_scorers = sum( 1 for stats in player_stats.values() if stats[ "goals" ] > 0 )
  unique_carders = sum( 1 for stats in player_stats.values() if stats[ "fairPlay" ] > 0 )
  avg_goals_per_week = total_goals / cumRounds if cumRounds else 0
  round_totals = [ 0 ] * cumRounds

  for stats in player_stats.values():
    for i, g in enumerate( stats[ "roundGoals" ] ):
      if not np.isnan( g ):
        round_totals[ i ] += g

  highest_round = max( range( cumRounds ), key=lambda i: round_totals[ i ] )
  highest_round_goals = round_totals[ highest_round ]

  top_scorer = max( player_stats.items(), key=lambda item: item[ 1 ][ "goals" ] )
  top_carder = max( player_stats.items(), key=lambda item: item[ 1 ][ "fairPlay" ] )

  return {
      "goals": total_goals,
      "yellows": total_yellows,
      "reds": total_reds,
      "uniqueScorers": unique_scorers,
      "uniqueCarders": unique_carders,
      "avgGoalsPerRound": avg_goals_per_week,
      "highestRound": highest_round,
      "highestRoundGoals": highest_round_goals,
      "numRounds": cumRounds,
      "top_scorer": {
          "name": top_scorer[ 1 ][ 'name' ],
          "goals": top_scorer[ 1 ][ 'goals' ]
      },
      "top_carder": {
          "name": top_carder[ 1 ][ 'name' ],
          "cards": top_carder[ 1 ][ 'yellows' ]
      }
  }


def playerPrimaryDivision( stats ):
  return max( stats[ "div" ], key=lambda div: stats[ "div" ][ div ][ 'appearances' ] )


def playerPlayedInDivision( stats, div ):
  return div in stats[ 'div' ] and stats[ 'div' ][ div ][ 'appearances' ] > 0


def calcPlayerBorrowStats( stats ):
  primary = playerPrimaryDivision( stats )
  return { div: count[ 'appearances' ] for div, count in stats[ "div" ].items() if div != primary }


def calcPlayerStats( stats ):
  return { div: count[ 'appearances' ] for div, count in stats[ "div" ].items() }


def totalBorrowings( stats ):
  return sum( calcPlayerBorrowStats( stats ).values() )


def getDiv( data, match ):
  for d in data:
    if d[ 'div' ][ 'name' ] == match:
      return d
  return None


def drawColourChart(
    colors, numCols: int, numRows: int, colLabels: list, rowLabels: list, dataMatrix, filename: str, rowData, div: str
):

  cellW = 40
  cellH = 40
  leftMargin = 200
  topMargin = 50

  imgW = leftMargin + cellW * ( numCols+1 )
  imgH = topMargin + cellH * ( numRows+1 )

  img = Image.new( "RGB", ( imgW, imgH ), "white" )
  draw = ImageDraw.Draw( img )
  font = ImageFont.load_default( size=cellH // 2 )

  # Draw filled rectangles
  for i in range( numCols ):
    x = leftMargin + i*cellW
    draw.text( ( x + cellW//4, 10 ), colLabels[ i ], fill="black", font=font )

  for i in range( numRows ):
    y = topMargin + i*cellH
    draw.text( ( 10, y + cellH//4 ), rowLabels[ i ], fill="black", font=font )
    for j in range( numCols ):
      x = leftMargin + j*cellW
      state: int = dataMatrix[ i, j ]

      played: bool = ( state & 1 ) == 1
      started: bool = ( state & 2 ) == 2
      yellows: bool = ( state & 4 ) == 4
      reds: bool = ( state & 8 ) == 8
      goals: bool = ( state & 16 ) == 16

      # colors = { 0: "black", 1: "lightgreen", 2: "green", 3: 'yellow', 4: 'red' }
      if not played:
        draw.rectangle( [ x, y, x + cellW, y + cellH ], outline="black", fill=colors[ 0 ] )
      elif not yellows and not reds:
        # No cards, so a rectangle will do
        plColor = 2 if started else 1
        draw.rectangle( [ x, y, x + cellW, y + cellH ], outline="black", fill=colors[ plColor ] )
      else:
        plColor = 2 if started else 1
        crdColor = 4 if reds else 3
        tl = ( x, y )
        tr = ( x + cellW, y )
        bl = ( x, y + cellH )
        br = ( x + cellW, y + cellH )
        tri1 = [ tl, bl, tr ]
        tri2 = [ br, bl, tr ]
        draw.polygon( tri1, outline='black', fill=colors[ plColor ] )
        draw.polygon( tri2, outline='black', fill=colors[ crdColor ] )

      if goals:
        wd = 16
        football = Image.open( "ball.png" ).convert( "RGBA" )
        football_sm = football.resize( ( wd, wd ), Image.Resampling.LANCZOS )
        #print( rowData[i] )
        nGoals = rowData[ i ][ 1 ][ 'div' ][ div ][ 'goals' ][ j ]
        if not np.isnan( nGoals ) and nGoals > 1:
          toDisp = str( int( nGoals ) )
          bbox = draw.textbbox( ( 0, 0 ), toDisp, font=font )
          h = bbox[ 3 ] - bbox[ 1 ]
          cx = x + ( cellW//2 )
          cy = y + ( cellH//2 )
          img.paste( football_sm, ( x + cellW//8, y + ( cellH-wd ) // 2 ), football_sm )
          draw.text( ( cx + cellW//8, cy - h ), text=toDisp, fill='red', stroke_width=0.2, font=font )
        else:
          img.paste( football_sm, ( x + ( cellW-wd ) // 2, y + ( cellH-wd ) // 2 ), football_sm )

  img.save( f"{plotBase}/{filename}.png" )


def calcAppearanceScore( player ) -> int:
  if player is None:
    # Can't score goals, can't get carded, can't start or appear
    return 0
  rVal: int = 1
  # Bit 0 (1) - Played
  # Bit 1 (2) - Started
  # Bit 2 (4) - Yellows
  # Bit 3 (8) - Reds
  # Bit 4 (16) - Goals
  # colors = { 0: "black", 1: "lightgreen", 2: "green", 3: 'yellow', 4: 'red' }
  if 'reds' in player and player[ 'reds' ] is not None and player[ 'reds' ] > 0:
    rVal |= 8
  if 'yellows' in player and player[ 'yellows' ] is not None and player[ 'yellows' ] > 0:
    if player[ 'yellows' ] > 1:
      rVal |= 8
    else:
      rVal |= 4
  if 'started' in player and player[ 'started' ] is not None and player[ 'started' ]:
    rVal |= 2

  if 'goals' in player and p2[ 'goals' ] is not None and player[ 'goals' ] > 0:
    rVal |= 16

  return rVal


parser = argparse.ArgumentParser(
    prog="Squadi Stats Processor", description="Processes stats data previously retrieved from Squadi"
)
parser.add_argument( "--year", help="The competition year of interest", type=int )

args = parser.parse_args()

print( "Loading configuration" )
with open( "data/config.json", "r" ) as f:
  config = json.load( f )

print( f"Starting our squadi stats processing for year {args.year}" )

configMatch = None
for comp in config:
  if comp[ 'organisation' ][ 'yearId' ] == args.year:
    configMatch = comp
    break

if configMatch is None:
  print( "Please provide a valid configuration year" )
  sys.exit( 1 )

outputBase = f"output/{configMatch['organisation']['yearId']}"
plotBase = f"plots/{configMatch['organisation']['yearId']}"
outputFolder = Path( outputBase )
if not outputFolder.exists():
  print( "Please retrieve Squadi data first" )
  sys.exit( 1 )

plotFolder = Path( plotBase )
if not plotFolder.exists():
  os.makedirs( plotFolder )

print( "Loading data" )
with open( f"{outputBase}/matchDetails.json", "r" ) as f:
  data = json.load( f )

print( " .. Getting unique players" )
players = uniquePlayers( data )

print( " .. Getting divisions" )
divisions = sortedDivisions( data )
print( "Accumulating stats" )
player_stats = accumulateStats( data )

print( " .. Sorting by Goals" )
topN = sorted( ( ( name, stats ) for name, stats in player_stats.items() if stats[ 'goals' ] > 2 ),
               key=lambda item: item[ 1 ][ "goals" ],
               reverse=True )

topN = topN[ :10 ]

print( "Plotting Golden Boot" )
plotStatsData( data, f"{plotBase}/golden_boot.png", topN, "roundGoals", "goals", "Goals", "Golden Boot Race" )

print( " .. Sorting by Fair Play" )
sorted_stats = sorted( player_stats.items(), key=lambda item: item[ 1 ][ "fairPlay" ], reverse=True )
topN = sorted_stats[ :5 ]

print( "Plotting Golden Card" )
plotStatsData( data, f"{plotBase}/golden_card.png", topN, "roundYellows", "yellows", "Cards", "Golden Card Race" )

infographic = getInfographicData( player_stats )

with open( f"{outputBase}/stats.json", "w", encoding="utf-8" ) as f:
  json.dump( infographic, f, indent=2, ensure_ascii=False )

print( "Calculating borrowings" )
rows = []
filtered_players = { name: stats for name, stats in player_stats.items() if len( stats[ "div" ] ) >= 2 }
# But we only care about "borrowings".  And we can take the punt that a primary team is the one they've appeared in the most
for name, stats in sorted(
    filtered_players.items(), key=lambda item: ( -totalBorrowings( item[ 1 ] ), naturalNameKey( item[ 0 ] ) )
):
  totalBorrow = totalBorrowings( stats )
  if totalBorrow > 1:
    playedStats = calcPlayerStats( stats )
    row = [ name, totalBorrow ] + [ playedStats.get( div, "" ) for div in divisions ] + [ stats[ "appearances" ] ]
    rows.append( row )

col_labels = [ "Player", "Borrowed" ] + divisions + [ "Total appearances" ]
col_widths = [ 24, 12 ] + [ 20 ] * len( divisions ) + [ 12 ]
plotRowData( col_labels, rows, f"{plotBase}/borrowings.png", 1280, 960, 1, 72 )

print( "Calculating appearances" )
for div in divisions:
  print( f" .. {div}" )
  divPlayers = { name: stats for name, stats in player_stats.items() if playerPlayedInDivision( stats, div ) }

  sortedDivPlayers = sorted( divPlayers.items(), key=lambda item: ( -item[ 1 ][ "div" ][ div ][ 'appearances' ], item[ 0 ] ) )

  rows = []
  for name, stats in sortedDivPlayers:
    row = [ name, stats[ "div" ][ div ][ 'appearances' ], stats[ 'starts' ] ]
    rows.append( row )

  col_labels = [ "Player", "Appearances", "Starts" ]
  plotRowData( col_labels, rows, f"{plotBase}/teamList.{div}.png", 1280, ( 48 * ( len( rows ) + 1 ) ), 2 )

  sortedDivPlayers = sorted( divPlayers.items(), key=lambda item: item[ 1 ][ "name" ] )
  playerNames = [ p[ 1 ][ 'name' ] for p in sortedDivPlayers ]

  divDetail = getDiv( data, div )
  if divDetail is not None:
    numRounds = len( divDetail[ 'matches' ] )
    playerMatrix = np.zeros( ( len( sortedDivPlayers ), numRounds ), dtype=np.uint32 )
    for i, p in enumerate( sortedDivPlayers ):
      for r in range( numRounds ):
        match = divDetail[ 'matches' ][ r ][ 'match' ]
        matched = None
        for p2 in match[ 'players' ]:
          if p[ 1 ][ 'name' ] == p2[ 'name' ]:
            matched = p2
            break
        playerMatrix[ i, r ] = calcAppearanceScore( matched )

    ## Marker colors for each state
    colors = { 0: "black", 1: "lightgreen", 2: "green", 3: 'yellow', 4: 'red'}

    colLabels = [ str( i + 1 ) for i in range( numRounds ) ]
    rowLabels = [ player[ 1 ][ 'name' ] for i, player in enumerate( sortedDivPlayers ) ]

    drawColourChart(
        colors, numRounds, len( sortedDivPlayers ), colLabels, rowLabels, playerMatrix, f"appearances.{div}", sortedDivPlayers,
        div
    )

print( "Complete" )
