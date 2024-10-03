import json
import logging
import time
import traceback
from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from os import environ
from dateutil.parser import parse

import awswrangler as wr
import boto3
import psycopg2
import psycopg2.extras
import pytz
from botocore.exceptions import ClientError
from psycopg2.extras import execute_values

s3 = boto3.client('s3')

session = boto3.Session()
db_host = environ.get('POSTGRES_HOST')
db_port = environ.get('POSTGRES_PORT')
db_user = environ.get('POSTGRES_USER')
db_database = environ.get('POSTGRES_DB')
sirivm_bucket = environ.get('SIRIVM_BUCKET')
region = environ.get('AWS_REGION')
operator_ref = environ.get('OPERATOR_REF')
line_name = environ.get('LINE_NAME')

logger = logging.getLogger('sirivm')
logging.getLogger().setLevel('INFO')

# Upload JSON String to an S3 Object
client = boto3.client('s3')

# uk_timezone = pytz.timezone('Europe/London')
bst = pytz.timezone('Europe/London')
utc = pytz.utc

global_timetable_dict = {}
loaded_timetable_path = ""

def readTimetable(timetable_name=None):
    global global_timetable_dict
    global loaded_timetable_path
    if timetable_name is None:
        content= client.get_object(Bucket=sirivm_bucket, Key='timetable/timetable.json').get('Body').read()
        global_timetable_dict = json.loads(content)
    else:
        if loaded_timetable_path != timetable_name:
            content= client.get_object(Bucket=sirivm_bucket, Key=timetable_name).get('Body').read()
            loaded_timetable_path = timetable_name
            global_timetable_dict = json.loads(content)
            logger.info(f"Loaded {timetable_name}")
    return

def readShards():
    global shards
    global no_of_shards
    shard_file = client.get_object(Bucket=sirivm_bucket, Key='shards.json').get('Body').read()
    shards = json.loads(shard_file)
    no_of_shards = len(shards["shards"])
    return

def readStopHistory(currentDate, shard_no, avl_timestamp):
    stop_history = {
        "control_info":{
            "last_avl": avl_timestamp,
            "last_avl_processed_time": datetime.now()
        }
    }
    try:
        content= client.get_object(Bucket=sirivm_bucket, Key=f'timetable_avl/{currentDate}/timetable_avl_stop_history_shard{shard_no}.json').get('Body').read()
        stop_history = json.loads(content)
        if "control_info" in stop_history:
            last_avl_filename = stop_history["control_info"]["last_avl"]
            if "last_avl_processed_time" in stop_history["control_info"]:
                last_avl_processed_time = stop_history["control_info"]["last_avl_processed_time"]
            else:
                last_avl_processed_time = "Not known"
            if int(last_avl_filename) > avl_timestamp:
                logger.warn(f"AVL is not in order, last avl: {stop_history['control_info']['last_avl']}, current avl: {avl_timestamp}")
            elif int(last_avl_filename) == avl_timestamp:
                logger.warn(f"Same AVL data coming in, last avl processed time: {last_avl_processed_time}, current last avl: {stop_history['control_info']['last_avl']}, current avl: {avl_timestamp}")
    except ClientError as ex:
        if ex.response['Error']['Code'] == 'NoSuchKey':
            logger.info('No object found - so returning empty')
        else:
            raise
    if "control_info" not in stop_history:
        stop_history["control_info"] = {}
    stop_history["control_info"]["last_avl"] = avl_timestamp
    stop_history["control_info"]["last_avl_processed_time"] = datetime.now()
    return stop_history

def cleanStopHistory(stop_history, avl_datetime):
    # Removing data that is > 1hr ago
    remove_group_id = []
    for group_id, match_details in stop_history.items():
        if group_id != "control_info":
            last_avl_time_str = match_details["last_avl_time"][:19]
            last_avl_time = datetime.strptime(last_avl_time_str, "%Y-%m-%d %H:%M:%S")
            if (avl_datetime.replace(tzinfo=utc) - last_avl_time.replace(tzinfo=utc)).total_seconds()/60/60 > 1:
                logging.info(f"Removing {group_id} with avl time {avl_datetime.replace(tzinfo=utc)} and last avl time {last_avl_time.replace(tzinfo=utc)}, time diff = {(avl_datetime.replace(tzinfo=utc) - last_avl_time.replace(tzinfo=utc)).total_seconds()/60/60}")
                remove_group_id.append(group_id)
    for group_id in remove_group_id:
        del stop_history[group_id]
    return stop_history

def log_specific(avl_operator_ref, avl_line_name, log_message, log_type=None):
    if operator_ref == avl_operator_ref and line_name == avl_line_name:
        logger.info(log_message)

