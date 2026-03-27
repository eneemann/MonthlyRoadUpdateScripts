import arcpy
import time
import os

from pathlib import Path

#: Notes before running: verify that these variables are pointing to the correct data (ie: at home vs at work)
    #: python 3
    # sgid_roads

# Start timer and print start time in local time
start_time = time.time()
readable_start = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
print("The script start time is {}".format(readable_start))


#: Variables
sgid_roads = r"C:\GIS Data\Road Network\SGID_20260324.gdb\Roads"    # Path to local copy of SGID roads
SGID = r"C:\Users\emneemann\AppData\Roaming\Esri\ArcGISPro\Favorites\internal@SGID@db.ugrc.utah.sde"    # Path to Pro SGID connection
work_dir = r"C:\GIS Data\Road Network\NetworkDataset\RecentBuilds"  # Path to local working directory
today = time.strftime("%Y%m%d")

#### Create a folder based on the date (ie: Year_Month_Day = 20260324)

folder_name = today
# create the folder
print("Creating Directory...")
today_dir = rf"{work_dir}\{folder_name}"
if not os.path.exists(today_dir):
    print(f"Creating work_dir: {today_dir} ...")
    os.makedirs(today_dir)
else:
    print(f"Directory: {today_dir} exists.")


# create new fgdb
print("Creating File Geodatabase...")
network_fgdb = rf'{today_dir}\UtahRoadsNetworkAnalysis.gdb'
if not arcpy.Exists(network_fgdb):
    network_fgdb = arcpy.management.CreateFileGDB(today_dir, 'UtahRoadsNetworkAnalysis.gdb')
network_fgdb_dataset = Path(rf'{today_dir}\UtahRoadsNetworkAnalysis.gdb\NetworkDataset')
network_fgdb_path = Path(rf'{today_dir}\UtahRoadsNetworkAnalysis.gdb')

