"use client";

import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { RefreshCw } from "lucide-react";

interface LogEntry {
  id: number;
  flight_id: string | null;
  level: string;
  message: string;
  created_at: string;
  flight_number?: string;
  departure_airport?: string;
  destination_airport?: string;
}

const levelColors: Record<string, string> = {
  info: "bg-blue-500",
  warning: "bg-yellow-500",
  error: "bg-red-500",
};

const levelBg: Record<string, string> = {
  info: "bg-blue-50 text-blue-700",
  warning: "bg-yellow-50 text-yellow-700",
  error: "bg-red-50 text-red-700",
};

export default function ActivityPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [level, setLevel] = useState("all");
  const [loading, setLoading] = useState(false);

  const fetchLogs = useCallback(async (reset = false) => {
    setLoading(true);
    const offset = reset ? 0 : logs.length;
    const res = await fetch(`/api/activity?level=${level}&limit=50&offset=${offset}`);
    const data = await res.json();
    if (reset) {
      setLogs(data.logs);
    } else {
      setLogs((prev) => [...prev, ...data.logs]);
    }
    setTotal(data.total);
    setLoading(false);
  }, [level, logs.length]);

  useEffect(() => {
    fetchLogs(true);
    const interval = setInterval(() => fetchLogs(true), 15000);
    return () => clearInterval(interval);
  }, [level]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Activity Log</h1>
        <Button variant="outline" size="sm" onClick={() => fetchLogs(true)} disabled={loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </Button>
      </div>

      <div className="flex gap-2">
        {["all", "info", "warning", "error"].map((l) => (
          <Button
            key={l}
            variant={level === l ? "default" : "outline"}
            size="sm"
            onClick={() => setLevel(l)}
          >
            {l === "all" ? "All" : l.charAt(0).toUpperCase() + l.slice(1)}
          </Button>
        ))}
        <span className="ml-auto text-sm text-gray-500 self-center">{total} total entries</span>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Worker Activity</CardTitle>
        </CardHeader>
        <CardContent>
          {logs.length === 0 ? (
            <p className="text-gray-500 text-sm">No activity yet</p>
          ) : (
            <div className="space-y-2">
              {logs.map((log) => (
                <div
                  key={log.id}
                  className="flex items-start gap-3 rounded-lg border border-gray-100 p-3"
                >
                  <span
                    className={`mt-1 h-2.5 w-2.5 rounded-full flex-shrink-0 ${levelColors[log.level] || "bg-gray-400"}`}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${levelBg[log.level] || "bg-gray-100 text-gray-600"}`}>
                        {log.level}
                      </span>
                      {log.flight_number && (
                        <span className="text-xs text-gray-400">
                          Flight {log.flight_number} ({log.departure_airport} &rarr; {log.destination_airport})
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-700 mt-1">{log.message}</p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {new Date(log.created_at + "Z").toLocaleString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
          {logs.length < total && (
            <Button
              variant="outline"
              className="w-full mt-4"
              onClick={() => fetchLogs(false)}
              disabled={loading}
            >
              Load More ({total - logs.length} remaining)
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
