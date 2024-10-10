from datetime import datetime

from lxml import etree

NS = {"siri": "http://www.siri.org.uk/siri"}


def parse_xml(source, batch_id, source_type="string"):
    """
    Parses XML data from a given source, which can be either a file path or a direct XML string.

    :param source: The XML source, either a file path or an XML string.
    :param source_type: The type of the source, 'file' for file paths or 'string' for XML strings.
    :return: A list of data extracted from the XML.
    """
    NS = {"siri": "http://www.siri.org.uk/siri"}  # Namespace declaration

    # Parse the XML based on the source type
    if source_type == "file":
        # For file source, open the file and parse it
        with open(source, "rb") as f:
            tree = etree.parse(f)
    elif source_type == "string":
        # For string source, parse directly from the string
        tree = etree.fromstring(source)
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
        if extracted_data:  # Ensure extracted_data is not None
            data.append(extracted_data)
    return data


def extract_data(vehicle_activity, service_delivery_timestamp, batch_id):
    NS = {"siri": "http://www.siri.org.uk/siri"}
    recorded_at_time = vehicle_activity.find(".//siri:RecordedAtTime", NS).text
    date_of_journey = datetime.strptime(recorded_at_time, "%Y-%m-%dT%H:%M:%S%z").date()
    latitude = vehicle_activity.find(".//siri:VehicleLocation/siri:Latitude", NS).text
    longitude = vehicle_activity.find(".//siri:VehicleLocation/siri:Longitude", NS).text
    line_name_elem = vehicle_activity.find(".//siri:PublishedLineName", NS)
    line_name = line_name_elem.text if line_name_elem is not None else None
    operator_ref = vehicle_activity.find(".//siri:OperatorRef", NS).text
    vehicle_ref = vehicle_activity.find(".//siri:VehicleRef", NS).text
    direction_ref_elem = vehicle_activity.find(".//siri:DirectionRef", NS)
    direction_ref = direction_ref_elem.text if direction_ref_elem is not None else None

    journey_ref_1_elem = vehicle_activity.find(
        ".//siri:FramedVehicleJourneyRef/siri:DatedVehicleJourneyRef",
        NS,
    )
    journey_ref_2_elem = vehicle_activity.find(".//siri:VehicleJourneyRef", NS)
    journey_ref_1 = journey_ref_1_elem.text if journey_ref_1_elem is not None else None
    journey_ref_2 = journey_ref_2_elem.text if journey_ref_2_elem is not None else None
    journey_ref = journey_ref_1 or journey_ref_2

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
        direction_ref,
        date_of_journey,
        batch_id,
    )