# main function
def main():
    # create dataset in the fgdb
    print("Creating Feature Dataset...")
    if not arcpy.Exists(rf"{network_fgdb}\NetworkDataset"):
        arcpy.management.CreateFeatureDataset(network_fgdb, 'NetworkDataset', sgid_roads)

    # import the sgid roads fc
    print("Importing SGID Roads ...")
    #expression = "ZIPCODE_L in ('84108', '84106', '84105')" ##TESTING STUFF##
    out_roads = rf"{network_fgdb_dataset}\Roads"
    # network_roads = arcpy.FeatureClassToFeatureClass_conversion(sgid_roads, str(network_fgdb) + r'/NetworkDataset', 'Roads', expression)
    network_roads = arcpy.conversion.ExportFeatures(sgid_roads, out_roads)


    ## add the needed fields ##
    print("Add needed network fields to fgdb road data")
    arcpy.management.AddField(network_roads,"NETSUBTYPE", "SHORT", "","","")
    arcpy.management.AddField(network_roads,"USEEXIST", "TEXT", "","","1")
    arcpy.management.AddField(network_roads,"URBTRAFFIC", "TEXT", "","","1")
    arcpy.management.AddField(network_roads,"EXCL_WALK", "TEXT", "","","1")
    arcpy.management.AddField(network_roads,"IMPED_MIN","DOUBLE","6","2")
    arcpy.management.AddField(network_roads,"F_T_IMP_MIN","DOUBLE","6","2")
    arcpy.management.AddField(network_roads,"T_F_IMP_MIN","DOUBLE","6","2")
    arcpy.management.AddField(network_roads,"IMPED_PED","DOUBLE","6","2")
    #arcpy.management.AddField(network_roads,"STARTX","DOUBLE","7","1")  # add geometry attributes below, instead
    #arcpy.management.AddField(network_roads,"ENDX","DOUBLE","7","1")  # add geometry attributes below, instead
    #arcpy.management.AddField(network_roads,"STARTY","DOUBLE","7","1")  # add geometry attributes below, instead
    #arcpy.management.AddField(network_roads,"ENDY","DOUBLE","7","1")  # add geometry attributes below, instead
    #arcpy.CalculateGeometryAttributes_management(network_roads, [["STARTX", "LINE_START_X"], ["ENDX", "LINE_END_X"]])  # add geometry attributes below, instead

    ## Add geometry fields with start and end XY values ##
    # but, do this for only limited access roads
    arcpy.management.MakeFeatureLayer(network_roads, 'network_roads_lyr', "DOT_HWYNAM <> ''")
    arcpy.management.AddGeometryAttributes('network_roads_lyr', "LINE_START_MID_END")
    arcpy.management.Delete('network_roads_lyr')


    ## create the needed scratch data (ie: the urban areas) and assign the segments that intersect the urban boundaries with an URBTRAFFIC = Yes or No ##
    urban_areas = generate_scratch_data(today_dir)   
    #arcpy.management.MakeFeatureLayer(urban_areas, 'urban_areas_lyr')
    print("Calculate URBTRAFFIC field...")
    arcpy.management.MakeFeatureLayer(network_roads, 'network_roads_lyr')
    urban_roads_selected = arcpy.management.SelectLayerByLocation('network_roads_lyr', 'intersect', urban_areas)
    # Replace a layer/table view name with a path to a dataset (which can be a layer file) or create the layer/table view within the script
    arcpy.management.CalculateField(urban_roads_selected, field="URBTRAFFIC", expression='"Y"')
    # calculate the segments that were not in an urban area to "N"
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "URBTRAFFIC is NULL")
    arcpy.management.CalculateField(urban_roads_selected, field="URBTRAFFIC", expression='"N"')
  

    ## begin calculating the field values ##
    ## USEEXIST ##
    print("Calculate USEEXIST fields...")
    # Yes    
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "not (SPEED_LMT is null) and ( SPEED_LMT >= 5 and SPEED_LMT <= 80)")
    arcpy.management.CalculateField(urban_roads_selected, field="USEEXIST", expression='"Y"')
    # No - also set SPEED_LMT to 25 for these records as well
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "USEEXIST is null or USEEXIST <> '1'")
    arcpy.management.CalculateField(urban_roads_selected, field="USEEXIST", expression='"N"')
    arcpy.management.CalculateField(urban_roads_selected, field="SPEED_LMT", expression='25')

    ## SPEED_LMT ##
    print("Calculate speed limits...")
    # 70 mph - UDOT limited access highway and freeways
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "CARTOCODE = '1' OR ((DOT_RTNAME = '0201P' OR DOT_RTNAME = '0201N') and CARTOCODE = '4') OR CARTOCODE = '2'")
    arcpy.management.CalculateField(urban_roads_selected, field="SPEED_LMT", expression='70')

    # 65 mph - major state and US highways
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "(CARTOCODE = '2' OR CARTOCODE = '3' OR CARTOCODE = '4' OR CARTOCODE = '5') AND USEEXIST = 'N'")
    arcpy.management.CalculateField(urban_roads_selected, field="SPEED_LMT", expression='65')

    # 55 mph - UDOT freeway collectors/feeders
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "DOT_RTNAME like '%C%' and (USEEXIST is null or USEEXIST <> 'Y')")
    arcpy.management.CalculateField(urban_roads_selected, field="SPEED_LMT", expression='55')

    # 40 mph - UDOT ramps
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "DOT_RTNAME like '%R%' and (USEEXIST is null or USEEXIST <> 'Y')")
    arcpy.management.CalculateField(urban_roads_selected, field="SPEED_LMT", expression='40')

    # 50 mph - invalid speeds on major local roads
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "(USEEXIST is null or  USEEXIST <> 'Y') AND ( CARTOCODE = '8')")
    arcpy.management.CalculateField(urban_roads_selected, field="SPEED_LMT", expression='55')

    # 45 mph - unpaved major roads
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "(USEEXIST is null or  USEEXIST <> 'Y') AND ( CARTOCODE = '9')")
    arcpy.management.CalculateField(urban_roads_selected, field="SPEED_LMT", expression='45')


    # downgrade speeds all non-divided major local and major highways in the urban buffer to 40 mph.  However, exclude Timp Highway, MountainView, Legacy, Bangerter Highway and fast portion of US 89 in Davis County
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "(CARTOCODE = '2' OR CARTOCODE = '3' OR CARTOCODE = '4' OR CARTOCODE = '5' OR CARTOCODE = '8' OR CARTOCODE = '9') AND URBTRAFFIC = 'Y' AND NOT (DOT_RTNAME = '0201P' OR DOT_RTNAME = '0201N' OR DOT_RTNAME = '0154P' or DOT_RTNAME = '0154N' OR DOT_RTNAME = '0085P' or DOT_RTNAME = '0085N' or (DOT_RTNAME Like '0%' and (CARTOCODE = '2' or CARTOCODE = '4')) or DOT_RTNAME LIKE '0092PC%' or DOT_RTNAME LIKE '0092NC%' or (DOT_RTNAME LIKE '0089%' and DOT_RTPART = '10'))")
    arcpy.management.CalculateField(urban_roads_selected, field="SPEED_LMT", expression='40')

    # downgrade the speeds on all freeways in settled areas to 65
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "(CARTOCODE = '1' OR ((DOT_RTNAME = '0201P' OR DOT_RTNAME = '0201N') and CARTOCODE = '4') OR CARTOCODE = '2') and URBTRAFFIC = 'Y'")
    arcpy.management.CalculateField(urban_roads_selected, field="SPEED_LMT", expression='65')

    ## Fix roads with a speed limit of zero
    # apply manual corrections - US89 , Timp Highway collector
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "DOT_RTNAME like '0092%' and DOT_RTNAME like '%C%'")
    arcpy.management.CalculateField(urban_roads_selected, field="SPEED_LMT", expression='65')

    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "DOT_RTNAME like '0085%'")
    arcpy.management.CalculateField(urban_roads_selected, field="SPEED_LMT", expression='55')

    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "DOT_RTNAME like '0154%'")
    arcpy.management.CalculateField(urban_roads_selected, field="SPEED_LMT", expression='55')


    #### PART 2: Calculate Travel Cost Impedance ####
    print("Calculate Travel Cost Impedance...")
    # calculate impedance (in minutes) for all ramp-accessed roads (freeways)
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "CARTOCODE = '1' or CARTOCODE = '2' or CARTOCODE = '4' or DOT_RTNAME like '%R%' or DOT_RTNAME like '%C%' or URBTRAFFIC = 'N'")
    arcpy.management.CalculateField(urban_roads_selected, field="IMPED_MIN", expression='(!SHAPE_Length!/1609 * 60) / !SPEED_LMT!')
    # switch selection and calculate the impedance (in minutes) for all traffic controlled roads by increasing the travel time by a factor of 1.5 to account for stop signs, signals, and turns
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','SWITCH_SELECTION')
    arcpy.management.CalculateField(urban_roads_selected, field="IMPED_MIN", expression='(!SHAPE_Length!/1609 * 60) / !SPEED_LMT! * 1.5')
    arcpy.management.CalculateField(urban_roads_selected, field="IMPED_PED", expression='!SHAPE_Length! / 84')
    # select limited access roadways (ie: freeways/ramps) and multiply by 1.2
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "CARTOCODE = '1' OR ((DOT_RTNAME = '0201P' OR DOT_RTNAME = '0201N') and CARTOCODE = '4') OR CARTOCODE = '2' or CARTOCODE = '7'")
    arcpy.management.CalculateField(urban_roads_selected, field="IMPED_MIN", expression='(!SHAPE_Length!/1609 * 60) / !SPEED_LMT! * 1.2')

    ## impedance needed to be be set differently for each direction on one way streets and routes. Check to see if ONE_WAY attributes for limited access freeways/highways need to be fixed
    print("Calculate one ways...")
    # for both directions of travel on I-215 (semi-looping), set the ONE_WAY attribute using manual selection so that all features oriented in the true direction of travel are set to 1 and the others to 2
    # oneway codes [0 = Two way travel; 1 = One way travel in direction of arc; 2 = One way travel in opposite direction of arc]
    # set oneway to '1'
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "(DOT_RTNAME = '0215N' and DOT_F_MILE > DOT_T_MILE) or (DOT_RTNAME = '0215P' and DOT_F_MILE < DOT_T_MILE)")
    arcpy.management.CalculateField(urban_roads_selected, field="ONEWAY", expression='1')
    # set oneway to '2'
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "(DOT_RTNAME = '0215N' and DOT_F_MILE < DOT_T_MILE) or (DOT_RTNAME = '0215P' and DOT_F_MILE > DOT_T_MILE)")
    arcpy.management.CalculateField(urban_roads_selected, field="ONEWAY", expression='2')

    ## For the positive (eastbound) travel direction for x (E-W) trending routes
    # query the coordinate values for these selected records (using two temporary fields populated by the calculate geometry field tool), to set the ONE_WAY attribute for these selected records as follows:
    # where x coordinate at start point is < then x coordinate at end point: set oneway = 1
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "(DOT_RTNAME = '0080P' or DOT_RTNAME = '0084P' or DOT_RTNAME = '0070P' or (DOT_RTNAME = '0201P' and DOT_RTPART = '2' ) or (DOT_RTNAME = '0007P' and DOT_RTPART = '2')) and START_X < END_X")
    arcpy.management.CalculateField(urban_roads_selected, field="ONEWAY", expression='1')
    # where x coordinate at start point is > then x coordinate at end point: set oneway = 2
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "(DOT_RTNAME = '0080P' or DOT_RTNAME = '0084P' or DOT_RTNAME = '0070P' or (DOT_RTNAME = '0201P' and DOT_RTPART = '2' ) or (DOT_RTNAME = '0007P' and DOT_RTPART = '2')) and START_X > END_X")
    arcpy.management.CalculateField(urban_roads_selected, field="ONEWAY", expression='2')

    ## For the negative (westbound) travel direction for X Trending (E-W) routes
    # Query the coordinate values for these selected records (using two temporary fields populated by the calculate geometry field tool), to set the ONE_WAY attribute for these selected records as follows:
    # where x coordinate at start point is > then x coordinate at end point: set oneway = 1
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "(DOT_RTNAME = '0080N' or DOT_RTNAME = '0084N' or DOT_RTNAME = '0070N' or DOT_RTNAME = '0201N' or DOT_RTNAME = '0007N') and START_X > END_X")
    arcpy.management.CalculateField(urban_roads_selected, field="ONEWAY", expression='1')
    # where x coordinate at start point is < then x coordinate at end point: set oneway = 2
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "(DOT_RTNAME = '0080N' or DOT_RTNAME = '0084N' or DOT_RTNAME = '0070N' or DOT_RTNAME = '0201N' or DOT_RTNAME = '0007N') and START_X < END_X")
    arcpy.management.CalculateField(urban_roads_selected, field="ONEWAY", expression='2')

    ## For the positive (northbound) travel direction for Y Trending (N-S) routes
    # Query the coordinate values for these selected records (using two temporary fields populated by the calculate geometry field tool), to set the ONE_WAY attribute for these selected records as follows:
    # where y coordinate at start point is < then y coordinate at end point: set oneway = 1
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "(DOT_RTNAME = '0015P' or (DOT_RTNAME = '0152P' and DOT_RTPART ='2') or (DOT_RTNAME = '0154P' and DOT_RTPART ='2') or DOT_RTNAME = '0067P' or (DOT_RTNAME = '0189P' and DOT_RTPART ='2') or (DOT_RTNAME = '0191P' and DOT_RTPART ='2') or (DOT_RTNAME = '0089P' and (DOT_RTPART ='4' or DOT_RTPART ='7' or DOT_RTPART ='9' or DOT_RTPART ='11'))) and START_Y < END_Y")
    arcpy.management.CalculateField(urban_roads_selected, field="ONEWAY", expression='1')
    # where y coordinate at start point is > then y coordinate at end point: set oneway = 2
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "(DOT_RTNAME = '0015P' or (DOT_RTNAME = '0152P' and DOT_RTPART ='2') or (DOT_RTNAME = '0154P' and DOT_RTPART ='2') or DOT_RTNAME = '0067P' or (DOT_RTNAME = '0189P' and DOT_RTPART ='2') or (DOT_RTNAME = '0191P' and DOT_RTPART ='2') or (DOT_RTNAME = '0089P' and (DOT_RTPART ='4' or DOT_RTPART ='7' or DOT_RTPART ='9' or DOT_RTPART ='11'))) and START_Y > END_Y")
    arcpy.management.CalculateField(urban_roads_selected, field="ONEWAY", expression='2')

    ## For the negative (southbound) travel direction for south north (y) trending routes and exception for a couple sections of us40 and us6
    # Query the coordinate values for these selected records (using two temporary fields populated by the calculate geometry field tool), to set the ONE_WAY attribute for these selected records as follows:
    # where y coordinate at start point is > then y coordinate at end point: set oneway = 1
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "(DOT_RTNAME = '0015N' or DOT_RTNAME = '0152N' or DOT_RTNAME = '0154N' or DOT_RTNAME = '0067N' or DOT_RTNAME = '0189N' or DOT_RTNAME = '0191N ' or DOT_RTNAME = '0040N' or DOT_RTNAME = '0006N' or DOT_RTNAME = '0089N' or (DOT_RTNAME = '0040P' and DOT_RTPART ='2') or (DOT_RTNAME = '0006P' and DOT_RTPART ='3')) and START_Y > END_Y")
    arcpy.management.CalculateField(urban_roads_selected, field="ONEWAY", expression='1')
    # where y coordinate at start point is < then y coordinate at end point: set oneway = 2
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "(DOT_RTNAME = '0015N' or DOT_RTNAME = '0152N' or DOT_RTNAME = '0154N' or DOT_RTNAME = '0067N' or DOT_RTNAME = '0189N' or DOT_RTNAME = '0191N ' or DOT_RTNAME = '0040N' or DOT_RTNAME = '0006N' or DOT_RTNAME = '0089N' or (DOT_RTNAME = '0040P' and DOT_RTPART ='2') or (DOT_RTNAME = '0006P' and DOT_RTPART ='3')) and START_Y < END_Y")
    arcpy.management.CalculateField(urban_roads_selected, field="ONEWAY", expression='2')


    ## Calculate the travel cost fields and then inflate the travel cost for the wrong direction of travel on one way segments by a large factor (100 x current impedance is currently used)
    print("Calculate T_F_IMP_MIN and F_T_IMP_MIN values...")
    # Transfer over all IMPED_MIN values to both T_F_IMP_MIN and F_T_IMP_MIN fields.
    # clear selection 
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','CLEAR_SELECTION')
    arcpy.management.CalculateField(urban_roads_selected, field="T_F_IMP_MIN", expression='!IMPED_MIN!')
    arcpy.management.CalculateField(urban_roads_selected, field="F_T_IMP_MIN", expression='!IMPED_MIN!')
    # Now, inflate the travel time on one ways...
    # Select all roads where the ONEWAY attribute = 1
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "ONEWAY = '1'")
    arcpy.management.CalculateField(urban_roads_selected, field="T_F_IMP_MIN", expression='!IMPED_MIN! * 100')
    # Select all roads where the ONEWAY attribute = 2
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "ONEWAY = '2'")
    arcpy.management.CalculateField(urban_roads_selected, field="F_T_IMP_MIN", expression='!IMPED_MIN! * 100')


    ## Part 3 - Build the network dataset
    # Create 2 different values for the NETSUBTYPE field so connectivity can be modeled at endpoints for limited access highways and ramps and at any vertex for other, surface streets:
    # Query for limited access features and set NETSUBTYPE = 1 and set EXCL_WALK = Y
    print("Calculate NETSUBTYPE values...")
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','NEW_SELECTION', "CARTOCODE = '1' or CARTOCODE = '2' or CARTOCODE = '4' or DOT_RTNAME like '%R%' or DOT_RTNAME like '%C%'")
    arcpy.management.CalculateField(urban_roads_selected, field="NETSUBTYPE", expression='1')
    arcpy.management.CalculateField(urban_roads_selected, field="EXCL_WALK", expression='"Y"')
    # Switch selection and set remaining records NETSUBTYPE = 2 and set EXCL_WALK = N
    urban_roads_selected = arcpy.management.SelectLayerByAttribute('network_roads_lyr','SWITCH_SELECTION')
    arcpy.management.CalculateField(urban_roads_selected, field="NETSUBTYPE", expression='2')
    arcpy.management.CalculateField(urban_roads_selected, field="EXCL_WALK", expression='"N"')

    # clean up resources and memory
    arcpy.management.Delete('network_roads_lyr')

    # create Subtypes to define the two geodatabase subtypes using the NETSUBTYPE field
    # Code: "1" || Description "Limited Access & Ramps"
    # Code: "2" || Description "Other"
    print("Create SUBTYPES for Limited Access & Ramps and Other...")
    arcpy.management.SetSubtypeField(network_roads, field="NETSUBTYPE", clear_value="DO_NOT_CLEAR")
    arcpy.management.AddSubtype(network_roads, subtype_code="1", subtype_description="Limited Access & Ramps")
    arcpy.management.AddSubtype(network_roads, subtype_code="2", subtype_description="Other")

    # build the netork based on an existing network .xml file template
    ## this is done in a seperate script b/c it needs to be run in Desktop 10.6 (or higher) or Pro
    ## use this script: "agrc_roadnetwork_create_and_build_network_run2nd.py"
    print("Done!")




