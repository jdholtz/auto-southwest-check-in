from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

from .checkin_scheduler import VIEW_RESERVATION_URL
from .flight import Flight
from .log import get_logger
from .utils import make_request

if TYPE_CHECKING:  # pragma: no cover
    from .flight_retriever import FlightRetriever

# Type alias for JSON
JSON = Dict[str, Any]

BOOKING_URL = "mobile-air-booking/"
BASE_URL = "https://mobile.southwest.com/api/" + BOOKING_URL
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
        flights = self._get_matching_flights(flight)
        logger.debug("Found %d matching flights", len(flights))
        for new_flight in flights:
            if new_flight["departureTime"] == flight.local_departure_time:
                return new_flight["startingFromPriceDifference"]

    def _get_matching_flights(self, flight: Flight) -> List[JSON]:
        """
        Get all of the flights that match the current flight's departure airport,
        arrival airport, and departure date.
        """
        change_flight_page = self._get_change_flight_page(flight)
        query = self._get_search_query(change_flight_page, flight)

        info = change_flight_page["_links"]["changeShopping"]
        site = BOOKING_URL + info["href"]

        # Southwest will not display the other page if its prices aren't requested. Therefore
        # we need to know what page to get based on what flight we requested (in case two flights
        # (round-trip flights) are on the same reservation)
        bound_page = "outboundPage" if query["outbound"]["isChangeBound"] else "inboundPage"

        logger.debug("Retrieving matching flights")
        response = make_request("POST", site, self.headers, query)
        return response["changeShoppingPage"]["flights"][bound_page]["cards"]

    def _get_change_flight_page(self, flight: Flight) -> JSON:
        # First, get the reservation information
        logger.debug("Fetching reservation information")
        info = {
            "first-name": self.flight_retriever.first_name,
            "last-name": self.flight_retriever.last_name,
        }
        site = VIEW_RESERVATION_URL + flight.confirmation_number
        response = make_request("GET", site, self.headers, info)

        # Next, get the search information needed to change the flight
        logger.debug("Retrieving search information for the current flight")
        info = response["viewReservationViewPage"]["_links"]["change"]
        site = BOOKING_URL + info["href"]
        response = make_request("GET", site, self.headers, info["query"])

        return response["changeFlightPage"]

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
