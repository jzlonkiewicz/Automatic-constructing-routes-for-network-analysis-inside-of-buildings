# -*- coding: iso-8859-2 -*-

import time
import os.path
import sys
import arcpy
from platform import python_version

arcpy.env.overwriteOutput = True
clock_start = time.clock()


def door_relation_function(database, room_name, door_work_layer, door_original_file, cursor_fields, door_type):

    # Function appends id of selected room to the list and appends the name of the room
    # into the fields outr_id, inr_id in the door file

    # door_type = 1 door opening in both sides
    # door_type = 2 door opening inside of chosen room
    # door_type = 3 door opening outside of chosen room

    room_path = os.path.join(database, room_name)
    room_list = []
    arcpy.CopyFeatures_management(door_work_layer, room_path)
    with arcpy.da.SearchCursor(room_path, ['nr']) as fun_cursor_1:
        for current_row in fun_cursor_1:
            room_id = current_row[0]
            room_list.append(room_id)
    del fun_cursor_1
    arcpy.Delete_management(room_path)

    if door_type == 2 or door_type == 3:
        with arcpy.da.UpdateCursor(door_original_file, cursor_fields) as fun_cursor_2:
            for current_row in fun_cursor_2:
                if current_row[1] in room_list:
                    current_row[door_type] = str(room_name)
                    fun_cursor_2.updateRow(current_row)
        del fun_cursor_2
    elif door_type == 1:
        with arcpy.da.UpdateCursor(door_original_file, cursor_fields) as fun_cursor_3:
            for current_row in fun_cursor_3:
                if current_row[1] in room_list and current_row[2] is None:
                    current_row[door_type+1] = str(room_name)
                    fun_cursor_3.updateRow(current_row)
                elif current_row[1] in room_list and current_row[2] is not None:
                    current_row[door_type+2] = str(room_name)
                    fun_cursor_3.updateRow(current_row)

        del fun_cursor_3


# Stage I - Setting up of proper paths and geodatabase for the results
try:
    print('Python', python_version())
    script_path = os.getcwd()
    print(script_path)
    my_data = os.path.join(script_path, "C-4")
    arcpy.AddMessage("Data catalog found")
    arcpy.AddMessage("Data catalog path: {}".format(my_data))

except NameError as e1:
    # If an error occurred, print line number and error message
    tb1 = sys.exc_info()[2]
    arcpy.AddWarning("An error occured on line {}".format(tb1.tb_lineno))
    arcpy.AddWarning(str(e1))

try:
    arcpy.AddMessage("Setting up of results database and datasets")
    my_database = os.path.join(my_data, "baza.gdb")
    arcpy.env.workspace = my_database
    storeys_set = os.path.join(my_database, "Kondygnacje")
    storeys_set_describe = arcpy.Describe(storeys_set)
    door_set = os.path.join(my_database, "Drzwi")
    door_set_describe = arcpy.Describe(door_set)
    fields = ["OBJECTID", "nr", "inr_id", "outr_id"]
    spatial_reference = arcpy.Describe(storeys_set).spatialReference
    data_sets = arcpy.ListDatasets(feature_type='feature')

    # This loop adds columns inr_id, outr_id and nr in all door files and fills fields "nr" column with id of record
    for data_set in data_sets:
        if data_set == "Drzwi":
            for feature_class in arcpy.ListFeatureClasses(feature_dataset=data_set):
                path = os.path.join(arcpy.env.workspace, data_set, feature_class)
                arcpy.AddField_management(path, "inr_id", "TEXT")
                arcpy.AddField_management(path, "outr_id", "TEXT")
                arcpy.AddField_management(path, "nr", "SHORT")
                with arcpy.da.UpdateCursor(path, fields) as door_id_cursor:
                    for door_record in door_id_cursor:
                        door_record[1] = str(door_record[0])
                        door_id_cursor.updateRow(door_record)
                del door_id_cursor

    # Creating data sets in results.gdb
    arcpy.CreateFileGDB_management(my_data, "results")
    results_database = os.path.join(my_data, "results.gdb")
    arcpy.CreateFeatureDataset_management(results_database, "corridors", spatial_reference)
    corridors_set = os.path.join(results_database, "corridors")
    arcpy.CreateFeatureDataset_management(results_database, "roads", spatial_reference)
    road_set = os.path.join(results_database, "roads")
    arcpy.CreateFeatureDataset_management(results_database, "doors", spatial_reference)
    door_results_set = os.path.join(results_database, "doors")
    arcpy.CreateFeatureDataset_management(results_database, "rooms", spatial_reference)
    room_set = os.path.join(results_database, "rooms")
    arcpy.CreateFeatureDataset_management(results_database, "three_d_features", spatial_reference)
    three_d_features_set = os.path.join(results_database, "three_d_features")