# this function imports the user-defined utrans roads into the the netork dataset feature class 
def import_RoadsIntoNetworkDataset(sgid_roads_to_import, network_roads):    
    # get list of field names
    sgid_roads_fieldnames = [f.name for f in arcpy.ListFields(sgid_roads_to_import)]
    network_roads_fieldnames = [f.name for f in arcpy.ListFields(network_roads)]

    # set up search cursors to select and insert data between feature classes (define two cursor on next line: search_cursor and insert_cursor)
    with arcpy.da.SearchCursor(sgid_roads_to_import, '*', sql_clause=('TOP 10', None)) as search_cursor, arcpy.da.InsertCursor(network_roads, network_roads_fieldnames) as insert_cursor:
        # itterate though the intersected utrans road centerline features
        for utrans_row in search_cursor:
            name = str(search_cursor[sgid_roads_fieldnames.index('NAME')])
            pre_dir = str(search_cursor[sgid_roads_fieldnames.index('PREDIR')])


            # create list of row values to insert (maybe just use the "network_roads_fieldnames" list)
            insert_row_values = [name, pre_dir]
            # insert the new row with the list of values
            for insert_row in insert_row_values:
                insert_cursor.insertRow(insert_row) 



def generate_scratch_data(today_dir):
    # create new fgdb
    print("Creating Scratch File Geodatabase...")

    scratch_fgdb = arcpy.management.CreateFileGDB(today_dir, 'NetworkBuild_scratchData.gdb')

    # union the census urban areas and the sgid muni
    print("Union the Census Urban Areas and SGID Munis")
    urban_areas = rf"{SGID}\SGID.DEMOGRAPHIC.UrbanAreasCensus2010"
    munis = rf"{SGID}\SGID.BOUNDARIES.Municipalities"
    in_list = [urban_areas, munis]
    out_fc = rf"{scratch_fgdb}\UrbanAreasMuni_Union"
    unioned_fc = arcpy.analysis.Union(in_features=in_list, out_feature_class=out_fc, join_attributes="ONLY_FID", cluster_tolerance="", gaps="GAPS")

    # dissolve this unioned data
    out_fc_dissolved = rf"{scratch_fgdb}\UrbanAreasMuni_Union_Dissolved"
    print("Dissolve the unioned layer")
    return arcpy.management.Dissolve(in_features=str(unioned_fc), out_feature_class=out_fc_dissolved, dissolve_field="", statistics_fields="", multi_part="MULTI_PART", unsplit_lines="DISSOLVE_LINES")


if __name__ == "__main__":
    # execute only if run as a script
    main()


print("Script shutting down ...")
# Stop timer and print end time
readable_end = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
print("The script end time is {}".format(readable_end))
print("Time elapsed: {:.2f}s".format(time.time() - start_time))