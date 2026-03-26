import { Badge } from "@/components/ui/badge";

const statusLabels: Record<string, string> = {
  pending: "Pending",
  scheduled: "Scheduled",
  checking_in: "Checking In",
  success: "Success",
  failed: "Failed",
};

export function StatusBadge({ status }: { status: string }) {
  const variant = status as "pending" | "scheduled" | "checking_in" | "success" | "failed";
  return <Badge variant={variant}>{statusLabels[status] || status}</Badge>;
}