except Exception as e2:
    # If an error occurred, print line number and error message
    tb2 = sys.exc_info()[2]
    arcpy.AddWarning("An error occurred on line {}".format(tb2.tb_lineno))
    arcpy.AddWarning(str(e2))

lap_time_1 = int(time.clock() - clock_start)
print('Duration of the first stage: {} seconds'.format(lap_time_1))
print(' ')


# Stage II - Creation of the corridors net
def protect_data_function():

    try:
        print("Stage II - Creation of the corridors net")
        three_d_corridor_list = []

        for current_storey in storeys_set_describe.children:
            storey_loop_time = time.clock()
            print("Current storey: {}".format(current_storey.name))
            current_storey_path = os.path.join(current_storey.path, current_storey.name)

            # Centroid 3D layers creation
            # This block makes name of storey cellar a number and calculates level for every storey
            storey_number = current_storey.name[slice(3, 4, 1)]
            if storey_number == 'm':
                storey_number = -1
            storey_level = int(storey_number) * 5
            arcpy.AddField_management(current_storey_path, "Z", "INTEGER")
            with arcpy.da.UpdateCursor(current_storey_path, ['Z', "room_id"]) as level_calculation_cursor:
                for h in level_calculation_cursor:
                    h[0] = storey_level
                    level_calculation_cursor.updateRow(h)
            del level_calculation_cursor

            rooms_centroids = os.path.join(room_set, (current_storey.name + '_centroids'))
            arcpy.FeatureToPoint_management(current_storey_path, rooms_centroids, "INSIDE")
            rooms_centroids_3d = os.path.join(three_d_features_set, (current_storey.name + '_centroids_3d'))
            arcpy.FeatureTo3DByAttribute_3d(rooms_centroids, rooms_centroids_3d, "Z")

            # Creation of corridors net
            storey_layer_name = current_storey.name + "_lyr"
            storey_layer = arcpy.MakeFeatureLayer_management(current_storey_path, storey_layer_name)
            arcpy.SelectLayerByAttribute_management(storey_layer, "NEW SELECTION", "corridor = 'yes'")
            corridors_count = arcpy.GetCount_management(storey_layer)

            # After this condition script creates a feature with centroids of Thiessen Polygons inside the corridor
            if str(corridors_count) != "0":
                corridor_polygon = os.path.join(corridors_set, (current_storey.name + '_corridor'))
                corridor_vertices = corridor_polygon + "_vertices"
                corridor_points_all = os.path.join(corridors_set, (current_storey.name + '_corridor_points_all'))
                thiessen_polygons = corridor_polygon + "_thiessenpolygons"
                thiessen_polygons_clip = thiessen_polygons + "_clipped"
                corridor_inner_points = thiessen_polygons_clip + "_centroids"
                arcpy.CopyFeatures_management(storey_layer, corridor_polygon)
                arcpy.FeatureVerticesToPoints_management(corridor_polygon, corridor_vertices)
                arcpy.CreateThiessenPolygons_analysis(corridor_vertices, thiessen_polygons, "ALL")
                arcpy.Clip_analysis(thiessen_polygons, corridor_polygon, thiessen_polygons_clip)
                arcpy.FeatureToPoint_management(thiessen_polygons_clip, corridor_inner_points, "CENTROID")
                corridor_layer = arcpy.MakeFeatureLayer_management(corridor_polygon, current_storey.name + "_corridor")
                arcpy.SelectLayerByAttribute_management(storey_layer, "CLEAR_SELECTION")

            # This loop processes door feature on current storey
            for current_door in door_set_describe.children:
                if current_storey.name == current_door.name[2:]:
                    current_door_path = os.path.join(current_door.path, current_door.name)
                    door_layer_name = "door" + current_door.name
                    current_door_layer = arcpy.MakeFeatureLayer_management(current_door_path, door_layer_name)

                    # After this condition script creates a feature of door centroids which are inside of the corridor
                    # and merges them with Thiessen Polygon centroids in corridor
                    if str(corridors_count) != "0":
                        door_in_corridor = os.path.join(door_results_set, (current_door.name + '_inside_corridor'))
                        door_in_corridor_centroids = os.path.join(corridors_set, (current_door.name + '_centroid'))
                        arcpy.SelectLayerByLocation_management(current_door_layer, "INTERSECT", corridor_layer)
                        arcpy.CopyFeatures_management(current_door_layer, door_in_corridor)
                        arcpy.FeatureToPoint_management(door_in_corridor, door_in_corridor_centroids, "INSIDE")
                        to_merge = [corridor_inner_points, door_in_corridor_centroids]
                        arcpy.Merge_management(to_merge, corridor_points_all)
                        with arcpy.da.UpdateCursor(corridor_points_all, ['Z']) as corridor_points_cursor:
                            for corridor_door_record in corridor_points_cursor:
                                corridor_door_record[0] = storey_level
                                corridor_points_cursor.updateRow(corridor_door_record)
                        del corridor_points_cursor

                        # Creation of TIN based on points net inside of the corridor
                        # and creation of the file with edges who doesn't intersect the wall
                        tin = os.path.join(my_data, (current_storey.name + '_tin'))
                        tin_edges = os.path.join(corridors_set, (current_storey.name + '_edges'))
                        corridor_net = os.path.join(corridors_set, (current_storey.name + '_corridor_net'))
                        arcpy.CreateTin_3d(tin, spatial_reference=spatial_reference, in_features=corridor_points_all)
                        arcpy.TinEdge_3d(tin, tin_edges)
                        tin_edges_layer = arcpy.MakeFeatureLayer_management(tin_edges, current_door.name + "_edges_layer")
                        arcpy.SelectLayerByLocation_management(tin_edges_layer, "WITHIN", corridor_layer)
                        arcpy.CopyFeatures_management(tin_edges_layer, corridor_net)
                        arcpy.SelectLayerByAttribute_management(tin_edges_layer, "CLEAR_SELECTION")
                        arcpy.SelectLayerByAttribute_management(current_door_layer, "CLEAR_SELECTION")

                    # Stage III - Creation of connection between the doors and rooms they lead to
                    print("Processed door layer:", current_door.name)

                    # In this loop script selects all types of doors who have relation to the current room
                    # and writes type of the relation to the attribute table
                    storey_cursor = arcpy.da.SearchCursor(current_storey_path, ["room_id", "id"])
                    for single_room_record in storey_cursor:
                        room_id_in_table = single_room_record[1]
                        room_number = str(single_room_record[0])

                        # Selection 1 for doors opening inside of the room (in)
                        select1 = arcpy.SelectLayerByAttribute_management(storey_layer_name, "NEW_SELECTION", '"id" = %s' % room_id_in_table)
                        arcpy.SelectLayerByLocation_management(in_layer=current_door_layer, overlap_type="WITHIN", select_features=select1, selection_type="NEW_SELECTION")
                        count_doors_1 = arcpy.GetCount_management(current_door_layer)
                        if str(count_doors_1) != "0":
                            door_relation_function(my_database, room_number, current_door_layer, current_door_path, fields, 2)

                        # Selection 2 for doors opening outside of the room (out)
                        arcpy.SelectLayerByLocation_management(in_layer=current_door_layer, overlap_type="BOUNDARY_TOUCHES", select_features=select1, selection_type="NEW_SELECTION")
                        arcpy.SelectLayerByLocation_management(in_layer=current_door_layer, overlap_type="WITHIN", select_features=select1, selection_type="REMOVE_FROM_SELECTION")
                        count_doors_2 = arcpy.GetCount_management(current_door_layer)
                        if str(count_doors_2) != "0":
                            door_relation_function(my_database, room_number, current_door_layer, current_door_path, fields, 3)

                        # Selection 3 for doors opening on both sides
                        arcpy.SelectLayerByLocation_management(in_layer=current_door_layer, overlap_type="CROSSED_BY_THE_OUTLINE_OF", select_features=select1, selection_type="NEW_SELECTION")
                        count_doors_3 = arcpy.GetCount_management(current_door_layer)
                        if str(count_doors_3) != "0":
                            door_relation_function(my_database, room_number, current_door_layer, current_door_path, fields, 1)

                    # Stage IV - Creation of the net in rooms other than corridors
                    door_centroids = os.path.join(door_results_set, (current_door.name + '_centroids'))
                    arcpy.FeatureToPoint_management(current_door_path, door_centroids, "INSIDE")
                    lines = []

                    with arcpy.da.SearchCursor(rooms_centroids, ['SHAPE@', 'room_id', 'corridor']) as door_to_room_cursor:
                        for room_record in door_to_room_cursor:
                            if room_record[2] != "yes":
                                start = room_record[0].centroid
                                for room_not_corridor in arcpy.da.SearchCursor(door_centroids, ['SHAPE@', 'inr_id', 'outr_id'], spatial_reference=spatial_reference):
                                    if room_record[1] == room_not_corridor[1] or room_record[1] == room_not_corridor[2]:
                                        end = room_not_corridor[0].centroid
                                        lines.append(arcpy.Polyline(arcpy.Array([start, end]), spatial_reference))
                    del door_to_room_cursor
                    rooms_net = os.path.join(road_set, (current_storey.name + '_net'))
                    arcpy.CopyFeatures_management(lines, rooms_net)
                    arcpy.AddField_management(rooms_net, "Z", "integer")
                    with arcpy.da.UpdateCursor(rooms_net, ['Z']) as cursor:
                        for l in cursor:
                            l[0] = storey_level
                            cursor.updateRow(l)
                    arcpy.FeatureTo3DByAttribute_3d(rooms_net, rooms_net + "_3D_rooms", "Z")
                    arcpy.Merge_management([rooms_net + "_3D_rooms", corridor_net], rooms_net + "_3D_all")
                    three_d_corridor_list.append(rooms_net + "_3D_all")
            lap_time_2 = int(time.clock() - storey_loop_time)
            print("Lasting of selection loop: {} seconds".format(lap_time_2))
            print(' ')

        # Stage V - Creation of net inside of staircases and elevators
        three_d_set_describe = arcpy.Describe(three_d_features_set)
        stairs = []
        ceiling_level = []
        floor_level = []
        for lower_floor in three_d_set_describe.children:
            lower_floor_number = lower_floor.name[slice(3, 4, 1)]
            if lower_floor_number == 'm':
                lower_floor_number = -1
            lower_floor_number_integer = int(lower_floor_number)
            lower_floor_path = os.path.join(lower_floor.path, lower_floor.name)

            for higher_floor in three_d_set_describe.children:
                higher_floor_number = higher_floor.name[slice(3, 4, 1)]

                if higher_floor_number == 'm':
                    higher_floor_number = -1
                higher_floor_number_integer = int(higher_floor_number)
                higher_floor_path = os.path.join(higher_floor.path, higher_floor.name)

                if higher_floor_number_integer - lower_floor_number_integer == 1:
                    for lower_staircase_room in arcpy.da.SearchCursor(lower_floor_path, ['SHAPE@', 'room_type', 'Z', "room_id"]):
                        lower_room_centroid = lower_staircase_room[0].centroid
                        lower_room_level = lower_staircase_room[2]
                        if lower_staircase_room[1] == "stairs1" or lower_staircase_room[1] == "stairs2" or lower_staircase_room[1] == "elevator":
                            for higher_staircase_room in arcpy.da.SearchCursor(higher_floor_path, ['SHAPE@', 'room_type', 'Z', 'room_id'], spatial_reference=spatial_reference):
                                if lower_staircase_room[1] == higher_staircase_room[1]:
                                    higher_room_centroid = higher_staircase_room[0].centroid
                                    higher_room_level = higher_staircase_room[2]
                                    stairs.append(arcpy.Polyline(arcpy.Array([lower_room_centroid, higher_room_centroid]), spatial_reference))
                                    floor_level.append(lower_room_level)
                                    ceiling_level.append(higher_room_level)

        stairs_net = os.path.join(three_d_features_set, "stairs_net")
        arcpy.CopyFeatures_management(stairs, stairs_net)
        print("Stairs layer has been generated!")
        arcpy.AddField_management(stairs_net, "floor_level", "integer")
        arcpy.AddField_management(stairs_net, "ceiling_level", "integer")

        # This loop takes ceiling and floor level from lists and updates it in stairs_net file attribute table
        with arcpy.da.UpdateCursor(stairs_net, ['floor_level', 'ceiling_level']) as staircase_level_cursor:
            counter = 0
            for staircase_floor in staircase_level_cursor:
                staircase_floor[0] = floor_level[counter]
                staircase_floor[1] = ceiling_level[counter]
                counter += 1
                staircase_level_cursor.updateRow(staircase_floor)
        arcpy.FeatureTo3DByAttribute_3d(stairs_net, stairs_net + "_3d", "floor_level", "ceiling_level")
        three_d_corridor_list.append(stairs_net + "_3d")
        arcpy.Merge_management(three_d_corridor_list, os.path.join(three_d_features_set, "net_3d"))

    except Exception as e3:
        # If an error occurred, print line number and error message
        tb3 = sys.exc_info()[2]
        arcpy.AddWarning("An error occurred on line {}".format(tb3.tb_lineno))
        arcpy.AddWarning(str(e3))

    finally:
        pass


