from datetime import datetime

from lxml import etree

NS = {"siri": "http://www.siri.org.uk/siri"}


def parse_xml(source, batch_id, source_type="string"):  # noqa: ANN001, ANN201 - BODS-7131
    """
    Parse XML data from a given source, which can be either a file path or a direct XML string.

    :param source: The XML source, either a file path or an XML string.
    :param source_type: The type of the source, 'file' for file paths or 'string' for XML strings.
    :return: A list of data extracted from the XML.
    """
    NS = {  # noqa: N806 - BODS-7131
        "siri": "http://www.siri.org.uk/siri",
    }  # Namespace declaration

    # Parse the XML based on the source type
    if source_type == "file":
        # For file source, open the file and parse it
        with open(source, "rb") as f:
            tree = etree.parse(f)  # noqa: S320 - BODS-7131
    elif source_type == "string":
        # For string source, parse directly from the string
        tree = etree.fromstring(source)  # noqa: S320 - BODS-7131
    else:
        raise ValueError("Unsupported source_type. Use 'file' or 'string'.")

    root = tree

    # Extract the ResponseTimestamp from the ServiceDelivery element
    # Ensure to navigate correctly considering the namespace
    service_delivery_timestamp = root.find(
        ".//siri:ServiceDelivery/siri:ResponseTimestamp",
        NS,
    ).text

    # Convert service_delivery_timestamp to the desired format if necessary
    # For example, if you need it as a datetime object or a specific string format,
    # you can convert it here using datetime.strptime() and then format it as needed.

    data = []
    for vehicle_activity in root.findall(".//siri:VehicleActivity", NS):
        # Now pass the extracted service_delivery_timestamp to extract_data
        extracted_data = extract_data(
            vehicle_activity,
            service_delivery_timestamp,
            batch_id,
        )
        print(f'extracted_data----{extracted_data}')
        if extracted_data:  # Ensure extracted_data is not None
            data.append(extracted_data)
    return data


def parse_direction(vehicle_activity):  # noqa: ANN001, ANN201
    direction_ref_elem = vehicle_activity.find(".//siri:DirectionRef", NS)
    if not direction_ref_elem:
        return None
    return direction_ref_elem.text


def normalize_direction(direction_ref):  # noqa: ANN001, ANN201
    """Map direction ref to normalized values. Either inbound or outbound"""
    if not direction_ref:
        return None

    direction_map = {
        "1": "outbound",
        "2": "inbound",
        "clockwise": "outbound",
        "anticlockwise": "inbound",
        "inbound": "inbound",
        "outbound": "outbound",
        "eastbound": "outbound",
        "westbound": "inbound",
    }
    direction_clean = direction_ref.strip().lower()
    return direction_map.get(direction_clean, direction_ref)


def extract_data(vehicle_activity, service_delivery_timestamp, batch_id):  # noqa: ANN001, ANN201 - BODS-7131
    NS = {"siri": "http://www.siri.org.uk/siri"}  # noqa: N806 - BODS-7131
    recorded_at_time = vehicle_activity.find(".//siri:RecordedAtTime", NS).text
    date_of_journey = datetime.strptime(recorded_at_time, "%Y-%m-%dT%H:%M:%S%z").date()
    latitude = vehicle_activity.find(".//siri:VehicleLocation/siri:Latitude", NS).text
    longitude = vehicle_activity.find(".//siri:VehicleLocation/siri:Longitude", NS).text
    line_name_elem = vehicle_activity.find(".//siri:PublishedLineName", NS)
    line_name = line_name_elem.text if line_name_elem is not None else None
    operator_ref = vehicle_activity.find(".//siri:OperatorRef", NS).text
    vehicle_ref = vehicle_activity.find(".//siri:VehicleRef", NS).text
    direction_ref = parse_direction(vehicle_activity)
    print(f"direction_ref-------{direction_ref}")
    direction_ref_normalized = normalize_direction(direction_ref)
    print(f"direction_ref_normalized-------{direction_ref_normalized}")

    journey_ref_1_elem = vehicle_activity.find(
        ".//siri:FramedVehicleJourneyRef/siri:DatedVehicleJourneyRef",
        NS,
    )
    journey_ref_2_elem = vehicle_activity.find(".//siri:VehicleJourneyRef", NS)
    journey_ref_1 = journey_ref_1_elem.text if journey_ref_1_elem is not None else None
    journey_ref_2 = journey_ref_2_elem.text if journey_ref_2_elem is not None else None
    journey_ref = journey_ref_1 or journey_ref_2

    origin_ref_elem = vehicle_activity.find(".//siri:OriginRef", NS)
    origin_ref = origin_ref_elem.text if origin_ref_elem is not None else None

    destination_ref_elem = vehicle_activity.find(".//siri:DestinationRef", NS)
    destination_ref = (
        destination_ref_elem.text if destination_ref_elem is not None else None
    )

    departure_time_elem = vehicle_activity.find(".//siri:OriginAimedDepartureTime", NS)
    departure_time = (
        departure_time_elem.text if departure_time_elem is not None else None
    )

    line_name_elem = vehicle_activity.find(".//siri:PublishedLineName", NS)
    line_name = line_name_elem.text if line_name_elem is not None else None

    if not journey_ref:
        journey_ref = f"{operator_ref}_{line_name}_{vehicle_ref}_{direction_ref}_{date_of_journey}"

    # Assuming service_delivery_timestamp is passed correctly formatted
    response_timestamp = service_delivery_timestamp

    return (
        recorded_at_time,
        response_timestamp,
        latitude,
        longitude,
        line_name,
        operator_ref,
        vehicle_ref,
        journey_ref,
        direction_ref_normalized,
        date_of_journey,
        batch_id,
        origin_ref,
        destination_ref,
        departure_time,
    )