def validateDate(date_input):
    if isinstance(date_input, datetime):
        return date_input
    else:
        date_input_wo_tz = date_input[:19]
        if "T" in date_input:
            converted_date = datetime.strptime(date_input_wo_tz, "%Y-%m-%dT%H:%M:%S")
        else:
            converted_date = datetime.strptime(date_input_wo_tz, "%Y-%m-%d %H:%M:%S")
        return converted_date

def checkTimeDifference(time_difference, last_time_in_zone, timetable_departure_time):
    if time_difference < -7200 or time_difference > 3600:
        logger.warn(f"time difference: {time_difference}, last_time_in_zone: {last_time_in_zone}, timetable_departure_time {validateDate(timetable_departure_time)}")

def updateMatchedStop(rec, pm_index, group_stop_history, last_time_in_zone, potential_matches_to_delete):
    # 22.1 move the potential match to be a match
    potential_matches_to_delete.append(pm_index)
    group_stop_history["matched_stops"].update(
        {pm_index: {"last_match_time": last_time_in_zone}}
    )
    # 22.2 update last match index to current potential match index
    group_stop_history["last_match"] = pm_index
    log_specific(rec['operator_ref'], rec['line_name'], f"22. moved {pm_index} to matched stops")
    log_specific(rec['operator_ref'], rec['line_name'], f"22. updated last match: {group_stop_history['last_match']}")
    log_specific(rec['operator_ref'], rec['line_name'], f"22. updated matched stop stop {pm_index}: {group_stop_history['matched_stops'][pm_index]}")                      
    
def writeMatchedStopToDb(is_final_stop, stop_pos_distances, group_id, pm_index, time_difference, last_time_in_zone, batch_id, timetable_departure_time):
    timetable_id = global_timetable_dict[group_id][pm_index][2]
    if is_final_stop:
        otp_state = getOtpState(True, time_difference)
        stop_type = 'final'
    else:
        otp_state = getOtpState(False, time_difference)
        stop_type = 'Non-final'
    # 23. update db with potential match details
    stop_pos_distances[group_id].update(
        { 
            pm_index: (
                time_difference,
                str(
                    last_time_in_zone.strftime(
                        "%H:%M:%S"
                    )
                ),
                timetable_id,
                group_id,
                batch_id,
                last_time_in_zone,
                otp_state,
                stop_type,
            )
        }
    )
                                                
def updatePotentialMatch(rec, pm_index, pm_details, current_avl_index, avl_pm_distance, recorded_at_time=None):
    pm_details["last_avl_index"] = current_avl_index
    pm_details["last_distance"] = avl_pm_distance
    if recorded_at_time is not None:
        pm_details["last_time_in_zone"] = recorded_at_time
    log_specific(operator_ref, line_name, f"18. updated potential match {pm_index}")
    log_specific(operator_ref, line_name, f"18. updated potential match {pm_details}")

def findPreviousMatchLastTimeInZone(previous_pm_index, group_stop_history):
    if previous_pm_index in group_stop_history["potential_matches"]:
        previous_match_last_time_in_zone = validateDate(group_stop_history["potential_matches"][previous_pm_index]["last_time_in_zone"])
    elif previous_pm_index in group_stop_history["matched_stops"]:
        previous_match_last_time_in_zone = validateDate(group_stop_history["matched_stops"][previous_pm_index]["last_match_time"])
    else:
        logger.debug(f"{previous_pm_index} not in matched_stops or potential matches")
        previous_match_last_time_in_zone = None
    return previous_match_last_time_in_zone

def checkPreviousMatchIsMatched(rec, previous_pm_index, previous_match_last_time_in_zone, group_stop_history, last_time_in_zone):
    if previous_match_last_time_in_zone is not None:
        if (
            previous_pm_index 
            in group_stop_history["potential_matches"] 
            or previous_pm_index
            in group_stop_history["matched_stops"]
            or previous_pm_index
            == group_stop_history["last_match"]
        ) and (last_time_in_zone.timestamp() > previous_match_last_time_in_zone.timestamp()):
            log_specific(operator_ref, line_name, "21. previous stop index is a previous match/potential match and recorded at time > previous match last time in zone")                              
            return True
    else:
        return False

def movePotentialMatchToMatch(is_final_stop, rec, pm_index, group_stop_history, last_time_in_zone, timetable_departure_time, potential_matches_to_delete, stop_pos_distances, group_id, batch_id):
    time_difference =  last_time_in_zone.timestamp() - validateDate(timetable_departure_time).timestamp()
    updateMatchedStop(rec, pm_index, group_stop_history, last_time_in_zone, potential_matches_to_delete)
    checkTimeDifference(time_difference, last_time_in_zone, timetable_departure_time)
    writeMatchedStopToDb(is_final_stop, stop_pos_distances, group_id, pm_index, time_difference, last_time_in_zone, batch_id, timetable_departure_time)
                                                
