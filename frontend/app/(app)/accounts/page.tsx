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
import { Plus, Trash2, Pencil } from "lucide-react";
import type { Account } from "@/lib/types";

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [open, setOpen] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isAlist, setIsAlist] = useState(false);
  const [autoUpgrade, setAutoUpgrade] = useState(false);
  const [loading, setLoading] = useState(false);
  const [editingName, setEditingName] = useState<string | null>(null);
  const [editNameValue, setEditNameValue] = useState("");

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
      body: JSON.stringify({
        display_name: displayName,
        username,
        password,
        is_alist: isAlist,
        auto_upgrade_seats: autoUpgrade,
      }),
    });
    setDisplayName("");
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

  async function saveName(id: string) {
    await fetch(`/api/accounts/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_name: editNameValue }),
    });
    setEditingName(null);
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
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Display Name
                </label>
                <Input
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="e.g. Mom, Dad, Work Account"
                />
                <p className="text-xs text-gray-400 mt-1">
                  A friendly name to identify this account
                </p>
              </div>
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
                  <div className="text-xs text-gray-400">
                    Enable for A-List or A-List Preferred members
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setIsAlist(!isAlist)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${isAlist ? "bg-blue-600" : "bg-gray-200"}`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${isAlist ? "translate-x-6" : "translate-x-1"}`}
                  />
                </button>
              </div>
              <div className="flex items-center justify-between rounded-lg border border-gray-200 p-3">
                <div>
                  <div className="text-sm font-medium">Auto Seat Upgrade</div>
                  <div className="text-xs text-gray-400">
                    Attempt seat upgrade 48h before departure
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setAutoUpgrade(!autoUpgrade)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${autoUpgrade ? "bg-blue-600" : "bg-gray-200"}`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${autoUpgrade ? "translate-x-6" : "translate-x-1"}`}
                  />
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
            <div className="space-y-3">
              {accounts.map((account) => (
                <div
                  key={account.id}
                  className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between rounded-lg border border-gray-200 p-4"
                >
                  <div className="flex flex-wrap items-center gap-3 md:gap-4">
                    <div>
                      {editingName === account.id ? (
                        <div className="flex items-center gap-2">
                          <Input
                            value={editNameValue}
                            onChange={(e) => setEditNameValue(e.target.value)}
                            className="h-8 w-48"
                            placeholder="Display name"
                            autoFocus
                            onKeyDown={(e) => {
                              if (e.key === "Enter") saveName(account.id);
                              if (e.key === "Escape") setEditingName(null);
                            }}
                          />
                          <Button size="sm" onClick={() => saveName(account.id)}>
                            Save
                          </Button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-gray-900">
                            {account.display_name || account.username}
                          </span>
                          <button
                            onClick={() => {
                              setEditingName(account.id);
                              setEditNameValue(account.display_name || "");
                            }}
                            className="text-gray-400 hover:text-gray-600"
                          >
                            <Pencil className="h-3 w-3" />
                          </button>
                        </div>
                      )}
                      {account.display_name && (
                        <div className="text-xs text-gray-400">{account.username}</div>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={account.is_active ? "active" : "inactive"}>
                        {account.is_active ? "Active" : "Inactive"}
                      </Badge>
                      <button
                        onClick={() =>
                          toggleField(account.id, "is_alist", account.is_alist)
                        }
                      >
                        <Badge variant={account.is_alist ? "success" : "default"}>
                          {account.is_alist ? "A-List" : "Standard"}
                        </Badge>
                      </button>
                      <button
                        onClick={() =>
                          toggleField(
                            account.id,
                            "auto_upgrade_seats",
                            account.auto_upgrade_seats
                          )
                        }
                      >
                        <Badge
                          variant={account.auto_upgrade_seats ? "scheduled" : "default"}
                        >
                          {account.auto_upgrade_seats ? "Auto Upgrade" : "No Upgrade"}
                        </Badge>
                      </button>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-gray-500">
                      {account.reservation_count ?? 0} reservation
                      {(account.reservation_count ?? 0) !== 1 ? "s" : ""}
                    </span>
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
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
