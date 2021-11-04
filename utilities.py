'''
Provide a number of utility Python functions that can de-clutter
the Jupyter notebooks that use them.
'''

# Import libraries
import pdb
import os 
import csv
import datetime
import pandas as pd
import geopandas   
import numpy as np
import matplotlib.pyplot as plt
import urllib
import seaborn as sns

import folium
from folium.plugins import FastMarkerCluster

import ipywidgets as widgets
from ipywidgets import interact, interactive, fixed, interact_manual, Layout
from IPython.display import display

from ECHO_modules.get_data import get_echo_data
from ECHO_modules.geographies import region_field, states

# Set up some default parameters for graphing
from matplotlib import cycler
colour = "#00C2AB" # The default colour for the barcharts
colors = cycler('color',
                ['#4FBBA9', '#E56D13', '#D43A69',
                 '#25539f', '#88BB44', '#FFBBBB'])
plt.rc('axes', facecolor='#E6E6E6', edgecolor='none',
       axisbelow=True, grid=True, prop_cycle=colors)
plt.rc('grid', color='w', linestyle='solid')
plt.rc('xtick', direction='out', color='gray')
plt.rc('ytick', direction='out', color='gray')
plt.rc('patch', edgecolor='#E6E6E6')
plt.rc('lines', linewidth=2)
font = {'family' : 'DejaVu Sans',
        'weight' : 'normal',
        'size'   : 16}
plt.rc('font', **font)
plt.rc('legend', fancybox = True, framealpha=1, shadow=True, borderpad=1)

# Styles for States ("other") and selected regions (e.g. Zip Codes) - "this"
style = {'this': {'fillColor': '#0099ff', 'color': '#182799', "weight": 1},
'other': {'fillColor': '#FFA500', 'color': '#182799', "weight": 1}}

def fix_county_names( in_counties ):
    '''
    ECHO_EXPORTER has counties listed both as ALAMEDA and ALAMEDA COUNTY, seemingly
    for every county.  We drop the 'COUNTY' so they only get listed once.

    Parameters
    ----------
    in_counties : list of county names (str)

    Returns
    -------
    list
        The list of counties without duplicates
    '''

    counties = []
    for county in in_counties:
        if (county.endswith( ' COUNTY' )):
            county = county[:-7]
        counties.append( county.strip() )
    counties = np.unique( counties )
    return counties


def show_region_type_widget():
    '''
    Create and return a dropdown list of types of regions

    Returns
    -------
    widget
        The dropdown widget with the list of regions
    '''

    style = {'description_width': 'initial'}
    select_region_widget = widgets.Dropdown(
        options=region_field.keys(),
        style=style,
        value='County',
        description='Region of interest:',
        disabled=False
    )
    display( select_region_widget )
    return select_region_widget


def show_state_widget():
    '''
    Create and return a dropdown list of states

    Returns
    -------
    widget
        The dropdown widget with the state list
    '''

    dropdown_state=widgets.Dropdown(
        options=states,
        description='State:',
        disabled=False,
    )
    
    display( dropdown_state )
    return dropdown_state


def show_pick_region_widget( type, state_widget=None ):
    '''
    Create and return a dropdown list of regions appropriate
    to the input parameters

    Parameters
    ----------
    type : str
        The type of region
    state_widget : widget
        The widget in which a state may have been selected

    Returns
    -------
    widget
        The dropdown widget with region choices
    '''

    region_widget = None
    
    if ( type != 'Zip Code' ):
        if ( state_widget is None ):
            print( "You must first choose a state." )
            return
        my_state = state_widget.value
    
    if ( type == 'Zip Code' ):
        region_widget = widgets.Text(
            value='98225',
            description='Zip Code:',
            disabled=False
        )
    elif ( type == 'County' ):
        df = pd.read_csv( 'ECHO_modules/state_counties.csv' )
        counties = df[df['FAC_STATE'] == my_state]['FAC_COUNTY']
        region_widget=widgets.SelectMultiple(
            options=fix_county_names( counties ),
            description='County:',
            disabled=False
        )
    elif ( type == 'Congressional District' ):
        df = pd.read_csv( 'ECHO_modules/state_cd.csv' )
        cds = df[df['FAC_STATE'] == my_state]['FAC_DERIVED_CD113']
        region_widget=widgets.SelectMultiple(
            options=cds.to_list(),
            description='District:',
            disabled=False
        )
    if ( region_widget is not None ):
        display( region_widget )
    return region_widget


