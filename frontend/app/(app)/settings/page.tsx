"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Trash2, Plus, Save, MessageSquare } from "lucide-react";
import type { NotificationConfig } from "@/lib/types";

const ALL_SEAT_LETTERS = ["A", "B", "C", "D", "E", "F"];

export default function SettingsPage() {
  const [notifications, setNotifications] = useState<NotificationConfig[]>([]);
  const [serviceUrl, setServiceUrl] = useState("");
  const [notificationLevel, setNotificationLevel] = useState(1);
  const [loading, setLoading] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  // Twilio SMS quick setup
  const [twilioSid, setTwilioSid] = useState("");
  const [twilioToken, setTwilioToken] = useState("");
  const [twilioFrom, setTwilioFrom] = useState("");
  const [twilioTo, setTwilioTo] = useState("");
  const [smsLoading, setSmsLoading] = useState(false);

  // Seat preferences
  const [preferredLetters, setPreferredLetters] = useState<string[]>(["A", "F"]);
  const [preferredRows, setPreferredRows] = useState("1,2,3,4,5,6");
  const [fallbackLetters, setFallbackLetters] = useState<string[]>(["A", "C", "D", "F"]);
  const [fareCheckMode, setFareCheckMode] = useState("same_day_nonstop");
  const [seatSaved, setSeatSaved] = useState(false);

  useEffect(() => {
    fetchNotifications();
    fetchPreferences();
  }, []);

  async function fetchNotifications() {
    const res = await fetch("/api/notifications");
    setNotifications(await res.json());
  }

  async function fetchPreferences() {
    const res = await fetch("/api/preferences");
    const data = await res.json();
    if (data.preferred_letters) setPreferredLetters(data.preferred_letters.split(","));
    if (data.preferred_rows) setPreferredRows(data.preferred_rows);
    if (data.fallback_letters) setFallbackLetters(data.fallback_letters.split(","));
    if (data.fare_check_mode) setFareCheckMode(data.fare_check_mode);
  }

  async function addNotification(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    await fetch("/api/notifications", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ service_url: serviceUrl, notification_level: notificationLevel }),
    });
    setServiceUrl("");
    setNotificationLevel(1);
    setLoading(false);
    fetchNotifications();
  }

  async function deleteNotification(id: string) {
    await fetch(`/api/notifications/${id}`, { method: "DELETE" });
    fetchNotifications();
  }

  async function testNotifications() {
    setTestResult(null);
    const res = await fetch("/api/notifications/test", { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      setTestResult(data.message);
    } else {
      setTestResult(data.error || "Test failed");
    }
    setTimeout(() => setTestResult(null), 5000);
  }

  async function savePreferences() {
    setSeatSaved(false);
    await fetch("/api/preferences", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        preferred_letters: preferredLetters.join(","),
        preferred_rows: preferredRows,
        fallback_letters: fallbackLetters.join(","),
        fare_check_mode: fareCheckMode,
      }),
    });
    setSeatSaved(true);
    setTimeout(() => setSeatSaved(false), 2000);
  }

  async function addTwilioSms(e: React.FormEvent) {
    e.preventDefault();
    if (!twilioSid || !twilioToken || !twilioFrom || !twilioTo) return;
    setSmsLoading(true);
    const fromClean = twilioFrom.replace(/\D/g, "");
    const toClean = twilioTo.replace(/\D/g, "");
    const url = `twilio://${twilioSid}:${twilioToken}@+${fromClean}/+${toClean}`;
    await fetch("/api/notifications", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ service_url: url, notification_level: 1 }),
    });
    setTwilioSid("");
    setTwilioToken("");
    setTwilioFrom("");
    setTwilioTo("");
    setSmsLoading(false);
    fetchNotifications();
  }

  function toggleLetter(letter: string, list: string[], setList: (v: string[]) => void) {
    if (list.includes(letter)) {
      setList(list.filter((l) => l !== letter));
    } else {
      setList([...list, letter].sort());
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Settings</h1>

      {/* Seat Preferences */}
      <Card>
        <CardHeader>
          <CardTitle>Seat Preferences</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-gray-500">
            Configure your preferred seat selections. Southwest now assigns seats at booking or
            check-in. For Basic fares, a seat is assigned at check-in. For A-List members, the app
            will attempt to upgrade to a preferred seat 48 hours before departure. These preferences
            determine which seats the system will target.
          </p>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Preferred Seat Letters
            </label>
            <div className="flex gap-2">
              {ALL_SEAT_LETTERS.map((letter) => (
                <button
                  key={letter}
                  onClick={() => toggleLetter(letter, preferredLetters, setPreferredLetters)}
                  className={`w-10 h-10 rounded-md text-sm font-medium border transition-colors ${
                    preferredLetters.includes(letter)
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
                  }`}
                >
                  {letter}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Preferred Rows (comma-separated)
            </label>
            <Input
              value={preferredRows}
              onChange={(e) => setPreferredRows(e.target.value)}
              placeholder="1,2,3,4,5,6"
            />
            <p className="text-xs text-gray-400 mt-1">
              Rows where your preferred letters will be prioritized (e.g., rows 1-6 for front seats)
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Fallback Seat Letters
            </label>
            <div className="flex gap-2">
              {ALL_SEAT_LETTERS.map((letter) => (
                <button
                  key={letter}
                  onClick={() => toggleLetter(letter, fallbackLetters, setFallbackLetters)}
                  className={`w-10 h-10 rounded-md text-sm font-medium border transition-colors ${
                    fallbackLetters.includes(letter)
                      ? "bg-orange-500 text-white border-orange-500"
                      : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
                  }`}
                >
                  {letter}
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-400 mt-1">
              Used when preferred seats in your target rows are not available
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Fare Check Mode
            </label>
            <div className="space-y-2">
              {[
                { value: "same_flight", label: "Same Flight Only", desc: "Only check your exact booked flight for price changes" },
                { value: "same_day_nonstop", label: "Same Day - Nonstop", desc: "Check all nonstop flights on your route that day (recommended)" },
                { value: "same_day", label: "Same Day - All Flights", desc: "Check all flights including connections on your route that day" },
              ].map((opt) => (
                <label
                  key={opt.value}
                  className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                    fareCheckMode === opt.value
                      ? "border-blue-500 bg-blue-50"
                      : "border-gray-200 hover:bg-gray-50"
                  }`}
                >
                  <input
                    type="radio"
                    name="fareCheckMode"
                    value={opt.value}
                    checked={fareCheckMode === opt.value}
                    onChange={(e) => setFareCheckMode(e.target.value)}
                    className="mt-0.5"
                  />
                  <div>
                    <div className="text-sm font-medium">{opt.label}</div>
                    <div className="text-xs text-gray-400">{opt.desc}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          <Button onClick={savePreferences}>
            <Save className="mr-2 h-4 w-4" />
            {seatSaved ? "Saved!" : "Save Preferences"}
          </Button>
        </CardContent>
      </Card>

      {/* SMS Text Notifications */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5" /> SMS Text Notifications
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-gray-500">
            Get text message alerts for check-ins, fare drops, and status updates.
            Requires a Twilio account (free trial available).
          </p>
          <form onSubmit={addTwilioSms} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Twilio Account SID
                </label>
                <Input
                  value={twilioSid}
                  onChange={(e) => setTwilioSid(e.target.value)}
                  placeholder="ACxxxxxxxxxx"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Twilio Auth Token
                </label>
                <Input
                  type="password"
                  value={twilioToken}
                  onChange={(e) => setTwilioToken(e.target.value)}
                  placeholder="Auth token"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  From Phone Number
                </label>
                <Input
                  value={twilioFrom}
                  onChange={(e) => setTwilioFrom(e.target.value)}
                  placeholder="+1234567890"
                  required
                />
                <p className="text-xs text-gray-400 mt-0.5">Your Twilio phone number</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  To Phone Number
                </label>
                <Input
                  value={twilioTo}
                  onChange={(e) => setTwilioTo(e.target.value)}
                  placeholder="+1234567890"
                  required
                />
                <p className="text-xs text-gray-400 mt-0.5">Your mobile number</p>
              </div>
            </div>
            <Button type="submit" disabled={smsLoading}>
              <MessageSquare className="mr-2 h-4 w-4" />
              {smsLoading ? "Adding..." : "Add SMS Notification"}
            </Button>
          </form>
          <p className="text-xs text-gray-400">
            You can also use other SMS providers via Apprise URLs in the section below.
          </p>
        </CardContent>
      </Card>

      {/* Notifications */}
      <Card>
        <CardHeader>
          <CardTitle>Notification Services</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-gray-500">
            Add notification URLs using{" "}
            <a
              href="https://github.com/caronc/apprise#supported-notifications"
              className="text-blue-600 underline"
              target="_blank"
              rel="noreferrer"
            >
              Apprise URL format
            </a>
            . Examples: <code className="bg-gray-100 px-1 rounded text-xs">tgram://bottoken/ChatID</code>,{" "}
            <code className="bg-gray-100 px-1 rounded text-xs">discord://WebhookID/WebhookToken</code>
          </p>

          <form onSubmit={addNotification} className="flex gap-2">
            <Input
              value={serviceUrl}
              onChange={(e) => setServiceUrl(e.target.value)}
              placeholder="Apprise notification URL"
              className="flex-1"
              required
            />
            <select
              value={notificationLevel}
              onChange={(e) => setNotificationLevel(Number(e.target.value))}
              className="rounded-md border border-gray-300 px-3 py-2 text-sm"
            >
              <option value={1}>Level 1 (All)</option>
              <option value={2}>Level 2</option>
              <option value={3}>Level 3</option>
              <option value={4}>Level 4</option>
              <option value={5}>Level 5 (Critical only)</option>
            </select>
            <Button type="submit" disabled={loading}>
              <Plus className="mr-1 h-4 w-4" /> Add
            </Button>
          </form>

          {notifications.length > 0 && (
            <>
              <div className="space-y-2">
                {notifications.map((n) => (
                  <div
                    key={n.id}
                    className="flex items-center justify-between rounded-lg border border-gray-200 p-3"
                  >
                    <div>
                      <code className="text-sm bg-gray-50 px-2 py-0.5 rounded">{n.service_url}</code>
                      <span className="ml-2 text-xs text-gray-400">Level {n.notification_level}</span>
                    </div>
                    <Button variant="ghost" size="icon" onClick={() => deleteNotification(n.id)}>
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </Button>
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-3">
                <Button variant="outline" onClick={testNotifications}>
                  Send Test Notification
                </Button>
                {testResult && (
                  <span className="text-sm text-green-600">{testResult}</span>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
