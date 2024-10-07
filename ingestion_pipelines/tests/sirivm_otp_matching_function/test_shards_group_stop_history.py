import logging
import datetime

from ingestion_pipelines.sirivm_otp_matching_function.sirivm_otp_matching_function.matcher.matching import get_shard_filter, get_group_stop_history
from .data.get_test_data import get_shards

class TestShards:

    logger = logging.getLogger('sirivm')
    logger.propagate=True

    shards = get_shards("shards.json")

    def test_get_shard_filter(self) -> None:
        """Test getting the shard filter
        """
        shard_filter = get_shard_filter(self.shards, "1")

        expected_filter = [
            "TFLO"
        ]
        assert shard_filter == expected_filter

    def test_get_shard_0_filter(self) -> None:
        """Test getting all the shards as shard 0 filter
        """
        shard_filter = get_shard_filter(self.shards, "0")

        expected_filter = [
            "TFLO",
            "NATX",
            "SCSO",
            "BNGN",
            "SDVN",
            "SSWL",
            "SCCU",
            "SCOX",
            "EYMS",
            "FBRA",
            "FHAM",
            "PLYC",
            "FLEI",
            "FYOR",
            "SVCT",
            "TDTR",
            "LNUD",
            "TPEN",
            "BNSM",
            "SCEM",
            "SCNH",
            "WRAY",
            "FESX",
            "ANEA",
            "FCYM",
            "BLUS",
            "AKSS",
            "BLAC",
            "CSLB",
            "FPOT",
            "ADER",
            "KBUS",
            "HRGT",
            "CRDR",
            "TNXB",
            "SCNE",
            "SCEK",
            "FSYO",
            "TBTN",
            "ARHE",
            "ACYM",
            "OXBC",
            "ANUM",
            "TFCN",
            "DAGC",
            "NCTR",
            "FCWL",
            "WBTR",
            "BPTR",
            "AMTM",
            "SCMN",
            "GNEL",
            "SCMY",
            "SCCM",
            "BHBC",
            "WDBC",
            "ARBB",
            "AMID",
            "BNDB",
            "AMNO",
            "TCVW",
            "NT",
            "PBLT",
            "THTR",
            "VECT",
            "SWWD",
            "AMSY",
            "FBRI",
            "SYRK",
            "FLDS",
            "SCGL",
            "FECS",
            "DIAM",
            "METR",
            "BRTB",
            "RBUS",
            "ANWE",
            "FHAL",
            "FHUD",
            "KDTR",
            "IPSW",
            "FTVA",
        ]
        assert shard_filter == expected_filter

    def test_get_shard_filter_not_str(self, caplog) -> None:
        """Test getting all the shards as shard 0 filter
        """
        with caplog.at_level(logging.ERROR):
            shard_filter = get_shard_filter(self.shards, 0)
        assert "shard_no 0 data type <class 'int'> is not a str" in caplog.text

class TestGroupStopHistory:
    def test_group_stop_history_empty_stop_history(self) -> None:
        """Test getting group stop history with an empty stop history
        """
        stop_history = {}
        group_id = "ABC12342024-09-01"
        group_stop_history = get_group_stop_history(group_id, stop_history)
        
        expected_group_stop_history = {
            "last_avl_time": "",
            "last_avl_index": 0,
            "matched_stops": {},
            "potential_matches": {},
        }

        assert group_stop_history == expected_group_stop_history

    def test_group_stop_history(self) -> None:
        """Test getting group stop history with a stop history with content
        """
        stop_history = {
            "ABC12342024-09-01" : {
                "last_avl_time": datetime.datetime(2024, 9, 1, 11, 34, 37),
                "last_avl_index": 6,
                "matched_stops": {
                    "1": {
                        "last_match_time": datetime.datetime(2024, 9, 1, 11, 32, 5)
                    }
                },
                "potential_matches": {
                    "2": {
                        "last_avl_index": 6, 
                        "last_distance": 58.596598093401845, 
                        "last_time_in_zone": datetime.datetime(2024, 9, 1, 11, 34, 37)
                    }
                },
            }
        }
        group_id = "ABC12342024-09-01"
        group_stop_history = get_group_stop_history(group_id, stop_history)
        
        expected_group_stop_history = {
            "last_avl_time": datetime.datetime(2024, 9, 1, 11, 34, 37),
            "last_avl_index": 6,
            "matched_stops": {
                "1": {
                    "last_match_time": datetime.datetime(2024, 9, 1, 11, 32, 5)
                }
            },
            "potential_matches": {
                "2": {
                    "last_avl_index": 6, 
                    "last_distance": 58.596598093401845, 
                    "last_time_in_zone": datetime.datetime(2024, 9, 1, 11, 34, 37)
                }
            },
        }
        
        assert group_stop_history == expected_group_stop_history