def get_regions_selected( region_type, region_widget ):
    '''
    The region_widget may have multiple selections.  
    Depending on its region_type, extract the selections
    and return them.

    Parameters
    ----------
    region_type : string
        'Zip Code', 'Congressional District', 'County'
   
    region_widget : widget
        The widget that will contain the selections.

    Returns
    -------
    list
        The selections
    '''

    selections = list()
    if ( region_type == 'Zip Code' ):
        selections = region_widget.value.split(',')
    else:
        selections = list( region_widget.value )

    return selections


def show_data_set_widget( data_sets ):
    '''
    Create and return a dropdown list of data sets with appropriate
    flags set in the echo_data.

    Parameters
    ----------
    data_sets : dict
        The data sets, key = name, value = DataSet object

    Returns
    -------
    widget
        The widget with data set choices
    '''
    
    data_set_choices = list( data_sets.keys() )
    
    data_set_widget=widgets.Dropdown(
        options=list(data_set_choices),
        description='Data sets:',
        disabled=False,
    ) 
    display(data_set_widget)
    return data_set_widget


def show_fac_widget( fac_series ):
    '''
    Create and return a dropdown list of facilities from the 
    input Series

    Parameters
    ----------
    fac_series : Series
        The facilities to be shown.  It may have duplicates.

    Returns
    -------
    widget
        The widget with facility names
    '''

    fac_list = fac_series.dropna().unique()
    fac_list.sort()
    style = {'description_width': 'initial'}
    widget=widgets.SelectMultiple(
        options=fac_list,
        style=style,
        layout=Layout(width='70%'),
        description='Facility Name:',
        disabled=False,
    )
    display(widget)
    return widget


def get_active_facilities( state, region_type, regions_selected ):
    '''
    Get a Dataframe with the ECHO_EXPORTER facilities with FAC_ACTIVE_FLAG
    set to 'Y' for the region selected.

    Parameters
    ----------
    state : str
        The state, which could be None
    region_type : str
        The type of region:  'State', 'Congressional District', etc.
    regions_selected : list
        The selected regions of the specified region_type

    Returns
    -------
    Dataframe
        The active facilities returned from the database query
    '''
    
    if ( region_type == 'State' ):
        sql = 'select * from "ECHO_EXPORTER" where "FAC_STATE" = \'{}\''
        sql += ' and "FAC_ACTIVE_FLAG" = \'Y\''
        sql = sql.format( state )
        df_active = get_echo_data( sql, 'REGISTRY_ID' )
    elif ( region_type == 'Congressional District'):
        cd_str = ",".join( map( lambda x: str(x), regions_selected ))
        sql = 'select * from "ECHO_EXPORTER" where "FAC_STATE" = \'{}\''
        sql += ' and "FAC_DERIVED_CD113" in ({})'
        sql += ' and "FAC_ACTIVE_FLAG" = \'Y\''
        sql = sql.format( state, cd_str )
        df_active = get_echo_data( sql, 'REGISTRY_ID' )
    elif ( region_type == 'County' ):
        # Single items in a list will have a comma at the end that trips up
        # the query.  Convert the regions_selected list to a string.
        regions = "'" + "','".join( regions_selected ) + "'"

        sql = 'select * from "ECHO_EXPORTER" where "FAC_STATE" = \'{}\''
        sql += ' and "FAC_COUNTY" in ({})'
        sql += ' and "FAC_ACTIVE_FLAG" = \'Y\''
        sql = sql.format( state, regions )
        df_active = get_echo_data( sql, 'REGISTRY_ID' )
    elif ( region_type == 'Zip Code' ):
        sql = 'select * from "ECHO_EXPORTER" where "FAC_ZIP" = \'{}\''
        sql += ' and "FAC_ACTIVE_FLAG" = \'Y\''
        sql = sql.format( regions_selected )
        df_active = get_echo_data( sql, 'REGISTRY_ID' )
    else:
        df_active = None
    return df_active


