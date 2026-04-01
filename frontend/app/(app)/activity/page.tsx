"use client";

import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { RefreshCw, AlertTriangle } from "lucide-react";

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

interface DiagnosticEntry {
  id: number;
  category: string;
  endpoint: string;
  expected_behavior: string;
  actual_behavior: string;
  headers_snapshot: string;
  response_snapshot: string;
  created_at: string;
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

const categoryColors: Record<string, string> = {
  auth_failure: "bg-red-100 text-red-700",
  api_error: "bg-orange-100 text-orange-700",
  api_change: "bg-purple-100 text-purple-700",
  checkin_failure: "bg-red-100 text-red-700",
  unexpected_response: "bg-yellow-100 text-yellow-700",
};

export default function ActivityPage() {
  const [tab, setTab] = useState<"activity" | "diagnostics">("activity");
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [level, setLevel] = useState("all");
  const [loading, setLoading] = useState(false);

  // Diagnostics state
  const [diagnostics, setDiagnostics] = useState<DiagnosticEntry[]>([]);
  const [diagTotal, setDiagTotal] = useState(0);
  const [diagCategory, setDiagCategory] = useState("all");
  const [categories, setCategories] = useState<string[]>([]);
  const [expandedDiag, setExpandedDiag] = useState<number | null>(null);

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

  const fetchDiagnostics = useCallback(async (reset = false) => {
    setLoading(true);
    const offset = reset ? 0 : diagnostics.length;
    const res = await fetch(`/api/diagnostics?category=${diagCategory}&limit=50&offset=${offset}`);
    const data = await res.json();
    if (reset) {
      setDiagnostics(data.diagnostics);
    } else {
      setDiagnostics((prev) => [...prev, ...data.diagnostics]);
    }
    setDiagTotal(data.total);
    setCategories(data.categories || []);
    setLoading(false);
  }, [diagCategory, diagnostics.length]);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;

    function startPolling() {
      if (tab === "activity") {
        fetchLogs(true);
        interval = setInterval(() => fetchLogs(true), 60000);
      } else {
        fetchDiagnostics(true);
        interval = setInterval(() => fetchDiagnostics(true), 60000);
      }
    }

    function handleVisibility() {
      clearInterval(interval);
      if (document.visibilityState === "visible") {
        startPolling();
      }
    }

    startPolling();
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [tab, level, diagCategory]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Activity</h1>
        <Button
          variant="outline"
          size="sm"
          onClick={() => (tab === "activity" ? fetchLogs(true) : fetchDiagnostics(true))}
          disabled={loading}
        >
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </Button>
      </div>

      {/* Tab switcher */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit">
        <button
          onClick={() => setTab("activity")}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
            tab === "activity" ? "bg-white shadow text-gray-900" : "text-gray-500 hover:text-gray-700"
          }`}
        >
          Activity Log
        </button>
        <button
          onClick={() => setTab("diagnostics")}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors flex items-center gap-1.5 ${
            tab === "diagnostics" ? "bg-white shadow text-gray-900" : "text-gray-500 hover:text-gray-700"
          }`}
        >
          <AlertTriangle className="h-3.5 w-3.5" /> Diagnostics
        </button>
      </div>

      {tab === "activity" ? (
        <>
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
            <span className="ml-auto text-sm text-gray-500 self-center">{total} entries</span>
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
                          <span
                            className={`text-xs px-1.5 py-0.5 rounded font-medium ${levelBg[log.level] || "bg-gray-100 text-gray-600"}`}
                          >
                            {log.level}
                          </span>
                          {log.flight_number && (
                            <span className="text-xs text-gray-400">
                              Flight {log.flight_number} ({log.departure_airport} &rarr;{" "}
                              {log.destination_airport})
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
        </>
      ) : (
        <>
          <div className="flex gap-2 flex-wrap">
            <Button
              variant={diagCategory === "all" ? "default" : "outline"}
              size="sm"
              onClick={() => setDiagCategory("all")}
            >
              All
            </Button>
            {categories.map((cat) => (
              <Button
                key={cat}
                variant={diagCategory === cat ? "default" : "outline"}
                size="sm"
                onClick={() => setDiagCategory(cat)}
              >
                {cat.replace(/_/g, " ")}
              </Button>
            ))}
            <span className="ml-auto text-sm text-gray-500 self-center">{diagTotal} entries</span>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>API Diagnostics</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-gray-500 mb-4">
                Structured diagnostic entries logged when API calls fail or return unexpected
                responses. Helps track Southwest API changes over time.
              </p>
              {diagnostics.length === 0 ? (
                <p className="text-gray-500 text-sm">No diagnostics yet</p>
              ) : (
                <div className="space-y-2">
                  {diagnostics.map((diag) => (
                    <div
                      key={diag.id}
                      className="rounded-lg border border-gray-200 overflow-hidden"
                    >
                      <div
                        className="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-50"
                        onClick={() =>
                          setExpandedDiag(expandedDiag === diag.id ? null : diag.id)
                        }
                      >
                        <div className="flex items-center gap-2">
                          <span
                            className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                              categoryColors[diag.category] || "bg-gray-100 text-gray-600"
                            }`}
                          >
                            {diag.category.replace(/_/g, " ")}
                          </span>
                          <span className="text-sm text-gray-700 font-mono">
                            {diag.endpoint}
                          </span>
                        </div>
                        <span className="text-xs text-gray-400">
                          {new Date(diag.created_at + "Z").toLocaleString()}
                        </span>
                      </div>
                      {expandedDiag === diag.id && (
                        <div className="border-t border-gray-100 bg-gray-50 p-4 space-y-3 text-sm">
                          <div>
                            <span className="font-medium text-gray-600">Expected: </span>
                            <span className="text-green-700">{diag.expected_behavior}</span>
                          </div>
                          <div>
                            <span className="font-medium text-gray-600">Actual: </span>
                            <span className="text-red-700">{diag.actual_behavior}</span>
                          </div>
                          {diag.headers_snapshot && (
                            <div>
                              <span className="font-medium text-gray-600">Headers sent: </span>
                              <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">
                                {diag.headers_snapshot}
                              </code>
                            </div>
                          )}
                          {diag.response_snapshot && (
                            <div>
                              <span className="font-medium text-gray-600">Response: </span>
                              <pre className="text-xs bg-gray-100 p-2 rounded mt-1 overflow-x-auto max-h-40">
                                {diag.response_snapshot}
                              </pre>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
              {diagnostics.length < diagTotal && (
                <Button
                  variant="outline"
                  className="w-full mt-4"
                  onClick={() => fetchDiagnostics(false)}
                  disabled={loading}
                >
                  Load More ({diagTotal - diagnostics.length} remaining)
                </Button>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
