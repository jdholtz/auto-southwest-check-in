"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/flights/status-badge";
import { CountdownTimer } from "@/components/flights/countdown-timer";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Plus, Trash2, ChevronDown, ChevronRight } from "lucide-react";
import type { Reservation } from "@/lib/types";

export default function ReservationsPage() {
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [open, setOpen] = useState(false);
  const [confirmationNumber, setConfirmationNumber] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchReservations();
  }, []);

  async function fetchReservations() {
    const res = await fetch("/api/reservations");
    setReservations(await res.json());
  }

  async function addReservation(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    await fetch("/api/reservations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        confirmation_number: confirmationNumber,
        first_name: firstName,
        last_name: lastName,
      }),
    });
    setConfirmationNumber("");
    setFirstName("");
    setLastName("");
    setOpen(false);
    setLoading(false);
    fetchReservations();
  }

  async function deleteReservation(id: string) {
    if (!confirm("Delete this reservation and all its flights?")) return;
    await fetch(`/api/reservations/${id}`, { method: "DELETE" });
    fetchReservations();
  }

  function toggleExpand(id: string) {
    const next = new Set(expanded);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setExpanded(next);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Reservations</h1>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" /> Add Reservation
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add Reservation</DialogTitle>
            </DialogHeader>
            <form onSubmit={addReservation} className="space-y-4 mt-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Confirmation Number
                </label>
                <Input
                  value={confirmationNumber}
                  onChange={(e) => setConfirmationNumber(e.target.value)}
                  placeholder="e.g. ABC123"
                  maxLength={6}
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">First Name</label>
                <Input
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  placeholder="First name"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Last Name</label>
                <Input
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  placeholder="Last name"
                  required
                />
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "Adding..." : "Add Reservation"}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Reservations</CardTitle>
        </CardHeader>
        <CardContent>
          {reservations.length === 0 ? (
            <p className="text-gray-500 text-sm">No reservations yet</p>
          ) : (
            <div className="space-y-2">
              {reservations.map((res) => (
                <div key={res.id} className="rounded-lg border border-gray-200">
                  <div
                    className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50"
                    onClick={() => toggleExpand(res.id)}
                  >
                    <div className="flex items-center gap-3">
                      {expanded.has(res.id) ? (
                        <ChevronDown className="h-4 w-4 text-gray-400" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-gray-400" />
                      )}
                      <div>
                        <div className="font-medium">
                          {res.confirmation_number}{" "}
                          <span className="text-gray-500 font-normal">
                            &mdash; {res.first_name} {res.last_name}
                          </span>
                        </div>
                        <div className="text-xs text-gray-400">
                          {(res as Reservation & { account_username?: string }).account_username
                            ? `Account: ${(res as Reservation & { account_username?: string }).account_username}`
                            : "Manual reservation"}
                          {" "}&middot; {res.flights?.length ?? 0} flight(s)
                          {res.flights && res.flights.length > 0 && (
                            <>
                              {" "}&middot;{" "}
                              {res.flights.map((f, i) => (
                                <span key={f.id}>
                                  {i > 0 && ", "}
                                  {f.departure_airport}
                                  {f.destination_airport ? ` → ${f.destination_airport}` : ""}
                                </span>
                              ))}
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={res.is_active ? "active" : "inactive"}>
                        {res.is_active ? "Active" : "Inactive"}
                      </Badge>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteReservation(res.id);
                        }}
                      >
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </div>
                  </div>
                  {expanded.has(res.id) && res.flights && res.flights.length > 0 && (
                    <div className="border-t border-gray-100 bg-gray-50 p-4">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-left text-gray-500">
                            <th className="pb-2 font-medium">Flight</th>
                            <th className="pb-2 font-medium">Route</th>
                            <th className="pb-2 font-medium">Departure</th>
                            <th className="pb-2 font-medium">Check-in In</th>
                            <th className="pb-2 font-medium">Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {res.flights.map((f) => (
                            <tr key={f.id}>
                              <td className="py-2 font-mono">{f.flight_number || "—"}</td>
                              <td className="py-2">
                                <span className="font-medium">{f.departure_airport}</span>
                                {" "}&rarr;{" "}
                                <span className="font-medium">{f.destination_airport}</span>
                              </td>
                              <td className="py-2">
                                <div>{new Date(f.departure_time).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}</div>
                                <div className="text-xs text-gray-400">{new Date(f.departure_time).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}</div>
                              </td>
                              <td className="py-2">
                                <CountdownTimer departureTime={f.departure_time} status={f.checkin_status} />
                              </td>
                              <td className="py-2">
                                <StatusBadge status={f.checkin_status} />
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
