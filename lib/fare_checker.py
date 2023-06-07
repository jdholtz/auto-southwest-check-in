from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from .checkin_scheduler import VIEW_RESERVATION_URL
from .flight import Flight
from .log import get_logger
from .utils import FlightChangeError, make_request

if TYPE_CHECKING:  # pragma: no cover
    from .flight_retriever import FlightRetriever

# Type alias for JSON
JSON = Dict[str, Any]

BOOKING_URL = "mobile-air-booking/"
logger = get_logger(__name__)


class FareChecker:
    def __init__(self, flight_retriever: FlightRetriever) -> None:
        self.flight_retriever = flight_retriever
        self.headers = flight_retriever.checkin_scheduler.headers

    def check_flight_price(self, flight: Flight) -> None:
        """
        Check if the price amount is negative (in either points or USD).
        If it is, send a notification to the user about the lower fare.
        """
        logger.debug("Checking current price for flight")
        flight_price = self._get_flight_price(flight)

        # The sign key will not exist if the price amount is 0
        sign = flight_price.get("sign", "")
        price_info = f"{sign}{flight_price['amount']} {flight_price['currencyCode']}"
        logger.debug("Flight price change found for %s", price_info)

        if sign == "-":
            # Lower fare!
            self.flight_retriever.notification_handler.lower_fare(flight, price_info)

    def _get_flight_price(self, flight: Flight) -> JSON:
        """Get the price difference of the flight"""
        flights, fare_type = self._get_matching_flights(flight)
        logger.debug("Found %d matching flights", len(flights))

        # Get the fares from the same flight
        for new_flight in flights:
            if (
                new_flight["departureTime"] == flight.local_departure_time
                and new_flight["arrivalTime"] == flight.local_arrival_time
            ):
                return self._get_matching_fare(new_flight["fares"], fare_type)

    def _get_matching_flights(self, flight: Flight) -> Tuple[List[JSON], str]:
        """
        Get all of the flights that match the current flight's departure airport,
        arrival airport, and departure date.

        Additionally, retrieve the flight's fare type so we can check the correct
        fare for a price drop.
        """
        change_flight_page, fare_type_bounds = self._get_change_flight_page(flight)
        query = self._get_search_query(change_flight_page, flight)

        info = change_flight_page["_links"]["changeShopping"]
        site = BOOKING_URL + info["href"]

        # Southwest will not display the other page if its prices aren't requested. Therefore
        # we need to know what page to get based on what flight we requested (in case two flights
        # (round-trip flights) are on the same reservation)
        bound_page = "outboundPage" if query["outbound"]["isChangeBound"] else "inboundPage"

        bound = 0 if bound_page == "outboundPage" else 1
        fare_type = fare_type_bounds[bound]["fareProductDetails"]["fareProductId"]

        logger.debug("Retrieving matching flights")
        response = make_request("POST", site, self.headers, query, max_attempts=7)
        return response["changeShoppingPage"]["flights"][bound_page]["cards"], fare_type

    def _get_change_flight_page(self, flight: Flight) -> Tuple[JSON, JSON]:
        # First, get the reservation information
        logger.debug("Fetching reservation information")
        info = {
            "first-name": self.flight_retriever.first_name,
            "last-name": self.flight_retriever.last_name,
        }
        site = VIEW_RESERVATION_URL + flight.confirmation_number
        response = make_request("GET", site, self.headers, info, max_attempts=7)
        reservation_info = response["viewReservationViewPage"]
        fare_type_bounds = reservation_info["bounds"]

        # Ensure the flight does not have a companion pass connected to it
        # as companion passes are not supported.
        self._check_for_companion(reservation_info)

        # Next, get the search information needed to change the flight
        logger.debug("Retrieving search information for the current flight")
        info = reservation_info["_links"]["change"]

        # The change link does not exist, so skip fare checking for this flight
        if info is None:
            raise FlightChangeError("Flight cannot be changed online")

        site = BOOKING_URL + info["href"]
        response = make_request("GET", site, self.headers, info["query"], max_attempts=7)

        return response["changeFlightPage"], fare_type_bounds

    def _get_search_query(self, flight_page: JSON, flight: Flight) -> JSON:
        """
        Generate the search query needed to get matching flights. The search query
        is different if the reservation is one-way vs. round-trip
        """
        bound_references = flight_page["_links"]["changeShopping"]["body"]
        search_terms = []
        for idx, bound in enumerate(flight_page["boundSelections"]):
            search_terms.append(
                {
                    "boundReference": bound_references[idx]["boundReference"],
                    "date": bound["originalDate"],
                    "destination-airport": bound["toAirportCode"],
                    "origin-airport": bound["fromAirportCode"],
                    # This allows selecting the correct flight for a round-trip reservation.
                    "isChangeBound": bound["timeDeparts"] == flight.local_departure_time,
                }
            )

        # Only generate a query including both 'outbound' and 'inbound' if the reservation
        # is round-trip. Otherwise, just generate a query including 'outbound'
        bounds = ["outbound", "inbound"]
        return dict(zip(bounds, search_terms))

    def _check_for_companion(self, reservation_info: JSON) -> None:
        grey_box_message = reservation_info["greyBoxMessage"]
        if (
            grey_box_message
            and "body" in grey_box_message
            and "companion" in grey_box_message["body"]
        ):
            raise FlightChangeError("Fare check is not supported with companion passes")

    def _get_matching_fare(self, fares: JSON, fare_type: str) -> JSON:
        if fares is None:
            return self._unavailable_fare(fare_type)

        for fare in fares:
            if fare["_meta"]["fareProductId"] == fare_type:
                if "priceDifference" in fare:
                    return fare["priceDifference"]

                return self._unavailable_fare(fare_type)

        raise KeyError(f"No fare type found matching {fare_type}")

    def _unavailable_fare(self, fare_type: str) -> JSON:
        """
        No fares are available (most likely due to tickets of that fare type
        not being sold anymore). Therefore, report back a 0 USD difference.
        """
        logger.debug("Fare %s is not availiable. Setting price difference to 0 USD", fare_type)
        return {"amount": 0, "currencyCode": "USD"}
