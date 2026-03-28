"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/flights/status-badge";
import { CountdownTimer } from "@/components/flights/countdown-timer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Camera } from "lucide-react";
import type { WorkerLog } from "@/lib/types";

interface CaptureEntry {
  id: number;
  flight_id: string;
  capture_dir: string;
  manifest_json: string;
  file_count: number;
  total_size_bytes: number;
  created_at: string;
}

interface ManifestFile {
  name: string;
  type: string;
  size_bytes?: number;
  captured_at?: string;
}

interface FareInfo {
  price_change: number;
  best_flight_number?: string;
  best_flight_nonstop?: number;
  best_flight_stops?: string;
  best_flight_depart_time?: string;
  my_flight_fare?: number;
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
  original_price?: number | null;
  original_currency?: string;
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
  const [captures, setCaptures] = useState<CaptureEntry[]>([]);
  const [editingFare, setEditingFare] = useState<string | null>(null);
  const [fareInput, setFareInput] = useState("");

  async function saveOriginalFare(flightId: string) {
    await fetch(`/api/flights/${flightId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ original_price: fareInput ? Number(fareInput) : null }),
    });
    setEditingFare(null);
    setFareInput("");
    fetchFlights();
  }

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
    const [logsRes, faresRes, capturesRes] = await Promise.all([
      fetch(`/api/flights/${flightId}/logs`),
      fetch(`/api/flights/${flightId}/fares`),
      fetch(`/api/flights/${flightId}/captures`),
    ]);
    setLogs(await logsRes.json());
    setFareHistory(await faresRes.json());
    setCaptures(await capturesRes.json());
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
          {flights.map((flight) => {
            const lf = flight.latest_fare;
            const hasAlt = lf?.best_flight_number;
            const savings = hasAlt && lf?.my_flight_fare != null
              ? lf.my_flight_fare - lf.price_change
              : 0;

            return (
            <Card key={flight.id} className="overflow-hidden">
              <div
                className="p-4 cursor-pointer hover:bg-gray-50 transition-colors"
                onClick={() => expandFlight(flight.id)}
              >
                {/* Row 1: Flight info */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm font-medium">
                          {flight.confirmation_number}
                        </span>
                        {flight.flight_number && (
                          <span className="text-xs text-gray-400">WN {flight.flight_number}</span>
                        )}
                      </div>
                      <div className="text-sm text-gray-600 mt-0.5">
                        {flight.first_name} {flight.last_name}
                        {flight.assigned_seat && (
                          <span className="ml-2 text-xs font-medium text-blue-600">
                            Seat {flight.assigned_seat}
                          </span>
                        )}
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
                          weekday: "short", month: "short", day: "numeric",
                        })}
                      </div>
                      <div className="text-xs text-gray-400">
                        {new Date(flight.departure_time).toLocaleTimeString(undefined, {
                          hour: "2-digit", minute: "2-digit",
                        })}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    {/* Fare + original price */}
                    <div className="text-right">
                      {editingFare === flight.id ? (
                        <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                          <span className="text-xs text-gray-400">$</span>
                          <Input
                            value={fareInput}
                            onChange={(e) => setFareInput(e.target.value)}
                            className="h-7 w-20 text-xs"
                            placeholder="0"
                            type="number"
                            autoFocus
                            onKeyDown={(e) => {
                              if (e.key === "Enter") saveOriginalFare(flight.id);
                              if (e.key === "Escape") setEditingFare(null);
                            }}
                          />
                          <Button size="sm" className="h-7 text-xs" onClick={() => saveOriginalFare(flight.id)}>
                            Save
                          </Button>
                        </div>
                      ) : (
                        <>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setEditingFare(flight.id);
                              setFareInput(flight.original_price ? String(flight.original_price) : "");
                            }}
                            className="text-xs text-gray-400 hover:text-blue-600"
                          >
                            {flight.original_price ? `Paid $${flight.original_price.toLocaleString()}` : "$ Set fare"}
                          </button>
                          <div className={`text-sm ${fareColor(lf)}`}>
                            {lf ? formatFare(lf) : "No fare data"}
                          </div>
                        </>
                      )}
                    </div>
                    <div className="w-24 text-right">
                      <CountdownTimer departureTime={flight.departure_time} status={flight.checkin_status} />
                    </div>
                    <StatusBadge status={flight.checkin_status} />
                  </div>
                </div>

                {/* Row 2: Better flight alternative (if exists) */}
                {hasAlt && (
                  <div className="mt-3 rounded-lg border border-green-200 bg-green-50 p-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="text-xs font-semibold text-green-700 uppercase">Better Flight</span>
                        <span className="text-sm font-medium text-green-800">
                          WN {lf.best_flight_number}
                        </span>
                        {lf.best_flight_stops && (
                          <span className="text-xs text-green-600">{lf.best_flight_stops}</span>
                        )}
                        {lf.best_flight_depart_time && (
                          <span className="text-xs text-green-600">
                            Departs {lf.best_flight_depart_time}
                          </span>
                        )}
                      </div>
                      <div className="text-right">
                        <span className="text-sm font-medium text-green-700">
                          {formatFare(lf)}
                        </span>
                        {savings > 0 && (
                          <span className="ml-2 text-xs text-green-600">
                            Save ${savings.toLocaleString()}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                )}
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
                            <div key={i} className="text-xs">
                              <div className="flex justify-between">
                                <span className="text-gray-400">
                                  {new Date(fare.checked_at + "Z").toLocaleString()}
                                </span>
                                <span className={fareColor(fare)}>
                                  {formatFare(fare)}
                                </span>
                              </div>
                              {fare.best_flight_number && (
                                <div className="text-green-600 ml-4">
                                  Better: WN {fare.best_flight_number}
                                  {fare.best_flight_nonstop ? " (Nonstop)" : ""}
                                </div>
                              )}
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

                  {/* Check-In Captures */}
                  {captures.length > 0 && (
                    <div className="mt-4 border-t border-gray-200 pt-4">
                      <h4 className="font-medium text-sm mb-3 flex items-center gap-2">
                        <Camera className="h-4 w-4" /> Check-In Captures
                      </h4>
                      {captures.map((cap) => {
                        let manifest: { files?: ManifestFile[]; errors?: string[]; network_requests_captured?: number } = {};
                        try {
                          manifest = JSON.parse(cap.manifest_json || "{}");
                        } catch { /* ignore */ }
                        const screenshots = (manifest.files || []).filter((f) => f.type === "screenshot");
                        const jsonFiles = (manifest.files || []).filter((f) => f.type === "json");
                        const domFiles = (manifest.files || []).filter((f) => f.type === "dom");

                        return (
                          <div key={cap.id} className="rounded border border-gray-200 bg-white p-3 space-y-3">
                            <div className="flex items-center justify-between text-xs text-gray-500">
                              <span>
                                Captured {new Date(cap.created_at + "Z").toLocaleString()} &middot;{" "}
                                {cap.file_count} files &middot;{" "}
                                {(cap.total_size_bytes / 1024).toFixed(0)} KB
                              </span>
                              <span>
                                {manifest.network_requests_captured ?? 0} network events
                              </span>
                            </div>

                            {/* Screenshots */}
                            {screenshots.length > 0 && (
                              <div>
                                <div className="text-xs font-medium text-gray-600 mb-1">Screenshots</div>
                                <div className="flex gap-2 overflow-x-auto">
                                  {screenshots.map((f) => (
                                    <a
                                      key={f.name}
                                      href={`/api/captures/${cap.id}/files?name=${f.name}`}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="flex-shrink-0"
                                    >
                                      {/* eslint-disable-next-line @next/next/no-img-element */}
                                      <img
                                        src={`/api/captures/${cap.id}/files?name=${f.name}`}
                                        alt={f.name}
                                        className="h-24 rounded border border-gray-200 hover:border-blue-400 transition-colors"
                                      />
                                      <div className="text-xs text-gray-400 mt-0.5 text-center">
                                        {f.name.replace(".png", "")}
                                      </div>
                                    </a>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* API Responses & DOM */}
                            <div className="flex gap-2 flex-wrap">
                              {jsonFiles.map((f) => (
                                <a
                                  key={f.name}
                                  href={`/api/captures/${cap.id}/files?name=${f.name}`}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-xs px-2 py-1 rounded bg-blue-50 text-blue-700 hover:bg-blue-100"
                                >
                                  {f.name}
                                </a>
                              ))}
                              {domFiles.map((f) => (
                                <a
                                  key={f.name}
                                  href={`/api/captures/${cap.id}/files?name=${f.name}`}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-xs px-2 py-1 rounded bg-purple-50 text-purple-700 hover:bg-purple-100"
                                >
                                  {f.name}
                                </a>
                              ))}
                            </div>

                            {/* Errors */}
                            {manifest.errors && manifest.errors.length > 0 && (
                              <div className="text-xs text-red-500">
                                {manifest.errors.length} capture error(s): {manifest.errors[0]}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </Card>
          );
          })}
        </div>
      )}
    </div>
  );
}
