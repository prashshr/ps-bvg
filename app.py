from flask import Flask, render_template, jsonify, request
import requests
from datetime import datetime
import logging
from pytz import timezone as pytz_timezone
from dateutil import parser

app = Flask(__name__)

# Set up logging for debugging
logging.basicConfig(level=logging.DEBUG)

# BVG API Base URL
departures_url = "https://v6.vbb.transport.rest/stops/{}/departures"
station_search_url = "https://v6.vbb.transport.rest/stations?query={}"

# Define your local timezone (CEST)
local_tz = pytz_timezone('Europe/Berlin')

# Function to get next departures from a station
def get_next_departures(station_id):
    params = {
        "duration": 20  # Get departures in the next n minutes
    }

    try:
        response = requests.get(departures_url.format(station_id), params=params)
        logging.debug(f"Request to BVG API for station ID {station_id}: {response.url}")

        if response.status_code == 200:
            response_json = response.json()
            logging.debug(f"Response from BVG API for station ID {station_id}: {response_json}")
            return response_json.get('departures', [])
        else:
            logging.error(f"Error fetching departures: {response.status_code} - {response.text}")
            raise Exception(f"Error fetching departures: {response.status_code} - {response.text}")
    except Exception as e:
        logging.exception("Exception occurred while fetching departures.")
        raise

# Function to search stations based on query
@app.route('/stations', methods=['GET'])
def get_stations():
    query = request.args.get('query', '')
    response = requests.get(station_search_url.format(query))

    if response.status_code == 200:
        return response.json()  # Return JSON response to the client
    else:
        app.logger.error(f"Error fetching stations: {response.status_code} - {response.text}")
        return jsonify({}), response.status_code  # Return empty JSON on error


# Define a dictionary to map station IDs to station names
station_names = {
    "900007105": "Wolliner Str. (Berlin)",  # Corrected name
    "900007110": "U-Bernauer Str.",
    "900110006": "U-Eberswalder Str."
}

# Function to format the departure data
def format_departures(departures, is_ubahn_only=False, station_id=None):
    data = []
    for departure in departures:
        try:
            transport_type = departure['line']['product']
            # Check if the station is Bernauer Str. or Eberswalder Str. and filter accordingly
            if (station_id in ["900007110", "900110006"]) and transport_type != "subway":
                continue

            if is_ubahn_only and transport_type != "subway":
                continue

            line_name = departure['line']['name']
            direction = departure['direction']

            departure_time = departure.get('when')
            planned_time = departure.get('plannedWhen')

            # If departure_time is None, use planned_time
            if departure_time is None:
                logging.debug(f"Departure time is None, using plannedWhen: {planned_time} for tripId: {departure.get('tripId')}")
                departure_time = planned_time

            if departure_time is not None:
                # Parse plannedWhen which is in ISO format with timezone
                departure_dt = parser.isoparse(departure_time)

                # Set current time to Berlin timezone
                current_time = datetime.now(local_tz)

                # Calculate remaining time in minutes
                remaining_time_seconds = (departure_dt - current_time).total_seconds()
                remaining_time = int(max(remaining_time_seconds // 60, 0))

                # Only include departures after the next 2 minutes
                if remaining_time < 2:
                    continue

                logging.debug(f"Remaining time: {remaining_time} min")

                delay = departure.get('delay', 0)
                delay_str = f"{delay // 60} min" if delay else "On Time"

                transport_logo = {
                    "bus": "bus_logo.png",
                    "tram": "tram_logo.png",
                    "subway": "ubahn_logo.png"
                }.get(transport_type, "bvg_logo.svg")

                data.append({
                    "line": line_name,
                    "direction": direction,
                    "departure_stop": station_names.get(station_id, "Unknown Stop"),
                    "departure_time": departure_dt.strftime('%Y-%m-%d %H:%M'),
                    "in_next": remaining_time,
                    "delay": delay_str,
                    "planned_time": departure_dt.strftime('%Y-%m-%d %H:%M'),
                    "type": transport_type.capitalize(),
                    "logo": transport_logo
                })
            else:
                logging.debug(f"Debug: departure_time is None for tripId: {departure.get('tripId')}")

        except Exception as e:
            logging.exception("Exception occurred while formatting departures.")
            continue
    return data

@app.route('/')
def index():
    station_ids = ["900007105", "900007110", "900110006"]  # Add all relevant station IDs
    all_departures = []

    try:
        for station_id in station_ids:
            departures = get_next_departures(station_id)
            formatted_departures = format_departures(departures, station_id=station_id)
            all_departures.extend(formatted_departures)
    except Exception as e:
        all_departures = []  # Ensure departures are empty on error

    # Sort the departures by planned departure time
    all_departures.sort(key=lambda x: datetime.strptime(x['planned_time'], '%Y-%m-%d %H:%M'))

    # Group by transport type and limit to 6 entries
    grouped_departures = {}
    for departure in all_departures:
        transport_type = departure['type']
        if transport_type not in grouped_departures:
            grouped_departures[transport_type] = []
        if len(grouped_departures[transport_type]) < 6:  # Limit to 6 departures
            grouped_departures[transport_type].append(departure)

    return render_template('index.html', grouped_departures=grouped_departures)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
