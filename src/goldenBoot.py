import matplotlib.pyplot as plt
import re
import json
import numpy as np
from PIL import Image, ImageDraw


def figure_for_resolution( width_px, height_px, dpi=100 ):
  return plt.subplots( figsize=( width_px / dpi, height_px / dpi ), dpi=dpi )


def running( prev_list, index, value ):
  return value if index == 0 else prev_list[ index - 1 ] + value


def cumulative( values ):
  total = 0
  out = []
  for v in values:
    total += v
    out.append( total )
  return out


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

  return sorted( all_divisions, key=naturalDivKey )


def maxMatches( data ):
  return max( len( d.get( "matches", [] ) ) for d in data )


def highestRoundsInAnyDiv( player ):
  return max( len( player[ 'divGoals' ][ d ] ) for d in player[ 'divGoals' ] )


def accumulateStats( data ):

  player_stats = {}
  cumRounds = maxMatches( data )
  for division in data:
    divName = division[ "div" ][ 'name' ]
    matchNum = 0
    for match in division.get( "matches", [] ):
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
                "byDiv": {},  # divName -> count,
                "runningGoals": [],
                "runningYellows": [],
                "runningReds": [],
                "runningFairPlay": [],
                "divGoals": {},
                "divYellows": {},
                "divReds": {},
                "divFairPlay": {},
                "starts": 0
            }
        )

        # appearances
        stats[ "appearances" ] += 1
        stats[ "byDiv" ][ divName ] = ( stats[ "byDiv" ].get( divName, 0 ) + 1 )

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

        divGoals = stats[ "divGoals" ].setdefault( divName, [] )
        divGoals.append( roundGoals )
        divYellows = stats[ "divYellows" ].setdefault( divName, [] )
        divYellows.append( roundYellows )
        divReds = stats[ "divReds" ].setdefault( divName, [] )
        divReds.append( roundReds )
        divFairPlay = stats[ "divFairPlay" ].setdefault( divName, [] )
        divFairPlay.append( ( roundYellows + 2*roundReds ) )

      matchNum += 1

  for name in player_stats:
    p = player_stats[ name ]
    playerRounds = highestRoundsInAnyDiv( p )
    for i in range( 0, playerRounds ):  # was cumRounds - 1
      goalsThisRound = 0
      yellowsThisRound = 0
      redsThisRound = 0
      fairPlayThisRound = 0
      anyGoals = False
      anyCards = False
      for division in data:
        divName = division[ "div" ][ 'name' ]
        if divName in p[ "divGoals" ]:
          divArr = p[ "divGoals" ][ divName ]
          divGoal = ( divArr[ i ] if i < len( divArr ) else 0 )
          goalsThisRound += divGoal
          anyGoals = True
        if divName in p[ "divYellows" ]:
          divArr = p[ "divYellows" ][ divName ]
          divCard = ( divArr[ i ] if i < len( divArr ) else 0 )
          yellowsThisRound += divCard
          anyCards = True
        if divName in p[ "divReds" ]:
          divArr = p[ "divReds" ][ divName ]
          divCard = ( divArr[ i ] if i < len( divArr ) else 0 )
          redsThisRound += divCard
          anyCards = True
        if divName in p[ "divFairPlay" ]:
          divArr = p[ "divFairPlay" ][ divName ]
          divCard = ( divArr[ i ] if i < len( divArr ) else 0 )
          fairPlayThisRound += divCard
          anyCards = True

      if anyGoals:
        p[ "runningGoals" ].append( running( p[ "runningGoals" ], i, goalsThisRound ) )
      if anyCards:
        p[ "runningYellows" ].append( running( p[ "runningYellows" ], i, yellowsThisRound ) )
        p[ "runningReds" ].append( running( p[ "runningReds" ], i, redsThisRound ) )
        p[ "runningFairPlay" ].append( running( p[ "runningFairPlay" ], i, fairPlayThisRound ) )

  return player_stats


