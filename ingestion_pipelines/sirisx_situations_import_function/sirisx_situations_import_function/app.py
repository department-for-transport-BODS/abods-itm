from datetime import UTC, datetime
from io import BytesIO

import requests
from aws_lambda_powertools import Logger
from lxml import etree
from psycopg2.extras import execute_batch

from .models import SituationRecord
from .shared.db import setup_db

SIRI_SX_CANCELLATIONS_URL = (
    "https://6tfu67dcng.execute-api.eu-west-2.amazonaws.com/v1/siri-sx"
)
NS_URI = "http://www.siri.org.uk/siri"

logger = Logger()
conn = setup_db()


def get_element_text(
    elem: etree._Element,
    path: str,
    default: str | None = None,
) -> str | None:
    return elem.findtext(path, default, namespaces={"siri": NS_URI})


def parse_datetime(datetime_str: str) -> datetime:
    """Parse ISO string to datetime object"""
    return datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))


def parse_situation_element(
    elem: etree._Element,
    response_timestamp: datetime,
    producer_ref: str,
) -> SituationRecord | None:
    try:
        situation_number = get_element_text(elem, ".//siri:SituationNumber")
        if not situation_number:
            logger.error(
                "Unable to parse PTSituation element: SituationNumber not found",
            )
            return None

        version = get_element_text(elem, ".//siri:Version")
        if version is None:
            logger.warning(
                "Missing Version for PTSituationElement. This may lead to duplicates",
                situation_number=situation_number,
                producer_ref=producer_ref,
            )

        operator_noc = get_element_text(elem, ".//siri:OperatorRef")
        line_name = get_element_text(elem, ".//siri:PublishedLineName")
        direction = get_element_text(elem, ".//siri:DirectionRef")
        journey_code = get_element_text(elem, ".//siri:DatedVehicleJourneyRef")
        condition = get_element_text(elem, ".//siri:Condition")
        progress = get_element_text(elem, ".//siri:Progress")

        origin_departure = get_element_text(elem, ".//siri:OriginAimedDepartureTime")
        date_of_journey = parse_datetime(origin_departure) if origin_departure else None

        start_time = get_element_text(elem, ".//siri:ValidityPeriod/siri:StartTime")
        end_time = get_element_text(elem, ".//siri:ValidityPeriod/siri:EndTime")
        start_datetime = parse_datetime(start_time) if start_time else None
        end_datetime = parse_datetime(end_time) if end_time else None

        return SituationRecord(
            producer_ref=producer_ref,
            situation_number=situation_number,
            version=version,
            operator_noc=operator_noc,
            line_name=line_name,
            direction=direction,
            date_of_journey=date_of_journey,
            start_date=start_datetime,
            end_date=end_datetime,
            journey_code=journey_code,
            condition=condition,
            progress=progress,
            event_timestamp=response_timestamp,
            creation_time=datetime.now(UTC),
        )

    except Exception:
        logger.exception("Failed to parse PtSituationElement")
        return None


def parse_xml(xml_bytes: bytes) -> list[SituationRecord]:
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        remove_blank_text=True,
        remove_comments=True,
    )
    root = etree.fromstring(xml_bytes, parser=parser)
    producer_ref = get_element_text(root, ".//siri:ProducerRef")
    if not producer_ref:
        logger.error("Unable to parse XML: No ProducerRef found")
        return []
    response_timestamp_str = get_element_text(root, ".//siri:ResponseTimestamp")
    if not response_timestamp_str:
        logger.warning("No ResponseTimestamp found, defaulting to datetime.now()")

    response_timestamp = (
        parse_datetime(response_timestamp_str)
        if response_timestamp_str
        else datetime.now(UTC)
    )

    tag = f"{{{NS_URI}}}PtSituationElement"
    context = etree.iterparse(
        BytesIO(xml_bytes),
        events=("end",),
        tag=tag,
        remove_blank_text=True,
        remove_comments=True,
    )

    rows: list[SituationRecord] = []
    for _, elem in context:
        try:
            row = parse_situation_element(elem, response_timestamp, producer_ref)
            if row:
                rows.append(row)
        except Exception:
            logger.exception("Error parsing XML")
        finally:
            elem.clear()
    return rows


def insert_rows(rows: list[SituationRecord]) -> None:
    with conn.cursor() as cur:
        logger.info("Inserting journey event rows", count=len(rows))
        insert_stmt = """
            INSERT INTO public.siri_sx_situations (
                producer_ref,
                situation_number,
                version,
                operator_noc,
                line_name,
                direction,
                date_of_journey,
                start_date,
                end_date,
                journey_code,
                condition,
                progress,
                event_timestamp,
                creation_time
            )
            VALUES (
                %(producer_ref)s,
                %(situation_number)s,
                %(version)s,
                %(operator_noc)s,
                %(line_name)s,
                %(direction)s,
                %(date_of_journey)s,
                %(start_date)s,
                %(end_date)s,
                %(journey_code)s,
                %(condition)s,
                %(progress)s,
                %(event_timestamp)s,
                %(creation_time)s
            )
            ON CONFLICT (producer_ref, situation_number, version) DO NOTHING;
        """
        execute_batch(cur, insert_stmt, [row.to_dict() for row in rows], page_size=1000)


def lambda_handler(_event: dict, _context: dict) -> None:
    logger.info("Retrieving XML from SIRI SX")
    response = requests.get(SIRI_SX_CANCELLATIONS_URL, timeout=30)
    response.raise_for_status()
    xml_bytes = response.content
    rows = parse_xml(xml_bytes)
    if not rows:
        logger.warning("No rows to insert.")
        return
    insert_rows(rows)
    logger.info(
        "All rows parsed and inserted",
    )