if __name__ == '__main__':
    protect_data_function()


# Stage VI - Testing of network analyse on created net
try:
    # Check out Network Analyst license if available. Fail if the Network Analyst license is not available.
    if arcpy.CheckExtension("network") == "Available":
        arcpy.CheckOutExtension("network")
    else:
        raise arcpy.ExecuteError("Network Analyst Extension license is not available.")

    stops = os.path.join(three_d_features_set, "stops_5")
    arcpy.CopyFeatures_management(os.path.join(my_database, "stops_5"), stops)
    network_dataset = os.path.join(three_d_features_set, "D_ND")
    output_route_layer = os.path.join(three_d_features_set, "Route")
    arcpy.na.CreateNetworkDatasetFromTemplate(os.path.join(my_data, "NDTemplate.xml"), three_d_features_set)
    print("Network data set has been created")
    arcpy.na.BuildNetwork(network_dataset)
    arcpy.na.MakeRouteLayer(network_dataset, output_route_layer, "Length")
    arcpy.na.AddLocations(output_route_layer, 'Stops', stops, "", "5 Centimeters", snap_to_position_along_network="SNAP", snap_offset="5 Centimeters")
    print("Stops has been added")
    arcpy.na.Solve(output_route_layer)
    arcpy.CopyFeatures_management(os.path.join(output_route_layer, "Routes"), os.path.join(three_d_features_set, "result_route"))
    print("Network analyze has been processed!")


except Exception as e4:
    # If an error occurred, print line number and error message
    tb4 = sys.exc_info()[2]
    arcpy.AddWarning("An error occurred on line {}".format(tb4.tb_lineno))
    arcpy.AddWarning(str(e4))

lap_time_3 = int(time.clock() - clock_start)
lap_time_3_seconds = lap_time_3 % 60
lap_time_3_minutes = int((lap_time_3-lap_time_3_seconds)/60)
print("Script working time: {0} minutes {1} seconds".format(lap_time_3_minutes, lap_time_3_seconds))



