TIMETABLE_EXTRACT_SLIDING_WINDOW_TIME_IN_MINUTES = 2 * 60
"Period of time that the timetable extract for live matching should cover"

EXPECTED_LATE_RUNNING_SERVICE_INTERVAL_IN_MINUTES = 12 * 60
"""Maximum amount of time that late running services are expected to continue past midnight"""

MATCH_ZONE_RADIUS_IN_METERS = 70
"""Radius around a stop that a ping within is considered 'at' the stop"""

SAVED_MATCHES_LIMIT = 2
"""Number of matches to be retained in stop history"""

SHORT_JOURNEY_STOP_COUNT = 3
"""Max length of a journey is considered a short journey"""

END_OF_JOURNEY_PROPORTION = 3 / 4
"""Proportion of the journey that is considered the 'end' of the journey"""

ESTIMATED_MATCHING_TIME_UPPER_LIMIT_IN_SECONDS = 180
"""Maximum time between pings that can be considered for estimated matching"""

ESTIMATED_MATCHING_DISTANCE_UPPER_LIMIT_IN_METRES = 2000
"""Maximum distance between pings that can be considered for estimated matching"""

MATCHING_TIME_LOWER_LIMIT_IN_SECONDS = -2 * 60 * 60
"""Maximum time before expected departure time that an early AVL can still be matched"""

MATCHING_TIME_UPPER_LIMIT_IN_SECONDS = 1 * 60 * 60
"""Maximum time after expected departure time that a late AVL can still be matched"""

RADIUS_OF_EARTH_IN_METERS = 6_371_000
"""Used for determining distances between points"""

TIMETABLE_UPDATED_NOTIFICATION_SQS_KEY_VALUE = "timetable"
"""Value passed by the extract generation to trigger otp matching to refresh the cached timetable extract"""

EARLY_THRESHOLD_IN_SECONDS = 60
"""The time difference between a match and the expected departure time must be more than this for the match to be considered early"""

LATE_THRESHOLD_IN_SECONDS = 359
"""The time difference between a match and the expected departure time must be more than this for the match to be considered late"""
