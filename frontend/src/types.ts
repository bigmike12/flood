export interface Region { id: string; name: string; lat: number; lng: number; }

export interface Kpis {
  mean_response_time: number;
  coverage_pct: number;
  casualties: number;
  rescued: number;
  total_requests: number;
  utilisation_pct: number;
  unmet: number;
}

export interface Snapshot {
  step: number;
  minute: number;
  flood: { lat: number; lng: number; depth: number }[];
  people: { lat: number; lng: number; state: string }[];
  units: { lat: number; lng: number; kind: string; state: string }[];
  hospitals: { lat: number; lng: number; free: number; beds: number }[];
  roads_closed_pct: number;
  flooded_pct: number;
  kpis: Kpis;
  finished: boolean;
}

export interface ScenarioConfig {
  region: string;
  flood_intensity: number;
  rainfall_mm: number;
  strategy: string;
  seed: number;
  n_responder_units: number;
}

export interface StrategyResult {
  label: string;
  mean_response_time: number;
  coverage_pct: number;
  casualties: number;
  utilisation_pct: number;
  casualties_averted: number;
}

export interface SavedScenario {
  id: string; name: string; region: string; flood_intensity: number;
  rainfall_mm: number; n_responder_units: number; n_ambulances: number;
  runs: number; created_at: string;
}

export interface Auth { token: string; username: string; role: string; }