def aggregate_by_facility(data, program, df_active):
    '''
    Definition
    data  = program data
    program = program object
    df_active = a df generated from previous cells of all fac active in the selected regions
    '''
    
    diff = None

    def differ(input, program):
      '''
      helper function to sort facilities in this program (input) from the full list of faciliities regulated under the program
      '''
      diff = list(
          set(df_active[program.echo_type + "_IDS"]) - set(input[program.idx_field])
          ) 
      
      # get rid of NaNs - probably no program IDs
      diff = [x for x in diff if str(x) != 'nan']
      
      # ^ Not perfect given that some facilities have multiple NPDES_IDs
      # Below return the full ECHO_EXPORTER details for facilities without violations, penalties, or inspections
      diff = df_active.loc[df_active[program.echo_type + "_IDS"].isin(diff)] 
      return diff

    if (program.name == "CWA Violations"): 
      year = data["YEARQTR"].astype("str").str[0:4:1]
      data["YEARQTR"] = year
      data["sum"] = data["NUME90Q"] + data["NUMCVDT"] + data['NUMSVCD'] + data["NUMPSCH"]
      data = data.groupby([program.idx_field, "FAC_NAME", "FAC_LAT", "FAC_LONG"]).sum()
      data = data.reset_index()
      data = data.loc[data["sum"] > 0] # only symbolize facilities with violations
      diff = differ(data, program)
      aggregator = "sum" # keep track of which field we use to aggregate data, which may differ from the preset

    # Penalties
    elif (program.name == "CAA Penalties" or program.name == "RCRA Penalties" or program.name == "CWA Penalties" ):
      data.rename( columns={ program.date_field: 'Date', program.agg_col: 'Amount'}, inplace=True )
      if ( program.name == "CWA Penalties" ):
        data['Amount'] = data['Amount'].fillna(0) + data['STATE_LOCAL_PENALTY_AMT'].fillna(0)
      data = data.groupby([program.idx_field, "FAC_NAME", "FAC_LAT", "FAC_LONG"]).agg({'Amount':'sum'})
      data = data.reset_index()
      data = data.loc[data["Amount"] > 0] # only symbolize facilities with penalties
      diff = differ(data, program)
      aggregator = "Amount" # keep track of which field we use to aggregate data, which may differ from the preset

    # Air emissions

    # Inspections, violations
    else: 
      data = data.groupby([program.idx_field, "FAC_NAME", "FAC_LAT", "FAC_LONG"]).agg({program.date_field: 'count'})
      data['count'] = data[program.date_field]
      data = data.reset_index()
      data = data.loc[data["count"] > 0] # only symbolize facilities with X
      diff = differ(data, program)
      aggregator = "count" # ??? keep track of which field we use to aggregate data, which may differ from the preset
      
    if ( len(data) > 0 ):
      return {"data": data, "diff": diff, "aggregator": aggregator}
    else:
      print( "There is no data for this program and region after 2000." )


def marker_text( row, no_text ):
    '''
    Create a string with information about the facility or program instance.

    Parameters
    ----------
    row : Series
        Expected to contain FAC_NAME and DFR_URL fields from ECHO_EXPORTER
    no_text : Boolean
        If True, don't put any text with the markers, which reduces chance of errors 

    Returns
    -------
    str
        The text to attach to the marker
    '''

    text = ""
    if ( no_text ):
        return text
    if ( type( row['FAC_NAME'] == str )) :
        try:
            text = row["FAC_NAME"] + ' - '
        except TypeError:
            print( "A facility was found without a name. ")
        if 'DFR_URL' in row:
            text += " - <p><a href='"+row["DFR_URL"]
            text += "' target='_blank'>Link to ECHO detailed report</a></p>" 
    return text


def check_bounds( row, bounds ):
    '''
    See if the FAC_LAT and FAC_LONG of the row are interior to
    the minx, miny, maxx, maxy of the bounds.

    Parameters
    ----------
    row : Series
    Must contain FAC_LAT and FAC_LONG
    bounds : Dataframe
    Bounding rectangle--minx,miny,maxx,maxy

    Returns
    -------
    True if the row's point is in the bounds
    '''

    if ( row['FAC_LONG'] < bounds.minx[0] or row['FAC_LAT'] < bounds.miny[0] \
         or row['FAC_LONG'] > bounds.maxx[0] or row['FAC_LAT'] > bounds.maxy[0]):
        return False
    return True