def plotStatsData( data, filename, sorted_stats, property, maxProp, labelY, title, withStep=False ):
  fig, ax = figure_for_resolution( 6000, 4000, dpi=100 )

  # Transparent backgrounds
  fig.patch.set_alpha( 0 )
  ax.patch.set_alpha( 0 )

  for i, ( name, value ) in enumerate( sorted_stats ):
    jitter = i * 0.03
    color = ax._get_lines.get_next_color()
    cumRounds = highestRoundsInAnyDiv( value )
    rangeData = range( 1, cumRounds + 1 )
    if withStep:
      ax.step( rangeData, [ g + jitter for g in value[ property ] ], where="post", linewidth=25, color=color )
    ax.plot(
        rangeData, [ g + jitter for g in value[ property ] ],
        marker="o",
        markersize=50,
        linewidth=25,
        label=name,
        color=color
    )
  #
  cumRounds = maxMatches( data )
  rangeData = range( 1, cumRounds + 1 )
  maxStat = ( sorted_stats[ 0 ][ 1 ] )[ maxProp ]
  maxStatRange = range( 0, maxStat + 1 )
  ax.set_title( title, fontsize=320, color="white" )
  ax.set_xlabel( "Round", fontsize=56, color="white" )
  ax.set_ylabel( labelY, fontsize=56, color="white" )
  ax.set_ybound( 0, maxStat + 1 )
  ax.grid( True, linestyle="--", alpha=0.4 )
  ax.legend( title="Player", fontsize=56 )
  ax.set_xticks( rangeData )
  ax.set_xticklabels( [ str( r ) for r in rangeData ], fontsize=56 )
  ax.set_yticks( maxStatRange )
  ax.set_yticklabels( maxStatRange, fontsize=56 )
  ax.tick_params( colors="white" )
  #
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
      cell.get_text().set_ha( "left" )
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
    for i, g in enumerate( stats[ "runningGoals" ] ):
      round_totals[ i ] += g - ( stats[ "runningGoals" ][ i - 1 ] if i > 0 else 0 )

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
  return max( stats[ "byDiv" ], key=lambda div: stats[ "byDiv" ][ div ] )


def calcPlayerBorrowStats( stats ):
  primary = playerPrimaryDivision( stats )
  return { div: count for div, count in stats[ "byDiv" ].items() if div != primary }


def totalBorrowings( stats ):
  return sum( calcPlayerBorrowStats( stats ).values() )


def getDiv( data, match ):
  for d in data:
    if d[ 'div' ][ 'name' ] == match:
      return d
  return None


print( "Loading data" )
with open( "output/matchDetails.json", "r" ) as f:
  data = json.load( f )

print( "Getting unique players" )
players = uniquePlayers( data )

print( "Getting divisions" )
divisions = sortedDivisions( data )
print( "Accumulating stats" )
player_stats = accumulateStats( data )

print( "Sorting by Goals" )
topN = sorted(   # sorted_stats
                      (
                        (name, stats)
                        for name, stats in player_stats.items()
                        if stats['goals'] > 2
                      ),
                      key=lambda item: item[1]["goals"], reverse=True)

topN = topN[ :10 ]

print( "Plotting Golden Boot" )
plotStatsData( data, "plots/golden_boot.png", topN, "runningGoals", "goals", "Goals", "Golden Boot Race" )

print( "Sorting by Fair Play" )
sorted_stats = sorted( player_stats.items(), key=lambda item: item[ 1 ][ "fairPlay" ], reverse=True )
topN = sorted_stats[ :5 ]

print( "Plotting Golden Card" )
plotStatsData( data, "plots/golden_card.png", topN, "runningYellows", "yellows", "Cards", "Golden Card Race" )

infographic = getInfographicData( player_stats )

with open( "data/stats.json", "w", encoding="utf-8" ) as f:
  json.dump( infographic, f, indent=2, ensure_ascii=False )

print( "Calculating appearances" )
rows = []
filtered_players = { name: stats for name, stats in player_stats.items() if len( stats[ "byDiv" ] ) >= 2 }

