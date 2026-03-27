"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Plus, Trash2 } from "lucide-react";
import type { Account } from "@/lib/types";

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [open, setOpen] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isAlist, setIsAlist] = useState(false);
  const [autoUpgrade, setAutoUpgrade] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchAccounts();
  }, []);

  async function fetchAccounts() {
    const res = await fetch("/api/accounts");
    setAccounts(await res.json());
  }

  async function addAccount(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    await fetch("/api/accounts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, is_alist: isAlist, auto_upgrade_seats: autoUpgrade }),
    });
    setUsername("");
    setPassword("");
    setIsAlist(false);
    setAutoUpgrade(false);
    setOpen(false);
    setLoading(false);
    fetchAccounts();
  }

  async function toggleField(id: string, field: string, currentValue: number) {
    await fetch(`/api/accounts/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [field]: !currentValue }),
    });
    fetchAccounts();
  }

  async function toggleActive(id: string, currentActive: number) {
    await fetch(`/api/accounts/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: !currentActive }),
    });
    fetchAccounts();
  }

  async function deleteAccount(id: string) {
    if (!confirm("Delete this account and all its reservations?")) return;
    await fetch(`/api/accounts/${id}`, { method: "DELETE" });
    fetchAccounts();
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Accounts</h1>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" /> Add Account
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add Southwest Account</DialogTitle>
            </DialogHeader>
            <form onSubmit={addAccount} className="space-y-4 mt-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
                <Input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Southwest username"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Southwest password"
                  required
                />
              </div>
              <div className="flex items-center justify-between rounded-lg border border-gray-200 p-3">
                <div>
                  <div className="text-sm font-medium">A-List Status</div>
                  <div className="text-xs text-gray-400">Enable for A-List or A-List Preferred members</div>
                </div>
                <button
                  type="button"
                  onClick={() => setIsAlist(!isAlist)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${isAlist ? "bg-blue-600" : "bg-gray-200"}`}
                >
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${isAlist ? "translate-x-6" : "translate-x-1"}`} />
                </button>
              </div>
              <div className="flex items-center justify-between rounded-lg border border-gray-200 p-3">
                <div>
                  <div className="text-sm font-medium">Auto Seat Upgrade</div>
                  <div className="text-xs text-gray-400">Attempt seat upgrade 48h before departure</div>
                </div>
                <button
                  type="button"
                  onClick={() => setAutoUpgrade(!autoUpgrade)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${autoUpgrade ? "bg-blue-600" : "bg-gray-200"}`}
                >
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${autoUpgrade ? "translate-x-6" : "translate-x-1"}`} />
                </button>
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "Adding..." : "Add Account"}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Southwest Accounts</CardTitle>
        </CardHeader>
        <CardContent>
          {accounts.length === 0 ? (
            <p className="text-gray-500 text-sm">No accounts added yet</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500">
                    <th className="pb-3 font-medium">Username</th>
                    <th className="pb-3 font-medium">Status</th>
                    <th className="pb-3 font-medium">Tier</th>
                    <th className="pb-3 font-medium">Seat Upgrade</th>
                    <th className="pb-3 font-medium">Reservations</th>
                    <th className="pb-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {accounts.map((account) => (
                    <tr key={account.id} className="border-b last:border-0">
                      <td className="py-3 font-medium">{account.username}</td>
                      <td className="py-3">
                        <Badge variant={account.is_active ? "active" : "inactive"}>
                          {account.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </td>
                      <td className="py-3">
                        <button onClick={() => toggleField(account.id, "is_alist", account.is_alist)}>
                          <Badge variant={account.is_alist ? "success" : "default"}>
                            {account.is_alist ? "A-List" : "Standard"}
                          </Badge>
                        </button>
                      </td>
                      <td className="py-3">
                        <button onClick={() => toggleField(account.id, "auto_upgrade_seats", account.auto_upgrade_seats)}>
                          <Badge variant={account.auto_upgrade_seats ? "scheduled" : "default"}>
                            {account.auto_upgrade_seats ? "Auto" : "Off"}
                          </Badge>
                        </button>
                      </td>
                      <td className="py-3">{account.reservation_count ?? 0}</td>
                      <td className="py-3">
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => toggleActive(account.id, account.is_active)}
                          >
                            {account.is_active ? "Disable" : "Enable"}
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => deleteAccount(account.id)}
                          >
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        </div>
                      </td>
                    </tr>
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
