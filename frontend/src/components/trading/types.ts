/** Formes des réponses de l'API : montants en texte exact, jamais recalculés ici. */

export type AssetStatus = "live" | "closed" | "suspended" | "stale" | "unavailable";

export type Tick = {
  symbol: string;
  quote: number;
  bid?: number | null;
  ask?: number | null;
  epoch: number;
  received_at: number;
};

export type Asset = {
  symbol: string;
  name: string;
  market: string;
  submarket: string | null;
  pip_size: number;
  /** Deriv propose des multiplicateurs sur cet actif ; `null` : pas encore lu. */
  multipliers: boolean | null;
  status: AssetStatus;
  tick: Tick | null;
};

export type Candle = { epoch: number; open: number; high: number; low: number; close: number };

export type BotState =
  | "starting"
  | "analyzing"
  | "position_open"
  | "paused"
  | "target_reached"
  | "limit_reached"
  | "error"
  | "stopping"
  | "stopped";

export type BotSession = {
  id: string;
  symbol: string;
  state: BotState;
  account_kind: string;
  command: string | null;
  stop_reason: string | null;
  error_code: string | null;
  start_balance: string | null;
  paused_until: string | null;
  started_at: string;
  ended_at: string | null;
  session_net: string;
  consecutive_losses: number;
  engine_online: boolean;
  deriv_connected: boolean;
};

export type Protection = {
  activation_level: string;
  ratchet_active: boolean;
  locked_level: string | null;
  floor_active: boolean;
  worst_case_loss: string;
};

export type Position = {
  id: string;
  symbol: string;
  direction: "up" | "down";
  multiplier: number;
  status: "opening" | "unknown" | "open" | "closed";
  stake: string;
  stop_loss: string;
  buy_price: string | null;
  commission: string | null;
  current_stop: string | null;
  current_profit: string | null;
  peak_profit: string | null;
  sell_price: string | null;
  net_result: string | null;
  entry_spot: string | null;
  stop_spot: string | null;
  close_requested: boolean;
  close_reason: string | null;
  opened_at: string | null;
  closed_at: string | null;
  protection: Protection | null;
  account_kind?: string;
};

export type RiskUsage = {
  session_net: string;
  session_loss_limit: string;
  session_target: string;
  day_net: string;
  day_loss_limit: string;
  day_target: string;
  exposure: string;
  exposure_limit: string;
  open_positions: number;
  max_positions: number;
  consecutive_losses: number;
  max_consecutive_losses: number;
  stop_loss: string;
  worst_case_loss: string;
  slippage_margin: string;
};

export type BotResponse = {
  session: BotSession | null;
  last_session: BotSession | null;
  open_positions: Position[];
  risk: RiskUsage | null;
  server_time: string;
};

export type Summary = {
  day_net: string;
  total_net: string;
  trades: number;
  wins: number;
  losses: number;
  win_rate: number | null;
  average_gain: string | null;
  average_loss: string | null;
  best: string | null;
  worst: string | null;
  curve: Array<{ at: string; net: string }>;
};

export type Decision = {
  id: number;
  at: string;
  kind: string;
  code: string | null;
  data: Record<string, unknown>;
  position: string | null;
};

export type SettingsResponse = {
  settings: Record<string, string | string[]>;
  ranges: Record<string, { min: string; max: string }>;
  provisional: string[];
};

export type DerivAccountView = {
  account_id: string;
  kind: "demo" | "real";
  currency: string;
  balance: string;
  status: string;
  selectable: boolean;
};

export type DerivConnection =
  | { connected: false }
  | {
      connected: true;
      auth_method: string;
      token_valid: boolean;
      token_expires_at: string | null;
      selected: { account_id: string | null; kind: string | null; currency: string | null };
      accounts: DerivAccountView[];
    };
