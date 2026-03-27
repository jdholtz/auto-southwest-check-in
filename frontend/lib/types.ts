export interface Account {
  id: string;
  username: string;
  password: string;
  is_active: number;
  is_alist: number;
  auto_upgrade_seats: number;
  retrieval_interval: number;
  created_at: string;
  updated_at: string;
  reservation_count?: number;
}

export interface Reservation {
  id: string;
  account_id: string | null;
  confirmation_number: string;
  first_name: string;
  last_name: string;
  is_active: number;
  created_at: string;
  updated_at: string;
  flights?: Flight[];
}

export interface Flight {
  id: string;
  reservation_id: string;
  flight_number: string;
  departure_airport: string;
  destination_airport: string;
  departure_time: string;
  is_international: number;
  checkin_status: "pending" | "scheduled" | "checking_in" | "success" | "failed";
  checkin_result: string | null;
  checkin_attempted_at: string | null;
  created_at: string;
  // Joined fields
  confirmation_number?: string;
  first_name?: string;
  last_name?: string;
}

export interface NotificationConfig {
  id: string;
  service_url: string;
  notification_level: number;
  is_active: number;
}

export interface WorkerLog {
  id: number;
  flight_id: string | null;
  level: string;
  message: string;
  created_at: string;
}

export interface DashboardStats {
  active_accounts: number;
  total_reservations: number;
  upcoming_checkins: number;
  successful_checkins: number;
  failed_checkins: number;
}
