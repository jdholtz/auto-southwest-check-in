"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Trash2, Plus } from "lucide-react";
import type { NotificationConfig } from "@/lib/types";

export default function SettingsPage() {
  const [notifications, setNotifications] = useState<NotificationConfig[]>([]);
  const [serviceUrl, setServiceUrl] = useState("");
  const [notificationLevel, setNotificationLevel] = useState(1);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchNotifications();
  }, []);

  async function fetchNotifications() {
    const res = await fetch("/api/notifications");
    setNotifications(await res.json());
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

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Settings</h1>

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
          )}
        </CardContent>
      </Card>
    </div>
  );
}
