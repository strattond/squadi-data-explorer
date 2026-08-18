import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from stats import maxMatches


def figure_for_resolution( width_px, height_px, dpi=100 ):
  return plt.subplots( figsize=( width_px / dpi, height_px / dpi ), dpi=dpi )


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


def drawColourChart(
    colors, numCols: int, numRows: int, colLabels: list, rowLabels: list, dataMatrix, filename: str, rowData, div: str, plotBase: str
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

