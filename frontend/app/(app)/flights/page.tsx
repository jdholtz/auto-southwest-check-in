"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/flights/status-badge";
import { CountdownTimer } from "@/components/flights/countdown-timer";
import type { Flight, WorkerLog } from "@/lib/types";

export default function FlightsPage() {
  const [flights, setFlights] = useState<Flight[]>([]);
  const [selectedFlight, setSelectedFlight] = useState<string | null>(null);
  const [logs, setLogs] = useState<WorkerLog[]>([]);

  useEffect(() => {
    fetchFlights();
    const interval = setInterval(fetchFlights, 30000);
    return () => clearInterval(interval);
  }, []);

  async function fetchFlights() {
    const res = await fetch("/api/flights");
    setFlights(await res.json());
  }

  async function viewLogs(flightId: string) {
    if (selectedFlight === flightId) {
      setSelectedFlight(null);
      return;
    }
    setSelectedFlight(flightId);
    const res = await fetch(`/api/flights/${flightId}/logs`);
    setLogs(await res.json());
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Flights</h1>

      <Card>
        <CardHeader>
          <CardTitle>All Flights</CardTitle>
        </CardHeader>
        <CardContent>
          {flights.length === 0 ? (
            <p className="text-gray-500 text-sm">No flights tracked yet</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500">
                    <th className="pb-3 font-medium">Confirmation</th>
                    <th className="pb-3 font-medium">Passenger</th>
                    <th className="pb-3 font-medium">Flight</th>
                    <th className="pb-3 font-medium">Route</th>
                    <th className="pb-3 font-medium">Departure</th>
                    <th className="pb-3 font-medium">Check-in In</th>
                    <th className="pb-3 font-medium">Seat</th>
                    <th className="pb-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {flights.map((flight) => (
                    <>
                      <tr
                        key={flight.id}
                        className="border-b last:border-0 cursor-pointer hover:bg-gray-50"
                        onClick={() => viewLogs(flight.id)}
                      >
                        <td className="py-3 font-mono">{flight.confirmation_number}</td>
                        <td className="py-3">
                          {flight.first_name} {flight.last_name}
                        </td>
                        <td className="py-3">{flight.flight_number || "—"}</td>
                        <td className="py-3">
                          {flight.departure_airport} &rarr; {flight.destination_airport}
                        </td>
                        <td className="py-3 text-gray-600">
                          {new Date(flight.departure_time).toLocaleString()}
                        </td>
                        <td className="py-3">
                          <CountdownTimer
                            departureTime={flight.departure_time}
                            status={flight.checkin_status}
                          />
                        </td>
                        <td className="py-3 font-mono text-sm">
                          {(flight as Flight & { assigned_seat?: string }).assigned_seat || "—"}
                        </td>
                        <td className="py-3">
                          <StatusBadge status={flight.checkin_status} />
                        </td>
                      </tr>
                      {selectedFlight === flight.id && (
                        <tr key={`${flight.id}-logs`}>
                          <td colSpan={8} className="bg-gray-50 p-4">
                            <div className="space-y-2">
                              <h4 className="font-medium text-sm">
                                Worker Logs
                                {flight.checkin_result && (
                                  <span className="ml-2 text-green-600 font-normal">
                                    Check-in result available
                                  </span>
                                )}
                              </h4>
                              {logs.length === 0 ? (
                                <p className="text-gray-400 text-xs">No logs yet</p>
                              ) : (
                                <div className="space-y-1 max-h-48 overflow-y-auto">
                                  {logs.map((log) => (
                                    <div key={log.id} className="flex gap-2 text-xs font-mono">
                                      <span className="text-gray-400 flex-shrink-0">
                                        {new Date(log.created_at).toLocaleTimeString()}
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
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