def positionsTimetableLookup(
    shard_no, avl_dict, timetable_output, batch_id=None, stop_history={}
):
    stop_pos_distances = {}
    stop_pos_distances_remove = []
    shard_filter = []
    distance_threshold = 70
    minute = 60
    if shard_no == "0":
        for n in range(1,no_of_shards+1):
            shard_filter.extend(shards["shards"][str(n)])
    else:
        shard_filter = shards["shards"][str(shard_no)]
    for rec in avl_dict:
        if (shard_no != "0" and rec['operator_ref'] in shard_filter) or (shard_no == "0" and rec['operator_ref'] not in shard_filter):
            group_id = f"{rec['operator_ref']}{rec['line_name']}{rec['journey_ref']}{str(rec['date_of_journey'])}"
            avl_latlong = (rec["latitude"], rec["longitude"])
            operator_ref = rec['operator_ref']
            line_name = rec['line_name']
            # 1. check if group id exists in timetable
            if group_id in global_timetable_dict.keys():
                stop_pos_distances.update({group_id: {}})
                log_specific(operator_ref, line_name, f"group_id {group_id} in timetable")
                final_stop_index = len(global_timetable_dict[group_id])

                # standardise recorded_at_time format
                recorded_at_time_str = rec["recorded_at_time"][:19]
                recorded_at_time = validateDate(recorded_at_time_str)
                recorded_at_time_utc = recorded_at_time.replace(tzinfo=utc)
                recorded_at_time_utc_str = datetime.strftime(recorded_at_time_utc, "%Y-%m-%dT%H:%M:%S")
                # 2. check if group id exists in stop_history, if not, create a blank group stop history
                if group_id not in stop_history.keys():
                    stop_history[group_id] = {
                        "last_match": "0",
                        "last_avl_time": "",
                        "last_avl_index": 0,
                        "matched_stops": {},
                        "potential_matches": {},
                    }
                group_stop_history = stop_history.get(group_id)
                current_avl_index = group_stop_history.get("last_avl_index")
                # 3. check if current recorded_at_time is the same as the last avl time in group_stop_history
                # ! recorded at time > last avl time?
                if recorded_at_time_utc != group_stop_history.get("last_avl_time") or recorded_at_time_utc_str != group_stop_history.get("last_avl_time"):
                    # 4. increment last avl index by 1 and update the time
                    current_avl_index += 1
                    group_stop_history["last_avl_index"] = current_avl_index
                    # getting the last avl time before the update for step 5
                    if group_stop_history["last_avl_time"] == "":
                        last_avl_time = recorded_at_time_utc
                    else:
                        if isinstance(group_stop_history["last_avl_time"], datetime):
                            last_avl_time = group_stop_history["last_avl_time"]
                        else:
                            last_avl_time = datetime.strptime(group_stop_history["last_avl_time"][:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=utc)
                    group_stop_history["last_avl_time"] = recorded_at_time_utc

                    last_matched_stop_index = group_stop_history.get("last_match")

                    # 5. check if any matched stop is more than 5 minutes ago except the last match stop
                    matched_stop_to_delete = []
                    log_specific(operator_ref, line_name, f"matched stops: {group_stop_history['matched_stops']}")
                    if len(group_stop_history["matched_stops"]) > 0:
                        log_specific(operator_ref, line_name, "5. looping through matched stops")
                        for ms_index, ms_details in group_stop_history["matched_stops"].items():
                            last_match_time = ms_details["last_match_time"] if isinstance(ms_details["last_match_time"], datetime) else datetime.strptime(ms_details["last_match_time"][:19], '%Y-%m-%d %H:%M:%S')
                            if (last_avl_time - last_match_time.replace(tzinfo=utc)).total_seconds() > 300 and ms_index != sorted(group_stop_history["matched_stops"].keys(),key=int)[-1]:
                                matched_stop_to_delete.append(ms_index)
                        log_specific(operator_ref, line_name, f"deleting matched stop indices: {matched_stop_to_delete}")
                        # discard all matched stop list records except the last match stop if last match time > 5 minutes ago
                        for d_ind in matched_stop_to_delete:
                            if d_ind != last_matched_stop_index:
                                del group_stop_history["matched_stops"][d_ind]

                        # 6+7. Check if avl < distance threshold from matched stop stop 1
                        # and avl is within 5 mins after the last stop 1 matching time
                        if "1" in group_stop_history["matched_stops"] and "1" in global_timetable_dict[group_id]:
                            log_specific(operator_ref, line_name, "Stop 1 is in matched stops")
                            ms_index = "1"
                            ms_latlong = global_timetable_dict[group_id][ms_index][0]
                            ms_details = group_stop_history["matched_stops"][ms_index]
                            ms_last_match_time = ms_details["last_match_time"] if isinstance(ms_details["last_match_time"], datetime) else datetime.strptime(ms_details["last_match_time"][:19], "%Y-%m-%d %H:%M:%S")
                            avl_ms_distance = haversine(avl_latlong, ms_latlong)
                            if avl_ms_distance < distance_threshold:
                                log_specific(operator_ref, line_name, f"6+7. avl is {avl_ms_distance}m, within {distance_threshold}m")
                                # 8. if avl is within 5 mins after the last first stop matching time
                                if recorded_at_time.timestamp() - ms_last_match_time.timestamp() < 5 * minute:
                                    log_specific(operator_ref, line_name, "6+7. Last match time is witin 5 mins after recorded at time")
                                    # 9.1 delete matched first stop
                                    del group_stop_history["matched_stops"][ms_index]
                                    # 9.2 set this match as a potential match
                                    group_stop_history["potential_matches"].update(
                                        {
                                            ms_index: {
                                                "last_avl_index": current_avl_index,
                                                "last_distance": avl_ms_distance,
                                                "last_time_in_zone": recorded_at_time_utc,
                                            }
                                        }
                                    )

                                    # 9.3 unmatch the last matched stop
                                    group_stop_history["last_match"] = "0"

                                    log_specific(operator_ref, line_name, f"updated last match: {group_stop_history['last_match']}")
                                    log_specific(operator_ref, line_name, f"updated stop 1 potential match: {group_stop_history['potential_matches'][ms_index]}")
                                    # 10. remove db matched details
                                    timetable_id = global_timetable_dict[group_id][ms_index][2]
                                    stop_pos_distances_remove.append((ms_index, timetable_id, group_id))
                                            
                    # 11. Find a potential match in all stops after the last matched stop
                    # including final stop here so there will be a match to the final stop
                    log_specific(operator_ref, line_name, "11. find potential matches in all stops after the last matched stop")
                    for i in range(
                        int(last_matched_stop_index) + 1,
                        final_stop_index + 1
                    ):
                        next_stop_latlong = global_timetable_dict[group_id][str(i)][0]
                        avl_next_stop_distance = haversine(
                            avl_latlong, next_stop_latlong
                        )
                        # 12. If avl and the next stop distance < threshold
                        if avl_next_stop_distance < distance_threshold:
                            log_specific(operator_ref, line_name, f"12. avl is {avl_next_stop_distance}m from stop {i}, less than {distance_threshold}m")
                            # 13. create potential match
                            group_stop_history["potential_matches"].update(
                                {
                                    str(i): {
                                        "last_avl_index": current_avl_index,
                                        "last_distance": avl_next_stop_distance,
                                        "last_time_in_zone": recorded_at_time_utc,
                                    }
                                }
                            )
                            log_specific(operator_ref, line_name, f"13. potential match (stop{i}) created: {group_stop_history['potential_matches'][str(i)]}")
                    group_stop_history["potential_matches"] = dict(sorted(group_stop_history["potential_matches"].items()))

                    # Check if avl is anywhere within the zone of a potential match
                    # 14. For each potential match
                    if len(group_stop_history.get("potential_matches")) > 0:
                        potential_matches_to_delete = []
                        potential_matches = group_stop_history.get("potential_matches")
                        log_specific(operator_ref, line_name, "14. looping through potential matches")
                        for pm_index, pm_details in potential_matches.items():
                            if pm_index in global_timetable_dict[group_id]:
                                # calculate distance between avl and potential match stops
                                avl_pm_distance = haversine(
                                    avl_latlong, global_timetable_dict[group_id][pm_index][0]
                                )
                                expected_departure_time = global_timetable_dict[group_id][pm_index][
                                    1
                                ]
                                timetable_id = global_timetable_dict[group_id][pm_index][2]
                                timetable_date_of_journey = global_timetable_dict[group_id][pm_index][3]
                                timetable_departure_time = (
                                    f"{timetable_date_of_journey} {expected_departure_time}"
                                )
                                previous_pm_index = str(int(pm_index) - 1)
                                previous_match_last_time_in_zone = findPreviousMatchLastTimeInZone(previous_pm_index, group_stop_history)
                                last_time_in_zone = validateDate(pm_details["last_time_in_zone"])
                                last_distance = pm_details["last_distance"]
                                # time_difference =  last_time_in_zone.timestamp() - validateDate(timetable_departure_time).timestamp()
                                # 15. If the distance between avl and potential match is less than threshold
                                if avl_pm_distance < distance_threshold:
                                    log_specific(operator_ref, line_name, f"15. avl is {avl_pm_distance}m from stop {pm_index}, less than {distance_threshold}m")
                                    # 16. Distance between avl and potential match stop is less than threshold
                                    # check if the potential match is the final stop of the route
                                    if int(pm_index) == final_stop_index:
                                        log_specific(operator_ref, line_name, f"16. {pm_index} is final stop")
                                        # 16.2 Check if the previous potential index is a potential match or a match and 
                                        # 16.3 if the potential match last time in zone is greater than the potential match (n-1) last time in zone
                                        if pm_index not in group_stop_history["matched_stops"] and checkPreviousMatchIsMatched(rec, previous_pm_index, previous_match_last_time_in_zone,  group_stop_history, last_time_in_zone):
                                            log_specific(operator_ref, line_name, f"17. {pm_index} is not matched")
                                            # 22-23. move potential match to be a match
                                            movePotentialMatchToMatch(True, rec, pm_index, group_stop_history, last_time_in_zone, timetable_departure_time, potential_matches_to_delete, stop_pos_distances, group_id, batch_id)
                                            # move the potential match n-1 to be a match
                                            if previous_pm_index in group_stop_history["potential_matches"]:
                                                movePotentialMatchToMatch(False, rec, previous_pm_index, group_stop_history, previous_match_last_time_in_zone, timetable_departure_time, potential_matches_to_delete, stop_pos_distances, group_id, batch_id)
                                    else:
                                        # 18. The potential match is not a final stop, update potential match with current avl data
                                        log_specific(operator_ref, line_name, f"16. stop {pm_index} is not a final stop")
                                        updatePotentialMatch(rec, pm_index, pm_details, current_avl_index, avl_pm_distance, recorded_at_time_utc)
                                else:
                                    # 15. avl > distance threshold from potential match stop
                                    # Find one more row of avl that is away from the stop
                                    # 19. Check if pm last distance > distance threshold
                                    log_specific(operator_ref, line_name, f"15. avl is {avl_pm_distance}m from stop {pm_index}, greater than {distance_threshold}m")
                                    if last_distance > distance_threshold:
                                        log_specific(operator_ref, line_name, f"19. Last distance {last_distance}m > {distance_threshold}m")
                                        # 20. check if the avl potential distance > last distance
                                        if avl_pm_distance > last_distance:
                                            log_specific(operator_ref, line_name, f"20. avl potential distance {avl_pm_distance}m > Last distance {last_distance}m")
                                            # avl is confirmed to be getting away from the stop with last distance > 70m
                                            # 21.1 Check if this is the first stop to match
                                            if int(pm_index)-1 == 0:
                                                movePotentialMatchToMatch(False, rec, pm_index, group_stop_history, last_time_in_zone, timetable_departure_time, potential_matches_to_delete, stop_pos_distances, group_id, batch_id)
                                            # If it's not the first match
                                            # 21.1 Check if the previous potential index is a potential match or a match and
                                            # 21.2 if the potential match last time in zone is greater than the potential match (n-1) last time in zone
                                            elif checkPreviousMatchIsMatched(rec, previous_pm_index, previous_match_last_time_in_zone, group_stop_history, last_time_in_zone):
                                                movePotentialMatchToMatch(False, rec, pm_index, group_stop_history, last_time_in_zone, timetable_departure_time, potential_matches_to_delete, stop_pos_distances, group_id, batch_id)
                                                if previous_pm_index in group_stop_history["potential_matches"]:
                                                    movePotentialMatchToMatch(False, rec, previous_pm_index, group_stop_history, previous_match_last_time_in_zone, timetable_departure_time, potential_matches_to_delete, stop_pos_distances, group_id, batch_id)
                                            else:
                                                # 21.1 the previous potential index is NOT a potential match or a match
                                                # and 21.2 avl time is NOT greater than the potential match (n-1) last time in zone
                                                # 25. update potential match with current avl index and distance between potential match stop and avl location
                                                updatePotentialMatch(rec, pm_index, pm_details, current_avl_index, avl_pm_distance)
                                        else:
                                            # 20. the avl potential distance < last distance
                                            # Avl is moving backwards
                                            # 24. update potential match with current avl index and distance between potential match stop and avl location
                                            updatePotentialMatch(rec, pm_index, pm_details, current_avl_index, avl_pm_distance)
                                    else:
                                        # 19. pm last distance < distance threshold
                                        # 25. update potential match with current avl index and distance between potential match stop and avl location
                                        updatePotentialMatch(rec, pm_index, pm_details, current_avl_index, avl_pm_distance)
                        # 22.1 remove matched stops from potential matches
                        if len(potential_matches_to_delete) > 0:
                            potential_matches_to_delete = set(potential_matches_to_delete)
                            for pm_index in potential_matches_to_delete:
                                del group_stop_history["potential_matches"][pm_index]
    timetable_output["set"].update(stop_pos_distances)
    timetable_output["remove"].extend(stop_pos_distances_remove)
    return timetable_output, stop_history

def getOtpState(is_final_stop, time_difference):
    if is_final_stop:
        if time_difference > 359:
            otp_state = "Late"
        else:
            otp_state = "OnTime"
    else:
        if time_difference < -60:
            otp_state = "Early"
        elif time_difference > 359:
            otp_state = "Late"
        else:
            otp_state = "OnTime"
    return otp_state

def coldStart():
    readTimetable()
    readShards()
    return

def haversine(position_latlong, stop_lat_long):
    """
    Calculate the great circle distance in kilometers between two points 
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians 
    lat1, lon1 = position_latlong
    lat2, lon2 = stop_lat_long
    
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371 # Radius of earth in kilometers. Use 3956 for miles. Determines return value units.
    return (c * r) * 1000

def read_avl(fname):
    colnames = ['recorded_at_time', 'response_timestamp', 'latitude', 'longitude', 'line_name', 'operator_ref', 'vehicle_ref', 'journey_ref', 'direction_ref', 'date_of_journey', 'batch_id']
    df = wr.s3.read_csv(path=f"s3://{sirivm_bucket}/{fname}", names = colnames, header = None)
    avl_dict = df.to_dict('records')
    return avl_dict

def get_rds_token():
    client = session.client('rds')
    try:
        token = client.generate_db_auth_token(DBHostname=db_host, Port=db_port, Region=region, DBUsername=db_user)
    except Exception:
        logging.error("could not get token ")
        
    return token

def write_to_s3(data_dict,path):
    data_string = json.dumps(data_dict, default=str)
    
    client.put_object(
        Bucket=sirivm_bucket, 
        Key=path,
        Body=data_string
    )
    return

try:
    read_timetable = time.process_time()
    coldStart()
    logger.info(f"Reading timetable and shard history: {time.process_time()-read_timetable}")
except Exception as e:
    logging.error(f'Error {e}')

def lambda_handler(event, context):
    for rec in event['Records']:
        if rec["messageAttributes"].get('Historic'):
            backfill_lambda_handler(event, context)
        else:
            live_lambda_handler(event, context)

def backfill_lambda_handler(event, context):
    """Fetch the historic avl record and timetable to do historic otp matching"""
    try:
        for rec in event['Records']:
            fname = rec['messageAttributes']['key']['stringValue']
            shard_no = rec['messageAttributes']['shard']['stringValue']
            logging.info(f"OTP data being processed for file {fname}")
            # fetch avl data
            avl_dict = read_avl(fname)
            # find a timetable for matching
            avl_time = fname[fname.index("avl_")+4:-3]
            avl_datetime = parse(avl_time)
            avl_year = avl_datetime.year
            avl_month = str(avl_datetime.month).zfill(2)
            avl_day = str(avl_datetime.day).zfill(2)
            avl_hour = str(avl_datetime.hour).zfill(2)
            avl_minute = "00" if avl_datetime.minute < 30 else "30"
            timetable_dir = f"timetable_shreds/YYYY={avl_year}/MM={avl_month}/DD={avl_day}/"
            timetable_name = f"timetable_{avl_year}{avl_month}{avl_day}_{avl_hour}_{avl_minute}.json"
            timetable_path = timetable_dir + timetable_name
            # fetch timetable s3 
            readTimetable(timetable_path)
            timetable_output = {'set': {}, 'remove': []}
            read_hist_start = time.process_time()
            shard_stop_history = readStopHistory(f"{avl_year}-{avl_month}-{avl_day}", shard_no, int(avl_time))
            logging.info(f"Read stop history: {time.process_time()-read_hist_start}")
            # for recovery, only process avl file that is greater than last process avl file
            if int(avl_time) >= int(shard_stop_history["control_info"]["last_avl"]):
                # clean stop history
                clean_start = time.process_time()
                clean_shard_stop_history = cleanStopHistory(shard_stop_history, avl_datetime)
                logging.info(f"Clean stop history: {time.process_time()-clean_start}")
                logging.info("Run matching")
                start_time = time.process_time()
                timetable_output, stop_history = positionsTimetableLookup(shard_no, avl_dict, timetable_output, None, clean_shard_stop_history)
                end_time, sql_start = time.process_time(), time.process_time()
                # Recalculating time difference when it's less than zero to make sure it's calculated correctly
                sql_query = """
                        update  public."Timetable" u
                        set
                            time_difference = case when t.time_difference::int < 0 then extract(epoch from (t.last_time_in_zone_utc::timestamp at TIME zone 'utc' - u.expected_departure_time::timestamp))::int else t.time_difference::int end,
                            actual_departure_time = t.last_time_in_zone_utc::timestamp at TIME zone 'utc',
                            load_time_stamp = now()::timestamp(0)
                        from (values %s) as t(time_difference, last_time_in_zone_str, timetable_id, group_id, batch_id, last_time_in_zone_utc, otp_state, is_final_stop, journey_date)
                        where u.timetable_id = t.timetable_id::int and date_of_journey = t.journey_date::date and coalesce(extract (epoch from (t.last_time_in_zone_utc::timestamp at TIME zone 'utc' - u.expected_departure_time)),0) > -7200;
                    """
                sql_query_otp_update = """
                        update  public."Timetable" u
                        set
                            otp_state = case when u.time_difference::int > 359 then 'Late' when (is_final_stop = 'Non-final' and u.time_difference::int < -60) then 'Early' else 'OnTime' end,
                            load_time_stamp = now()::timestamp(0)
                        from (values %s) as t(time_difference, last_time_in_zone_str, timetable_id, group_id, batch_id, last_time_in_zone_utc, otp_state, is_final_stop, journey_date)
                        where u.timetable_id = t.timetable_id::int and date_of_journey = t.journey_date::date and coalesce(extract (epoch from (t.last_time_in_zone_utc::timestamp at TIME zone 'utc' - u.expected_departure_time)),0) > -7200;
                    """
                sql_remove_query = """
                    update  public."Timetable" u
                    set
                        time_difference = null,
                        actual_departure_time = null,
                        otp_state = null,
                        load_time_stamp = now()::timestamp(0)
                    from (values %s) as t(stop_ind, timetable_id, group_id, journey_date)
                    where u.timetable_id = t.timetable_id::int and date_of_journey = t.journey_date::date and u.group_id = t.group_id and u.stop_index = t.stop_ind::int;
                """
                try:
                    conn = psycopg2.connect(host = db_host, port = db_port, database = db_database, user = db_user, password = get_rds_token(), sslmode = 'require')
                    conn.autocommit = True
                    cur = conn.cursor()
                    if len(timetable_output["remove"]) > 0:
                        for item in timetable_output["remove"]:
                            item_list = list(item)
                            item_list.append(f"{avl_year}-{avl_month}-{avl_day}")
                            item_with_date = tuple(item_list)
                            logging.info(f"Removing {item_with_date} from db")
                            execute_values(cur, sql_remove_query, [item_with_date])
                    if len(timetable_output["set"]) > 0:
                        for group_id, match_index_dict in timetable_output["set"].items():
                            if len(match_index_dict) > 0:
                                for v_to_set in match_index_dict.values():
                                    v_list = list(v_to_set)
                                    v_list.append(f"{avl_year}-{avl_month}-{avl_day}")
                                    v_to_set_with_date = tuple(v_list)
                                    logging.info(f"writing {v_to_set_with_date} to db")
                                    execute_values(cur, sql_query, [v_to_set_with_date])
                                    # Update otp state again as the otp calculation is not taking the updated time difference value
                                    execute_values(cur, sql_query_otp_update, [v_to_set_with_date])
                    logging.info(f"{fname} historic matching successful")
                    # cur.execute("Update public.batch set otp_update_status = 'Success' where avl_fname=%s ;", [fname])
                    sql_end, s3_start = time.process_time(), time.process_time()
                    write_to_s3(stop_history,f'timetable_avl/{avl_year}-{avl_month}-{avl_day}/timetable_avl_stop_history_shard{shard_no}.json')
                    s3_end = time.process_time()
                    logging.info(f"OTP data updated for file {fname}, Process AVL time: {end_time-start_time}, Write to db time: {sql_end-sql_start}, Write to s3 time: {s3_end-s3_start}")
                except Exception as e:
                    logging.exception(e, stack_info=True, exc_info=True)
            else:
                logging.info(f"{avl_time} has been processed, skipping.")
    except Exception as e:
        logging.exception(e, stack_info=True, exc_info=True)
    return

def live_lambda_handler(event, context):
    print(event)
    try: 
        lambda_start = time.process_time()
        currentDate = datetime.today().strftime('%Y-%m-%d')
        for rec in event['Records']:
            if rec['messageAttributes']['key']['stringValue'] != 'timetable':
                fname = rec['messageAttributes']['key']['stringValue']
                batch_id = rec['messageAttributes']['batch_id']['stringValue']
                shard_no = rec['messageAttributes']['shard']['stringValue']
                logging.info(f"OTP data being processed for file {fname}")
                # Check if avl file coming in in order
                avl_time_val =  int(fname[-17:-3])
                avl_datetime = parse(str(avl_time_val))
                avl_dict = read_avl(fname)
                timetable_output = {'set': {}, 'remove': []}
                # read stop history of the shard
                read_hist_start = time.process_time()
                shard_stop_history = readStopHistory(currentDate, shard_no, avl_time_val)
                logging.info(f"Read stop history: {time.process_time()-read_hist_start}")
                # clean stop history
                clean_start = time.process_time()
                clean_shard_stop_history = cleanStopHistory(shard_stop_history, avl_datetime)
                logging.info(f"Clean stop history: {time.process_time()-clean_start}")

                start_time = time.process_time()
                timetable_output, stop_history = positionsTimetableLookup(shard_no, avl_dict, timetable_output, batch_id, clean_shard_stop_history)
                end_time, sql_start = time.process_time(), time.process_time()
                sql_query = """
                    update  public."Timetable" u
                    set
                        time_difference = t.time_difference::int,
                        actual_departure_time = t.last_time_in_zone_utc::timestamp at TIME zone 'utc',
                        otp_state = t.otp_state::TEXT,
                        load_time_stamp = now()::timestamp(0)
                    from (values %s) as t(time_difference, last_time_in_zone_str, timetable_id, group_id, batch_id, last_time_in_zone_utc, otp_state, is_final_stop)
                    where u.timetable_id = t.timetable_id::int and date_of_journey = now()::date and coalesce(extract (epoch from (t.last_time_in_zone_utc::timestamp at TIME zone 'utc' - u.expected_departure_time)),0) > -7200;
                """
                sql_remove_query = """
                    update  public."Timetable" u
                    set
                        time_difference = null,
                        actual_departure_time = null,
                        otp_state = null,
                        load_time_stamp = now()::timestamp(0)
                    from (values %s) as t(stop_ind, timetable_id, group_id)
                    where u.timetable_id = t.timetable_id::int and date_of_journey = now()::date and u.group_id = t.group_id and u.stop_index = t.stop_ind::int;
                """
                try:
                    conn = psycopg2.connect(host = db_host, port = db_port, database = db_database, user = db_user, password = get_rds_token(), sslmode = 'require')
                    conn.autocommit = True
                    cur = conn.cursor()
                    execute_values(cur, sql_remove_query, timetable_output["remove"])
                    for group_id, match_index_dict in timetable_output["set"].items():
                        if len(match_index_dict) > 0:
                            for v_to_set in match_index_dict.values():
                                execute_values(cur, sql_query, [v_to_set])
                            logging.info(f"Writing group {group_id}, matched stop(s) {list(timetable_output['set'][group_id].keys())} to db")
                    cur.execute("Update public.batch set otp_update_status = 'Success' where batch_id=%s ;", [batch_id])
                    sql_end, s3_start = time.process_time(), time.process_time()
                    write_to_s3(stop_history,f'timetable_avl/{currentDate}/timetable_avl_stop_history_shard{shard_no}.json')
                    s3_end = time.process_time()
                    logging.info(f"OTP data updated for file {fname}, Process AVL time: {end_time-start_time}, Write to db time: {sql_end-sql_start}, Write to s3 time: {s3_end-s3_start}")
                except Exception as e:
                    logging.error(f'Error {e}')
                    if batch_id:
                        cur.execute("Update public.batch set otp_update_status = 'Failed' where batch_id=%s ;", [batch_id])
            else:
                logging.info("Refresh Timetable")
                timetable_start = time.process_time()
                readTimetable()
                logger.info(f"Refresh timetable: {time.process_time()-timetable_start}")

    except Exception as e:
        logging.error(f'Error connecting to abods DB. Error {e}')
        traceback.print_exc()
        if batch_id:
            try: 
                cur.execute("Update public.batch set otp_update_status = 'Failed' where batch_id=%s ;", [batch_id])
            except Exception as e:
                logging.error(f'Error connecting to abods DB. Error {e}')
    try:
        logger.info(f"Entire lambda process: {time.process_time()-lambda_start}")
    except Exception as e:
        logging.error(f'Error {e}')
    return