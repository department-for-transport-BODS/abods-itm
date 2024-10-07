from .matcher_config import config
from .models import AVLRecord
from .utils import log_specific, haversine

distance_threshold = config.get("distance_threshold")


def get_lowest_matched_stop_index(group_stop_history: dict) -> int:
    """Get the lowest matched stop index if the matched stop list has 2 saved matches

    Args:
        group_stop_history (dict): Stop history of the current group id

    Returns:
        int: Lowest_matched_stop_index
    """
    matched_stops = group_stop_history["matched_stops"]
    # 11. Are there 2 actual matches already stored?
    if len(matched_stops) > 1:
        # ordered_matched_stops = dict(sorted(matched_stops.items(), key=lambda t: int(t[0])))
        # 12. Select the lowest index of these 2 stops
        lowest_matched_stop_index = min(list(matched_stops.keys()), key=int)
    else:
        # 12. Select all stops
        lowest_matched_stop_index = 0
    return lowest_matched_stop_index


def find_potential_matches(
    avl: AVLRecord,
    timetable_dict: dict,
    group_stop_history: dict,
    current_avl_index: int,
    final_stop_index: int,
) -> None:
    """Find potential matches after the last match

    Args:
        avl (AVLRecord): Avl record
        timetable_dict (dict): Timetable data
        group_stop_history (dict): Stop history of the current group id
        current_avl_index (int): Current avl index
        final_stop_index (int): The stop index of the final stop
    """
    # 11-12. get the stop index to start for finding potential matches
    lowest_matched_stop_index = get_lowest_matched_stop_index(group_stop_history)
    for i in range(int(lowest_matched_stop_index) + 1, final_stop_index + 1):
        next_stop_latlong = timetable_dict[avl.group_id][str(i)][0]
        avl_next_stop_distance = haversine(avl, next_stop_latlong)
        # 13. If avl and the next stop distance < threshold
        if avl_next_stop_distance < distance_threshold:
            log_specific(
                avl,
                f"12. avl is {avl_next_stop_distance}m from stop {i}, less than {distance_threshold}m",
            )
            # 14. create potential match
            group_stop_history["potential_matches"].update(
                {
                    str(i): {
                        "last_avl_index": current_avl_index,
                        "last_distance": avl_next_stop_distance,
                        "last_time_in_zone": avl.recorded_at_time_utc,
                    }
                }
            )
            log_specific(
                avl,
                f"13. potential match (stop{i}) created: {group_stop_history['potential_matches'][str(i)]}",
            )