def mapper(df, bounds=None, no_text=False):
    '''
    Display a map of the Dataframe passed in.
    Based on https://medium.com/@bobhaffner/folium-markerclusters-and-fastmarkerclusters-1e03b01cb7b1

    Parameters
    ----------
    df : Dataframe
        The facilities to map.  They must have a FAC_LAT and FAC_LONG field.
    bounds : Dataframe
        A bounding rectangle--minx, miny, maxx, maxy.  Discard points outside.

    Returns
    -------
    folium.Map
    '''

    # Initialize the map
    m = folium.Map(
        location = [df.mean()["FAC_LAT"], df.mean()["FAC_LONG"]]
    )

    # Create the Marker Cluster array
    #kwargs={"disableClusteringAtZoom": 10, "showCoverageOnHover": False}
    mc = FastMarkerCluster("")
 
    # Add a clickable marker for each facility
    for index, row in df.iterrows():
        if ( bounds is not None ):
            if ( not check_bounds( row, bounds )):
                continue
        mc.add_child(folium.CircleMarker(
            location = [row["FAC_LAT"], row["FAC_LONG"]],
            popup = marker_text( row, no_text ),
            radius = 8,
            color = "black",
            weight = 1,
            fill_color = "orange",
            fill_opacity= .4
        ))
    
    m.add_child(mc)
    
    bounds = m.get_bounds()
    m.fit_bounds(bounds)

    # Show the map
    return m

def point_mapper(df, aggcol, quartiles=False, other_fac=None, basemap=None):
  '''
  Display a point symbol map of the Dataframe passed in. A point symbol map represents 
  each facility as a point, with the size of the point scaled to the data value 
  (e.g. inspections, violations) proportionally or through quartiles.
  Parameters
  ----------
  df : Dataframe
      The facilities to map. They must have a FAC_LAT and FAC_LONG field.
      This Dataframe should
      already be aggregated by facility e.g.:
      NPDES_ID  violations  FAC_LAT FAC_LONG
      NY12345   13          43.03   -73.92
      NY54321   2           42.15   -80.12
      ...
  aggcol : String
      The name of the field in the Dataframe that has been aggregated. This is
      used for the legend (pop-up window on the map)
  quartiles : Boolean
      False (default) returns a proportionally-scaled point symbol map, meaning
      that the radius of each point is directly scaled to the value (e.g. 13 violations)
      True returns a graduated point symbol map, meaning that the radius of each 
      point is a function of the splitting the Dataframe into quartiles. 
  other_fac : Dataframe
      Other regulated facilities without violations, inspections,
      penalties, etc. - whatever the value being mapped is. This is an optional 
      variable enabling further context to the map. They must have a FAC_LAT and FAC_LONG field.
  basemap : Dataframe
      Should be a spatial dataframe from get_spatial_data that can be mapped
      
  Returns
  -------
  folium.Map
  '''
  if ( df is not None ):

    map_of_facilities = folium.Map()
   
    if quartiles == True:
      df['quantile'] = pd.qcut(df[aggcol], 4, labels=False, duplicates="drop")
      scale = {0: 8,1:12, 2: 16, 3: 24} # First quartile = size 8 circles, etc.

    # add basemap (selected regions)
    if (basemap is not None):
      b = folium.GeoJson(
        basemap,
        style_function = lambda x: style['this']
      ).add_to(map_of_facilities)

    # Add a clickable marker for each facility with info
    for index, row in df.iterrows():
      if quartiles == True:
        r = scale[row["quantile"]]
      else:
        r = row[aggcol]
      map_of_facilities.add_child(folium.CircleMarker(
        location = [row["FAC_LAT"], row["FAC_LONG"]],
        popup = marker_text( row, False ) + "<p>" + aggcol + ": "+str(row[aggcol]),
        radius = r * 2, # arbitrary scalar
        color = "black",
        weight = 1,
        fill_color = "orange",
        fill_opacity= .4
      ))
    
    # add other facilities
    if ( other_fac is not None ):
      for index, row in other_fac.iterrows():
        map_of_facilities.add_child(folium.CircleMarker(
          location = [row["FAC_LAT"], row["FAC_LONG"]],
          popup = marker_text( row, False ),
          radius = 4,
          color = "black",
          weight = 1,
          fill_color = "black",
          fill_opacity= 1
        ))
    
    # check and fit bounds
    bounds = map_of_facilities.get_bounds()
    map_of_facilities.fit_bounds(bounds)

    return map_of_facilities

  else:
    print( "There are no facilities to map." ) 

