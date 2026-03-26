"use client";

import { useEffect, useState } from "react";

function getTimeUntil(targetDate: string): string {
  const now = new Date();
  const checkinTime = new Date(new Date(targetDate).getTime() - 24 * 60 * 60 * 1000);
  const diff = checkinTime.getTime() - now.getTime();

  if (diff <= 0) return "Now";

  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
  const seconds = Math.floor((diff % (1000 * 60)) / 1000);

  if (days > 0) return `${days}d ${hours}h ${minutes}m`;
  if (hours > 0) return `${hours}h ${minutes}m ${seconds}s`;
  return `${minutes}m ${seconds}s`;
}

export function CountdownTimer({ departureTime, status }: { departureTime: string; status: string }) {
  const [timeLeft, setTimeLeft] = useState(getTimeUntil(departureTime));

  useEffect(() => {
    if (status === "success" || status === "failed") return;
    const interval = setInterval(() => setTimeLeft(getTimeUntil(departureTime)), 1000);
    return () => clearInterval(interval);
  }, [departureTime, status]);

  if (status === "success") return <span className="text-green-600 text-sm">Checked in</span>;
  if (status === "failed") return <span className="text-red-600 text-sm">Failed</span>;

  return <span className="text-sm font-mono text-blue-600">{timeLeft}</span>;
}