# But we onlny care about "borrowings".  And we can take the punt that a primary team is the one they've appeared in the most
for name, stats in sorted(
    filtered_players.items(), key=lambda item: ( -totalBorrowings( item[ 1 ] ), naturalNameKey( item[ 0 ] ) )
):
  borrowedStats = calcPlayerBorrowStats( stats )
  totalBorrow = totalBorrowings( stats )
  row = [ name, totalBorrow ] + [ borrowedStats.get( div, "" ) for div in divisions ] + [ stats[ "appearances" ] ]
  if totalBorrow > 1:
    rows.append( row )

col_labels = [ "Player", "Borrowed" ] + divisions + [ "Total appearances" ]
col_widths = [ 24, 12 ] + [ 20 ] * len( divisions ) + [ 12 ]
plotRowData( col_labels, rows, "plots/borrowings.png", 1280, 960, 1, 72 )

for label, w in zip( col_labels, col_widths ):
  print( label.ljust( w ), end='' )
print()
for row in rows:
  for value, w in zip( row, col_widths ):
    print( str( value ).ljust( w ), end='' )
  print()

div10players = { name: stats for name, stats in player_stats.items() if playerPrimaryDivision( stats ) == "Metro 10 South" }

sorted10s = sorted( div10players.items(), key=lambda item: item[ 1 ][ "starts" ] )

rows = []
for name, stats in sorted10s:
  row = [ name, stats[ "byDiv" ][ 'Metro 10 South' ], stats[ 'starts' ] ]
  rows.append( row )

col_labels = [ "Player", "Appearances", "Starts" ]
plotRowData( col_labels, rows, "plots/appearances.png", 640, 480, 2 )

print( col_labels[ 0 ].ljust( 24 ) + " " + str( col_labels[ 1 ] ).ljust( 12 ) + str( col_labels[ 2 ] ).ljust( 6 ) )
for row in rows:
  print( row[ 0 ].ljust( 24 ) + " " + str( row[ 1 ] ).ljust( 12 ) + str( row[ 2 ] ).ljust( 6 ) )

sorted10s = sorted( div10players.items(), key=lambda item: item[ 1 ][ "name" ] )
playerNames = [ p[ 1 ][ 'name' ] for p in sorted10s ]
div10 = getDiv( data, 'Metro 10 South' )
if div10 is not None:
  numRounds = len( div10[ 'matches' ] )
  playerMatrix = np.zeros( ( len( sorted10s ), numRounds ) )
  i = 0
  for p in sorted10s:
    for r in range( 0, numRounds ):
      match = div10[ 'matches' ][ r ][ 'match' ]
      didPlay = False
      didStart = False
      for p2 in match[ 'players' ]:
        if p[ 1 ][ 'name' ] == p2[ 'name' ]:
          didPlay = True
          didStart = ( p2[ 'started' ] is not None and p2[ 'started' ] )
          break
      playerMatrix[ i, r ] = ( 2 if didStart else ( 1 if didPlay else 0 ) )
    i += 1

  ## Marker colors for each state
  colors = { 0: "red", 1: "lightgreen", 2: "green"}

  cellW = 30
  cellH = 20
  leftMargin = 150
  topMargin = 50

  imgW = leftMargin + cellW * ( numRounds+1 )
  imgH = topMargin + cellH * ( len( sorted10s ) + 1 )

  img = Image.new( "RGB", ( imgW, imgH ), "white" )
  draw = ImageDraw.Draw( img )

  # Draw circles in each cell
  for i in range( 0, numRounds ):
    x = leftMargin + i*cellW
    draw.text( ( x + cellW//4, 10 ), str( i + 1 ), fill="black" )

  for i, player in enumerate( sorted10s ):
    y = topMargin + i*cellH
    draw.text( ( 10, y + cellH//4 ), player[ 1 ][ 'name' ], fill="black" )
    for j in range( 0, numRounds ):
      x = leftMargin + j*cellW
      state = playerMatrix[ i, j ]

      # Cell border
      draw.rectangle( [ x, y, x + cellW, y + cellH ], outline="black", fill=colors[ state ] )

      # Circle center
      cx = x + cellW//2
      cy = y + cellH//2
      radius = 6

      state = playerMatrix[ i ][ j ]

  img.save( "plots/starts.png" )

print( "Complete" )