def show_map(regions, states, region_type, spatial_tables):
    '''
    # show the map of just the regions (e.g. zip codes) and the selected state(s)
    # create the map using a library called Folium (https://github.com/python-visualization/folium)
    '''
    map = folium.Map()  

    # Show the state(s)
    s = folium.GeoJson(
      states,
      name = "State",
      style_function = lambda x: style['other']
    ).add_to(map)
    folium.GeoJsonTooltip(fields=["stusps"]).add_to(s)

    # Show the intersection regions (e.g. Zip Codes)
    m = folium.GeoJson(
      regions,
      name = region_type,
      style_function = lambda x: style['this']
    ).add_to(map)
    folium.GeoJsonTooltip(fields=[spatial_tables[region_type]["id_field"].lower()]).add_to(m) # Add tooltip for identifying features

    # compute boundaries so that the map automatically zooms in
    bounds = m.get_bounds()
    map.fit_bounds(bounds, padding=0)

    # display the map!
    display(map)

def selector(units):
    '''
    helper function for `get_spatial_data`
    helps parse out multiple inputs into a SQL format
    e.g. takes a list ["AL", "AK", "AR"] and returns the string ("AL", "AK", "AR")
    '''
    selection = '('
    if (type(units) == list):
      for place in units:
          selection += '\''+str(place)+'\', '
      selection = selection[:-2] # remove trailing comma
      selection += ')'
    else:
      selection = '(\''+str(units)+'\')'
    return selection

def get_spatial_data(region_type, states, spatial_tables):
    '''
    returns spatial data from the database utilizing an intersection query 
    e.g. return watersheds based on whether they cross the selected state

    region_type = "Congressional District" # from cell 3 region_type_widget
    states = ["AL"]  # from cell 2 state dropdown selection. 
    states variable has ability to be expanded to multiple state selection.
    spatial_tables is from ECHO_modules/geographies.py
    '''

    def sqlizer(query):
      '''
      takes template sql and injects a query into it to return geojson-formatted geo data
      '''
      #develop sql
      sql = """
        SELECT jsonb_build_object(
            'type', 'FeatureCollection', 'features', jsonb_agg(features.feature)
        )
        FROM (
            SELECT jsonb_build_object(
                'type', 'Feature','id', gid, 'geometry',
                ST_AsGeoJSON(geom)::jsonb,'properties',
                to_jsonb(inputs) - 'gid' - 'geom'
            ) feature
            FROM ( 
              """+query+"""
            ) inputs
        ) features;
      """

      url = 'http://portal.gss.stonybrook.edu/echoepa/index2.php?query=' 
      data_location = url + urllib.parse.quote_plus(sql) + '&pg'
      #print(data_location) # Debugging
      #print(sql) # Debugging
      result = geopandas.read_file(data_location)
      return result
    
    # Get the regions of interest (watersheds, zips, etc.) based on their intersection with the state(s)
    selection = selector(states)
    #print(selection) # Debugging
    query = """
      SELECT this.* 
      FROM """ + spatial_tables[region_type]['table_name'] + """ AS this
      JOIN """ + spatial_tables["State"]['table_name'] + """ AS other 
      ON other.""" + spatial_tables["State"]['id_field'] + """ IN """ + selection + """ 
      AND ST_Within(this.geom,other.geom) """
    regions = sqlizer(query)

    # Get the intersecting geo (i.e. states)
    query = """
      SELECT * 
      FROM """ + spatial_tables["State"]['table_name'] + """
      WHERE """ + spatial_tables["State"]['id_field'] + """ IN """ + selection + ""
    states = sqlizer(query) #reset intersecting_geo to its spatial data

    return regions, states
    # send results to the show_map function to display
    #show_map(regions, states, region_type, spatial_tables)

def write_dataset( df, base, type, state, regions ):
    '''
    Write out a file of the Dataframe passed in.

    Parameters
    ----------
    df : Dataframe
        The data to write.
    base: str
        A base string of the file to write
    type: str
        The region type of the data
    state: str
        The state, or None
    regions: list
        The region identifiers, e.g. CD number, County, State, Zip code
    '''
    if ( df is not None and len( df ) > 0 ):
        if ( not os.path.exists( 'CSVs' )):
            os.makedirs( 'CSVs' )
        filename = 'CSVs/' + base[:50]
        if ( type != 'Zip Code' ):
            filename += '-' + state
        filename += '-' + type
        if ( regions is not None ):
            for region in regions:
                filename += '-' + str(region)
        filename = urllib.parse.quote_plus(filename, safe='/')
        filename += '.csv'
        df.to_csv( filename ) 
        print( "Wrote " + filename )
    else:
        print( "There is no data to write." )


