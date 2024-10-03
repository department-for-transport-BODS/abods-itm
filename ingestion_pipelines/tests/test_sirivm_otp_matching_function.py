import unittest
from sirivm_otp_matching_function.app import positionsTimetableLookup

class TestPositionsTimetableLookup(unittest.TestCase):
    def setUp(self):
        self.timetable_test_output_1 = []
        self.timetable_test_output_2 = [(-100, "13:21:20", 518770951, 1.9317099225915164, 'A2BV112232024-05-01', {}, '2024-05-01T12:21:20')]
        self.empty_last_position_dict = {}
        self.last_position_dict_1 = {"A2BV112232024-05-01": {"last_position": "1", "distance": 29.64979374920034, "recorded_at_time": "2024-05-01T12:21:20", "otp_state": "Early"}}
        self.last_position_dict_2 = {"A2BV112232024-05-01": "6"}
        self.avl_test_1 = [
            {"recorded_at_time": "2024-05-01T12:21:20+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.401907, "longitude": -3.111911, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:21:56+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40248, "longitude": -3.11219, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
        ]
        self.avl_test_2 = [
            {"recorded_at_time": "2024-05-01T12:21:20+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.401907, "longitude": -3.111911, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:21:56+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40248, "longitude": -3.11219, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:26:27+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40452, "longitude": -3.11289, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:32:40+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40601, "longitude": -3.11352, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:37:10+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40679, "longitude": -3.11018, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:37:40+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.4072, "longitude": -3.10768, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
        ]
        self.avl_test_3 = [
            {"recorded_at_time": "2024-05-01T12:21:20+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.401907, "longitude": -3.111911, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1323", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:21:56+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40248, "longitude": -3.11219, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1323", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
        ]
        self.avl_test_4 = [
            {"recorded_at_time": "2024-05-01T12:21:20+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.401907, "longitude": -3.111911, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:21:56+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40248, "longitude": -3.11219, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1323", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
        ]
        self.avl_test_5 = [
            {"recorded_at_time": "2024-05-01T12:56:21+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40314, "longitude": -3.10315, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:57:21+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40306, "longitude": -3.10335, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T13:00:21+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40283, "longitude": -3.10392, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T13:03:21+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40215, "longitude": -3.10523, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T13:03:56+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40399, "longitude": -3.11258, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T13:06:10+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40229, "longitude": -3.11204, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
        ]
        self.avl_test_6 = [
            {"recorded_at_time": "2024-05-01T12:18:40+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.400799, "longitude": -3.111292, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:19:40+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.401421, "longitude": -3.111568, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:20:40+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.401675, "longitude": -3.111745, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:21:20+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.401907, "longitude": -3.111911, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:21:56+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40248, "longitude": -3.11219, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:26:27+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40452, "longitude": -3.11289, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:32:40+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40601, "longitude": -3.11352, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:37:10+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40679, "longitude": -3.11018, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:37:40+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.4072, "longitude": -3.10768, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:38:10+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40732, "longitude": -3.10595, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:39:15+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40734, "longitude": -3.10565, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:45:15+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.4068, "longitude": -3.10514, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:45:20+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40604, "longitude": -3.10432, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:48:20+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40583, "longitude": -3.10671, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:49:20+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40574, "longitude": -3.10713, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:53:21+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40394, "longitude": -3.10321, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:56:21+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40314, "longitude": -3.10315, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T12:57:21+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40306, "longitude": -3.10335, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T13:00:21+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40283, "longitude": -3.10392, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T13:03:21+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40215, "longitude": -3.10523, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T13:03:56+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40399, "longitude": -3.11258, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T13:06:10+00:00", "response_timestamp": "2024-05-01T14:04:40+00:00", "latitude": 53.40229, "longitude": -3.11204, "line_name": "1", "operator_ref": "A2BV", "vehicle_ref": "YJ60_KFC", "journey_ref": "1223", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
        ]
        self.avl_test_7 = [
            {"recorded_at_time": "2024-05-01T10:01:24+00:00", "response_timestamp": "2024-05-01T12:01:40+00:00", "latitude": 53.39852, "longitude": -3.16911, "line_name": "100", "operator_ref": "A2BV", "vehicle_ref": "AB30_PCC", "journey_ref": "1000", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T10:06:58+00:00", "response_timestamp": "2024-05-01T12:01:40+00:00", "latitude": 53.39657, "longitude": -3.17288, "line_name": "100", "operator_ref": "A2BV", "vehicle_ref": "AB30_PCC", "journey_ref": "1000", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T10:14:00+00:00", "response_timestamp": "2024-05-01T12:01:40+00:00", "latitude": 53.39121, "longitude": -3.17919, "line_name": "100", "operator_ref": "A2BV", "vehicle_ref": "AB30_PCC", "journey_ref": "1000", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T10:17:00+00:00", "response_timestamp": "2024-05-01T12:01:40+00:00", "latitude": 53.39097, "longitude": -3.17971, "line_name": "100", "operator_ref": "A2BV", "vehicle_ref": "AB30_PCC", "journey_ref": "1000", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T08:30:07+00:00", "response_timestamp": "2024-05-01T12:01:40+00:00", "latitude": 53.37693, "longitude": -3.11693, "line_name": "129", "operator_ref": "A2BV", "vehicle_ref": "GE30_POE", "journey_ref": "0830", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T08:37:12+00:00", "response_timestamp": "2024-05-01T12:01:40+00:00", "latitude": 53.37711, "longitude": -3.12228, "line_name": "129", "operator_ref": "A2BV", "vehicle_ref": "GE30_POE", "journey_ref": "0830", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
            {"recorded_at_time": "2024-05-01T08:50:54+00:00", "response_timestamp": "2024-05-01T12:01:40+00:00", "latitude": 53.37608, "longitude": -3.12676, "line_name": "129", "operator_ref": "A2BV", "vehicle_ref": "GE30_POE", "journey_ref": "0830", "direction_ref": "outbound", "date_of_journey": "2024-05-01", "batch_id": "4256"},
        ]
    
    # last position dict is empty, both bus positions are within 70m
    def test_empty_last_position_dict(self):
        timetable_output, last_position_index = positionsTimetableLookup(
            avl_dict = self.avl_test_1, timetable_output = self.timetable_test_output_1, batch_id=None, last_position_dict = self.empty_last_position_dict
        )
        assert len(timetable_output) == 2
        assert timetable_output[0][0] == -100
        assert timetable_output[0][1] == "12:21:20"
        assert timetable_output[0][2] == 518770951
        assert timetable_output[0][3] < 70
        assert timetable_output[0][4] == "A2BV112232024-05-01"
        assert timetable_output[0][5] == None
        assert timetable_output[0][6] == "2024-05-01T12:21:20"
        assert timetable_output[0][7] == "Early"
        assert last_position_index["A2BV112232024-05-01"]["last_position"] == 1
        assert timetable_output[1][0] == -64
        assert timetable_output[1][1] == "12:21:56"
        assert timetable_output[1][2] == 518770951
        assert timetable_output[1][3] < 70
        assert timetable_output[1][4] == "A2BV112232024-05-01"
        assert timetable_output[1][5] == None
        assert timetable_output[1][6] == "2024-05-01T12:21:56"
        assert timetable_output[1][7] == "Early"
        assert last_position_index["A2BV112232024-05-01"]["last_position"] == 1
        assert last_position_index["A2BV112232024-05-01"]["distance"] == 64.64693710746909
        assert last_position_index["A2BV112232024-05-01"]["recorded_at_time"] == "2024-05-01T12:21:56"
        assert last_position_index["A2BV112232024-05-01"]["otp_state"] == "Early"

    # last position dict is not empty, there're bus positions within 70m and out of 70m range, the output result should not have any duplicates
    def test_non_empty_last_position_dict(self):
        timetable_output, last_position_index = positionsTimetableLookup(
            avl_dict = self.avl_test_2, timetable_output = self.timetable_test_output_2, batch_id=None, last_position_dict = self.last_position_dict_1
        )
        print(f"test 2: {timetable_output}")
        assert len(timetable_output) == 4
        assert timetable_output[3][0] == 34
        assert timetable_output[3][1] == "12:37:10"
        assert timetable_output[3][2] == 518770952
        assert timetable_output[3][3] < 70
        assert timetable_output[3][4] == "A2BV112232024-05-01"
        assert timetable_output[3][5] == None
        assert timetable_output[3][6] == "2024-05-01T12:37:10"
        assert timetable_output[3][7] == "OnTime"
        assert last_position_index["A2BV112232024-05-01"]["last_position"] == 2
        assert last_position_index["A2BV112232024-05-01"]["distance"] == 5.221130257809479
        assert last_position_index["A2BV112232024-05-01"]["recorded_at_time"] == "2024-05-01T12:37:10"
        assert last_position_index["A2BV112232024-05-01"]["otp_state"] == "OnTime"

    # position data with empty last position dict does not match with the timetable group id
    def test_empty_last_position_dict_no_matching_group_id(self):
        timetable_output, last_position_index = positionsTimetableLookup(
            avl_dict = self.avl_test_3, timetable_output = self.timetable_test_output_1, batch_id=None, last_position_dict = self.empty_last_position_dict
        )
        assert len(timetable_output) == 0
        assert len(last_position_index) == 0

    # position data with non-empty last position dict with one data which does not match with the timetable group id
    def test_non_empty_last_position_dict_no_matching_group_id(self):
        timetable_output, last_position_index = positionsTimetableLookup(
            avl_dict = self.avl_test_4, timetable_output = self.timetable_test_output_1, batch_id=None, last_position_dict = self.last_position_dict_1
        )
        assert len(timetable_output) == 1
        assert last_position_index["A2BV112232024-05-01"]["last_position"] == 1

    # the last position dict only contains last position index (old ver.)
    def test_last_position_dict_w_index_only(self):
        timetable_output, last_position_index = positionsTimetableLookup(
            avl_dict = self.avl_test_5, timetable_output = self.timetable_test_output_1, batch_id=None, last_position_dict = self.last_position_dict_2
        )
        assert len(timetable_output) == 2
        assert timetable_output[1][0] == 322
        assert timetable_output[1][1] == "13:06:10"
        assert timetable_output[1][2] == 518770957
        assert timetable_output[1][3] < 70
        assert timetable_output[1][4] == "A2BV112232024-05-01"
        assert timetable_output[1][5] == None
        assert timetable_output[1][6] == "2024-05-01T13:06:10"
        assert timetable_output[1][7] == "OnTime"
        assert last_position_index["A2BV112232024-05-01"]["last_position"] == 7

    def test_circular_route(self):
        timetable_output, last_position_index = positionsTimetableLookup(
            avl_dict = self.avl_test_6, timetable_output = self.timetable_test_output_1, batch_id=None, last_position_dict = self.empty_last_position_dict
        )
        assert len(timetable_output) == 12

    # test final stop otp treatment
    def test_final_stop_otp_treatment(self):
        timetable_output, last_position_index = positionsTimetableLookup(
            avl_dict = self.avl_test_7, timetable_output = self.timetable_test_output_1, batch_id=None, last_position_dict = self.empty_last_position_dict
        )
        assert len(timetable_output) == 6
        assert timetable_output[0][0] == 84
        assert timetable_output[0][1] == "10:01:24"
        assert timetable_output[0][2] == 518770958
        assert timetable_output[0][3] < 70
        assert timetable_output[0][4] == "A2BV10010002024-05-01"
        assert timetable_output[0][5] == None
        assert timetable_output[0][6] == "2024-05-01T10:01:24"
        assert timetable_output[0][7] == "OnTime"
        assert timetable_output[3][0] == 7
        assert timetable_output[3][1] == "08:30:07"
        assert timetable_output[3][2] == 518770961
        assert timetable_output[3][3] < 70
        assert timetable_output[3][4] == "A2BV12908302024-05-01"
        assert timetable_output[3][5] == None
        assert timetable_output[3][6] == "2024-05-01T08:30:07"
        assert timetable_output[3][7] == "OnTime"
        assert last_position_index["A2BV10010002024-05-01"]["last_position"] == 3
        assert last_position_index["A2BV10010002024-05-01"]["distance"] == 40.01278299815018
        assert last_position_index["A2BV10010002024-05-01"]["recorded_at_time"] == "2024-05-01T10:14:00"
        assert last_position_index["A2BV10010002024-05-01"]["otp_state"] == "OnTime"
        assert last_position_index["A2BV12908302024-05-01"]["last_position"] == 3
        assert last_position_index["A2BV12908302024-05-01"]["distance"] == 13.974540517704886
        assert last_position_index["A2BV12908302024-05-01"]["recorded_at_time"] == "2024-05-01T08:50:54"
        assert last_position_index["A2BV12908302024-05-01"]["otp_state"] == "Late"


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
