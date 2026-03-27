"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/flights/status-badge";
import { CountdownTimer } from "@/components/flights/countdown-timer";
import { Badge } from "@/components/ui/badge";
import type { WorkerLog } from "@/lib/types";

interface FareInfo {
  price_change: number;
  currency_code: string;
  checked_at: string;
}

interface FlightWithFare {
  id: string;
  reservation_id: string;
  flight_number: string;
  departure_airport: string;
  destination_airport: string;
  departure_time: string;
  is_international: number;
  checkin_status: string;
  checkin_result: string | null;
  assigned_seat?: string;
  confirmation_number: string;
  first_name: string;
  last_name: string;
  latest_fare: FareInfo | null;
  baseline_fare: FareInfo | null;
}

function formatFare(fare: FareInfo | null): string {
  if (!fare) return "—";
  const sign = fare.price_change > 0 ? "+" : "";
  if (fare.currency_code === "PTS" || fare.currency_code === "Points") {
    return `${sign}${fare.price_change.toLocaleString()} pts`;
  }
  return `${sign}$${Math.abs(fare.price_change).toLocaleString()}`;
}

function fareColor(fare: FareInfo | null): string {
  if (!fare) return "text-gray-400";
  if (fare.price_change < -1) return "text-green-600 font-medium";
  if (fare.price_change > 1) return "text-red-600 font-medium";
  return "text-gray-500";
}

export default function FlightsPage() {
  const [flights, setFlights] = useState<FlightWithFare[]>([]);
  const [selectedFlight, setSelectedFlight] = useState<string | null>(null);
  const [logs, setLogs] = useState<WorkerLog[]>([]);
  const [fareHistory, setFareHistory] = useState<FareInfo[]>([]);

  useEffect(() => {
    fetchFlights();
    const interval = setInterval(fetchFlights, 30000);
    return () => clearInterval(interval);
  }, []);

  async function fetchFlights() {
    const res = await fetch("/api/flights");
    setFlights(await res.json());
  }

  async function expandFlight(flightId: string) {
    if (selectedFlight === flightId) {
      setSelectedFlight(null);
      return;
    }
    setSelectedFlight(flightId);
    const [logsRes, faresRes] = await Promise.all([
      fetch(`/api/flights/${flightId}/logs`),
      fetch(`/api/flights/${flightId}/fares`),
    ]);
    setLogs(await logsRes.json());
    setFareHistory(await faresRes.json());
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Flights</h1>
        <p className="text-sm text-gray-500">
          {flights.length} flight{flights.length !== 1 ? "s" : ""} tracked
        </p>
      </div>

      {flights.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <p className="text-gray-500">
              No flights tracked yet. Add a Southwest account or reservation to get started.
              Flights appear here once the worker retrieves them from Southwest.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {flights.map((flight) => (
            <Card key={flight.id} className="overflow-hidden">
              <div
                className="p-4 cursor-pointer hover:bg-gray-50 transition-colors"
                onClick={() => expandFlight(flight.id)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm font-medium">
                          {flight.confirmation_number}
                        </span>
                        {flight.flight_number && (
                          <span className="text-xs text-gray-400">
                            WN {flight.flight_number}
                          </span>
                        )}
                      </div>
                      <div className="text-sm text-gray-600 mt-0.5">
                        {flight.first_name} {flight.last_name}
                      </div>
                    </div>
                    <div className="text-sm">
                      <span className="font-medium">{flight.departure_airport}</span>
                      {" "}&rarr;{" "}
                      <span className="font-medium">{flight.destination_airport}</span>
                    </div>
                    <div className="text-sm text-gray-500">
                      <div>
                        {new Date(flight.departure_time).toLocaleDateString(undefined, {
                          weekday: "short",
                          month: "short",
                          day: "numeric",
                        })}
                      </div>
                      <div className="text-xs text-gray-400">
                        {new Date(flight.departure_time).toLocaleTimeString(undefined, {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    {/* Fare info */}
                    <div className="text-right">
                      <div className={`text-sm ${fareColor(flight.latest_fare)}`}>
                        {flight.latest_fare ? formatFare(flight.latest_fare) : "No fare data"}
                      </div>
                      {flight.latest_fare && (
                        <div className="text-xs text-gray-400">
                          {flight.latest_fare.price_change < -1
                            ? "Lower fare!"
                            : flight.latest_fare.price_change > 1
                            ? "Price increased"
                            : "No change"}
                        </div>
                      )}
                    </div>
                    {/* Seat */}
                    {flight.assigned_seat && (
                      <Badge variant="scheduled">Seat {flight.assigned_seat}</Badge>
                    )}
                    {/* Countdown */}
                    <div className="w-24 text-right">
                      <CountdownTimer
                        departureTime={flight.departure_time}
                        status={flight.checkin_status}
                      />
                    </div>
                    {/* Status */}
                    <StatusBadge status={flight.checkin_status} />
                  </div>
                </div>
              </div>

              {/* Expanded detail */}
              {selectedFlight === flight.id && (
                <div className="border-t border-gray-100 bg-gray-50 p-4">
                  <div className="grid grid-cols-2 gap-6">
                    {/* Fare History */}
                    <div>
                      <h4 className="font-medium text-sm mb-2">Fare History</h4>
                      {fareHistory.length === 0 ? (
                        <p className="text-gray-400 text-xs">
                          No fare checks yet. Fares are checked every 4 hours.
                        </p>
                      ) : (
                        <div className="space-y-1 max-h-48 overflow-y-auto">
                          {fareHistory.map((fare, i) => (
                            <div
                              key={i}
                              className="flex justify-between text-xs"
                            >
                              <span className="text-gray-400">
                                {new Date(fare.checked_at + "Z").toLocaleString()}
                              </span>
                              <span className={fareColor(fare)}>
                                {formatFare(fare)}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Worker Logs */}
                    <div>
                      <h4 className="font-medium text-sm mb-2">Activity Log</h4>
                      {logs.length === 0 ? (
                        <p className="text-gray-400 text-xs">No logs yet</p>
                      ) : (
                        <div className="space-y-1 max-h-48 overflow-y-auto">
                          {logs.map((log) => (
                            <div key={log.id} className="flex gap-2 text-xs font-mono">
                              <span className="text-gray-400 flex-shrink-0">
                                {new Date(log.created_at + "Z").toLocaleTimeString()}
                              </span>
                              <span
                                className={
                                  log.level === "error"
                                    ? "text-red-600"
                                    : log.level === "warning"
                                    ? "text-yellow-600"
                                    : "text-gray-600"
                                }
                              >
                                [{log.level}]
                              </span>
                              <span className="text-gray-700">{log.message}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