def make_filename( base, type, state, region, filetype='csv' ):
    '''
    Make a filename from the parameters and return it.
    The filename will be in the Output directory relative to
    the current working directory, and in a sub-directory
    built out of the state and CD.

    Parameters
    ----------
    base : str
        A base string of the file
    type : str
        The region type
    state : str
        The state or None
    region : str
        The region
    filetype : str
        Optional file suffix.

    Returns
    -------
    str
        The filename created.

    Examples
    --------
    >>> filename = make_filename( 'noncomp_CWA_pg6', *df_type )
    '''
    # If type is 'State', the state name is the region.
    dir = 'Output/'
    if ( type == 'State' ):
        dir += region
        filename = base + '_' + region
    else:
        dir += state
        filename = base + '_' + state
        if ( region is not None ):
            dir += str(region)
            filename += '-' + str(region)
    x = datetime.datetime.now()
    filename += '-' + x.strftime( "%m%d%y") +'.' + filetype
    dir += '/'
    if ( not os.path.exists( dir )):
        os.makedirs( dir )
    return dir + filename


def get_top_violators( df_active, flag, noncomp_field, action_field, num_fac=10 ):
    '''
    Sort the dataframe and return the rows that have the most number of
    non-compliant quarters.

    Parameters
    ----------
    df_active : Dataframe
        Must have ECHO_EXPORTER fields
    flag : str
        Identifies the EPA programs of the facility (AIR_FLAG, NPDES_FLAG, etc.)
    noncomp_field : str
        The field with the non-compliance values, 'S' or 'V'.
    action_field
        The field with the count of quarters with formal actions
    num_fac
        The number of facilities to include in the returned Dataframe

    Returns
    -------
    Dataframe
        The top num_fac violators for the EPA program in the region

    Examples
    --------
    >>> df_violators = get_top_violators( df_active, 'AIR_FLAG',
        'CAA_3YR_COMPL_QTRS_HISTORY', 'CAA_FORMAL_ACTION_COUNT', 20 )
    '''
    df = df_active.loc[ df_active[flag] == 'Y' ]
    if ( len( df ) == 0 ):
        return None
    df_active = df.copy()
    noncomp = df_active[ noncomp_field ]
    noncomp_count = noncomp.str.count('S') + noncomp.str.count('V')
    df_active['noncomp_count'] = noncomp_count
    df_active = df_active[['FAC_NAME', 'noncomp_count', action_field,
            'DFR_URL', 'FAC_LAT', 'FAC_LONG']]
    df_active = df_active[df_active['noncomp_count'] > 0]
    df_active = df_active.sort_values( by=['noncomp_count', action_field], 
            ascending=False )
    df_active = df_active.head( num_fac )
    return df_active   

def chart_top_violators( ranked, state, selections, epa_pgm ):
    '''
    Draw a horizontal bar chart of the top non-compliant facilities.

    Parameters
    ----------
    ranked : Dataframe
        The facilities to be charted
    state : str
        The state
    selections : list
        The selections
    epa_pgm : str
        The EPA program associated with this list of non-compliant facilities

    Returns
    -------
    seaborn.barplot
        The graph that is generated
    '''
    if ranked is None:
        print( 'There is no {} data to graph.'.format( epa_pgm ))
        return None
    unit = ranked.index 
    values = ranked['noncomp_count'] 
    if ( len(values) == 0 ):
        return "No {} facilities with non-compliant quarters in {} - {}".format(
            epa_pgm, state, str( selections ))
    
    sns.set(style='whitegrid')
    fig, ax = plt.subplots(figsize=(10,10))
    #cmap = sns.color_palette("rocket", as_cmap=True)
    #barplot_colors = [cmap(c) for c in values]

    try:
        g = sns.barplot(x=values, y=unit, order=list(unit), orient="h", palette="rocket") 
        g.set_title('{} facilities with the most non-compliant quarters in {} - {}'.format( 
                epa_pgm, state, str( selections )))
        ax.set_xlabel("Non-compliant quarters")
        ax.set_ylabel("Facility")
        ax.set_yticklabels(ranked["FAC_NAME"])
        return ( g )
    except TypeError as te:
        print( "TypeError: {}".format( str(te) ))
        return None
