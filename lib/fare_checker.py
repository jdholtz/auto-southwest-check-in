from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from .log import get_logger
from .utils import CheckFaresOption, FlightChangeError, make_request, time

if TYPE_CHECKING:
    from .flight import Flight
    from .reservation_monitor import ReservationMonitor

# Type alias for JSON
JSON = dict[str, Any]

BOOKING_URL = "mobile-air-booking/"
logger = get_logger(__name__)


class FareChecker:
    def __init__(self, reservation_monitor: ReservationMonitor) -> None:
        self.reservation_monitor = reservation_monitor
        self.headers = reservation_monitor.checkin_scheduler.headers
        self.filter = get_fare_check_filter(self.reservation_monitor.config.check_fares)
        self._cancel_refund_cache = {}

    def check_flight_price(self, flight: Flight) -> None:
        """
        Check if the price amount is negative (in either points or USD).
        If it is, send a notification to the user about the lower fare.
        """
        logger.debug("Checking current price for flight")
        flight_price = self._get_flight_price(flight)

        price_info = f"{flight_price['amount']:+,} {flight_price['currencyCode']}"
        logger.debug("Flight price change found for %s", price_info)

        # The Southwest website can report a fare price difference of -1 USD. This is a
        # false positive as no credit is actually received when the flight is changed.
        # Refer to this discussion for more information:
        # https://github.com/jdholtz/auto-southwest-check-in/discussions/102
        if flight_price["amount"] < -1:
            # Lower fare!
            self.reservation_monitor.notification_handler.lower_fare(flight, price_info)

    def _get_flight_price(self, flight: Flight) -> JSON:
        """Get the price difference of the flight"""
        flights, fare_type = self._get_matching_flights(flight)
        logger.debug("Found %d matching flights", len(flights))

        original_fare = None
        if fare_type.startswith("WGA"):
            original_fare = self._get_original_wga_fare(flight, flights)

        lowest_fare = self._get_lowest_fare(flight, flights, fare_type, original_fare)
        return lowest_fare

    def _get_matching_flights(self, flight: Flight) -> tuple[list[JSON], str]:
        """
        Get all of the flights that match the current flight's departure airport,
        arrival airport, and departure date.

        Additionally, retrieve the flight's fare type so we can check the correct
        fare for a price drop.
        """
        change_flight_page, fare_type_bounds = self._get_change_flight_page(flight.reservation_info)
        query = self._get_search_query(change_flight_page, flight)

        info = change_flight_page["_links"]["changeShopping"]
        site = BOOKING_URL + info["href"]

        # Southwest will not display the other page if its prices aren't requested. Therefore
        # we need to know what page to get based on what flight we requested (in case two flights
        # (round-trip flights) are on the same reservation)
        if query.get("outbound", {}).get("isChangeBound"):
            bound_page = "outboundPage"
        elif query.get("inbound", {}).get("isChangeBound"):
            bound_page = "inboundPage"
        else:
            # This exception usually happens when Southwest changes the formatting of their flight
            # numbers
            raise ValueError("Flight number did not match any flight bound on the reservation")

        bound = 0 if bound_page == "outboundPage" else 1
        fare_type = fare_type_bounds[bound]["fareProductDetails"]["fareProductId"]

        logger.debug("Retrieving matching flights")
        time.sleep(2)

        response = make_request("POST", site, self.headers, query, max_attempts=7)
        return response["changeShoppingPage"]["flights"][bound_page]["cards"], fare_type

    def _get_change_flight_page(self, reservation_info: JSON) -> tuple[JSON, list[JSON]]:
        fare_type_bounds = reservation_info["bounds"]

        # Ensure the flight does not have a companion pass connected to it
        # as companion passes are not supported.
        self._check_for_companion(reservation_info)

        # Next, get the search information needed to change the flight
        logger.debug("Retrieving search information for the current flight")
        change_link = reservation_info["_links"]["change"]
        reaccom_link = reservation_info["_links"]["reaccom"]

        if reaccom_link is not None:
            # The flight is reaccommodated, so no fare checking is needed
            raise FlightChangeError("Flight can be changed for free (reaccommodated)")

        # The change link does not exist, so skip fare checking for this flight
        if change_link is None:
            raise FlightChangeError("Flight cannot be changed online")

        site = BOOKING_URL + change_link["href"]
        time.sleep(2)

        response = make_request("GET", site, self.headers, change_link["query"], max_attempts=7)
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
                    "isChangeBound": bound["flight"] == flight.flight_number,
                }
            )

        # Only generate a query including both 'outbound' and 'inbound' if the reservation
        # is round-trip. Otherwise, just generate a query including 'outbound'
        bounds = ["outbound", "inbound"]
        return dict(zip(bounds, search_terms))

    def _check_for_companion(self, reservation_info: JSON) -> None:
        grey_box_message = reservation_info["greyBoxMessage"]
        if grey_box_message and "companion" in (grey_box_message.get("body") or ""):
            raise FlightChangeError("Fare check is not supported with companion passes")

    def _get_lowest_fare(
        self,
        flight: Flight,
        flights: list[JSON],
        fare_type: str,
        original_fare: JSON | None = None,
    ) -> JSON:
        """
        Get the lowest fare for the queried flights based on the filter being used. If no fare is
        available for the specific fare type, a 0 USD difference will be returned.
        """
        lowest_fare = None

        for new_flight in flights:
            # Only compare flight fares that match the current filter
            if self.filter(flight, new_flight):
                fare = self._get_matching_fare(new_flight["fares"], fare_type, original_fare)
                # Check if this fare is the lowest encountered so far
                if not lowest_fare or (fare and fare["amount"] < lowest_fare["amount"]):
                    lowest_fare = fare

        if not lowest_fare:
            # No fares are available (most likely due to tickets of that fare type
            # not being sold anymore). Therefore, report back a 0 USD difference.
            logger.debug("Fare %s is not available. Setting price difference to 0 USD", fare_type)
            lowest_fare = {"amount": 0, "currencyCode": "USD"}

        return lowest_fare

    def _get_matching_fare(
        self, fares: list[JSON], fare_type: str, original_fare: JSON | None = None
    ) -> JSON | None:
        """
        Get the fare that matches the fare type. If a fare exists, the amount will be returned, as
        an integer, and the currency code (USD or points). If no fare exists, nothing will be
        returned.
        """
        if fares is None:
            fares = []

        for fare in fares:
            if fare["_meta"]["fareProductId"] == fare_type:
                if "priceDifference" in fare:
                    return self._parse_amount(fare["priceDifference"])

                break

        if fare_type.startswith("WGA"):
            return self._get_basic_fare_difference(fares, original_fare)

        return None

    def _get_basic_fare_difference(
        self, fares: list[JSON], original_fare: JSON | None = None
    ) -> JSON | None:
        """
        Basic fares can be unavailable on the change page even when the flight can still be
        cancelled and rebooked more cheaply. If the originally paid fare is available from the
        cancel flow, derive the current Basic fare using the available upgrade fares:

            current basic fare = current upgrade fare - displayed price difference

        Otherwise, derive the originally paid fare from an available upgrade fare using:

            paid fare = current fare price - displayed price difference

        Then compare the cheapest current Basic fare against the originally paid fare.
        """
        if original_fare is None:
            original_fare = self._derive_original_basic_fare(fares)

        if original_fare is None:
            return None

        lowest_current_basic_fare = self._get_lowest_current_basic_fare(
            fares, original_fare["currencyCode"]
        )
        if lowest_current_basic_fare is None:
            return None

        return {
            "amount": lowest_current_basic_fare["amount"] - original_fare["amount"],
            "currencyCode": lowest_current_basic_fare["currencyCode"],
        }

    def _derive_original_basic_fare(self, fares: list[JSON]) -> JSON | None:
        original_basic_fare = None
        for fare in fares:
            current_price = self._get_fare_price(fare)
            price_difference = fare.get("priceDifference")

            if current_price is None or price_difference is None:
                continue

            parsed_current_price = self._parse_amount(current_price)
            parsed_difference = self._parse_amount(price_difference)
            if parsed_current_price["currencyCode"] != parsed_difference["currencyCode"]:
                continue

            calculated_original_price = {
                "amount": parsed_current_price["amount"] - parsed_difference["amount"],
                "currencyCode": parsed_current_price["currencyCode"],
            }

            if original_basic_fare is None:
                original_basic_fare = calculated_original_price

        return original_basic_fare

    def _get_lowest_available_fare(
        self, fares: list[JSON], currency_code: str | None = None
    ) -> JSON | None:
        lowest_available_fare = None
        for fare in fares:
            current_price = self._get_fare_price(fare)
            if current_price is None:
                continue

            parsed_current_price = self._parse_amount(current_price)
            if currency_code and parsed_current_price["currencyCode"] != currency_code:
                continue

            if (
                lowest_available_fare is None
                or parsed_current_price["amount"] < lowest_available_fare["amount"]
            ):
                lowest_available_fare = parsed_current_price

        return lowest_available_fare

    def _get_lowest_current_basic_fare(
        self, fares: list[JSON], currency_code: str | None = None
    ) -> JSON | None:
        lowest_current_basic_fare = None

        for fare in fares:
            current_price = self._get_fare_price(fare)
            price_difference = fare.get("priceDifference")

            if current_price is None or price_difference is None:
                continue

            parsed_current_price = self._parse_amount(current_price)
            parsed_difference = self._parse_amount(price_difference)

            if parsed_current_price["currencyCode"] != parsed_difference["currencyCode"]:
                continue

            if currency_code and parsed_current_price["currencyCode"] != currency_code:
                continue

            current_basic_fare = {
                "amount": parsed_current_price["amount"] - parsed_difference["amount"],
                "currencyCode": parsed_current_price["currencyCode"],
            }

            if (
                lowest_current_basic_fare is None
                or current_basic_fare["amount"] < lowest_current_basic_fare["amount"]
            ):
                lowest_current_basic_fare = current_basic_fare

        return lowest_current_basic_fare

    def _get_original_wga_fare(self, flight: Flight, flights: list[JSON]) -> JSON | None:
        currency_code = self._get_wga_currency(flight, flights)
        if currency_code is None:
            return None

        cache_key = (flight.confirmation_number, flight.flight_number, currency_code)
        if cache_key in self._cancel_refund_cache:
            return self._cancel_refund_cache[cache_key]

        try:
            original_fare = self._get_cancel_refund_total(flight, currency_code)
        except (FlightChangeError, KeyError, ValueError) as err:
            logger.debug(
                "Could not retrieve WGA refund quote for %s: %s", flight.flight_number, err
            )
            original_fare = None

        self._cancel_refund_cache[cache_key] = original_fare
        return original_fare

    def _get_wga_currency(self, flight: Flight, flights: list[JSON]) -> str | None:
        for new_flight in flights:
            if self.filter(flight, new_flight):
                lowest_fare = self._get_lowest_available_fare(new_flight.get("fares") or [])
                if lowest_fare is not None:
                    return lowest_fare["currencyCode"]

        return None

    def _get_cancel_refund_total(self, flight: Flight, currency_code: str) -> JSON | None:
        refund_quote_page = self._get_cancel_refund_quote_page(flight.reservation_info)
        self._validate_cancel_refund_quote(refund_quote_page, flight)

        for trip_total in refund_quote_page.get("tripTotals") or []:
            if trip_total["currencyCode"] == currency_code:
                return self._parse_amount(trip_total)

        return None

    def _get_cancel_refund_quote_page(self, reservation_info: JSON) -> JSON:
        cancel_page = self._get_cancel_bound_page(reservation_info)
        refund_quote_link = cancel_page["_links"]["refundQuote"]
        site = BOOKING_URL + refund_quote_link["href"]

        logger.debug("Retrieving refund quote information for the current flight")
        time.sleep(2)

        response = make_request(
            refund_quote_link["method"],
            site,
            self.headers,
            refund_quote_link.get("body", {}),
            max_attempts=7,
        )
        return response["cancelRefundQuotePage"]

    def _get_cancel_bound_page(self, reservation_info: JSON) -> JSON:
        self._check_for_companion(reservation_info)

        cancel_link = reservation_info["_links"].get("cancelBound")
        if cancel_link is None:
            raise FlightChangeError("Flight cannot be cancelled online")

        site = BOOKING_URL + cancel_link["href"]
        time.sleep(2)

        response = make_request(
            cancel_link["method"],
            site,
            self.headers,
            cancel_link.get("query", {}),
            max_attempts=7,
        )
        return response["viewForCancelBoundPage"]

    def _validate_cancel_refund_quote(self, refund_quote_page: JSON, flight: Flight) -> None:
        cancel_bounds = refund_quote_page.get("cancelBounds") or []
        matching_bounds = [
            bound for bound in cancel_bounds if bound.get("flight") == flight.flight_number
        ]

        if len(matching_bounds) != 1 or len(cancel_bounds) != 1:
            raise FlightChangeError("Could not determine the refund quote for the exact flight")

    def _get_fare_price(self, fare: JSON) -> JSON | None:
        for price_key in ["discountedPrice", "price"]:
            price = fare.get(price_key)
            if price is not None:
                return price

        return None

    def _parse_amount(self, price_info: JSON) -> JSON:
        sign = price_info.get("sign", "")
        parsed_amount = int(sign + price_info["amount"].replace(",", ""))
        return {"amount": parsed_amount, "currencyCode": price_info["currencyCode"]}


def get_fare_check_filter(check_fares: CheckFaresOption) -> Callable[[Flight, JSON], bool]:
    if check_fares == CheckFaresOption.SAME_FLIGHT:
        return same_flight_filter
    if check_fares == CheckFaresOption.SAME_DAY_NONSTOP:
        return nonstop_flight_filter
    if check_fares == CheckFaresOption.SAME_DAY:
        return any_flight_filter

    raise ValueError(f"check_fares value ({check_fares}) did not match any valid option")


def same_flight_filter(flight: Flight, flight_json: JSON) -> bool:
    return flight_json["flightNumbers"] == flight.flight_number


def any_flight_filter(*_) -> bool:
    return True


def nonstop_flight_filter(_, flight_json: JSON) -> bool:
    return flight_json["stopDescription"] == "Nonstop"
