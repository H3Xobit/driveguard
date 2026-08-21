export type VehicleScore = {
  vehicle_id: string;
  temporal: number;
  zone: number;
  fused: number;
  baseline_rf: number;
  compounding: boolean;
  nearest_zone?: string | null;
  severity: string;
  behavior: string;
  alert?: string;
  alert_score?: number;
  source?: string;
  lat: number;
  lon: number;
  speed_kmh: number;
};

export type IncidentRow = {
  incident_id: string;
  vehicle_id: string;
  severity: string;
  fused_score: number;
  behavior: string;
  alert?: string;
  alert_score?: number;
  summary: string;
  recommended_action: string;
  citations: { section_id: string; title: string }[];
  lat: number;
  lon: number;
};

export const DEMO_VEHICLES: VehicleScore[] = [
  {
    vehicle_id: "V-1042",
    temporal: 0.84,
    zone: 0.64,
    fused: 0.91,
    baseline_rf: 0.79,
    compounding: true,
    nearest_zone: "HYD-CBD-01",
    severity: "fault",
    behavior: "harsh_braking",
    alert: "cas_hmw",
    alert_score: 2.4,
    source: "cas",
    lat: 17.386,
    lon: 78.487,
    speed_kmh: 28,
  },
  {
    vehicle_id: "V-2218",
    temporal: 0.22,
    zone: 0.12,
    fused: 0.19,
    baseline_rf: 0.18,
    compounding: false,
    nearest_zone: null,
    severity: "info",
    behavior: "calm",
    alert: "none",
    alert_score: 0,
    source: "cas",
    lat: 17.401,
    lon: 78.41,
    speed_kmh: 54,
  },
  {
    vehicle_id: "V-7730",
    temporal: 0.61,
    zone: 0.71,
    fused: 0.72,
    baseline_rf: 0.58,
    compounding: true,
    nearest_zone: "HYD-ORR-03",
    severity: "warn",
    behavior: "speeding",
    alert: "cas_fcw",
    alert_score: 5.6,
    source: "cas",
    lat: 17.4,
    lon: 78.355,
    speed_kmh: 96,
  },
];

export const DEMO_ZONES = [
  { zone_id: "HYD-NH44-12", lat: 17.312, lon: 78.474, historical_risk: 0.82, name: "NH44 merge" },
  { zone_id: "HYD-ORR-03", lat: 17.401, lon: 78.352, historical_risk: 0.71, name: "ORR west" },
  { zone_id: "HYD-CBD-01", lat: 17.385, lon: 78.486, historical_risk: 0.64, name: "Central arterial" },
];

export const DEMO_STATS = {
  alerts: { cas_hmw: 18, cas_fcw: 6, cas_ldw: 4 },
  weekday: { Friday: 28 },
};

export const DEMO_INCIDENTS: IncidentRow[] = [
  {
    incident_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1",
    vehicle_id: "V-1042",
    severity: "fault",
    fused_score: 0.91,
    behavior: "harsh_braking",
    alert: "cas_hmw",
    alert_score: 2.4,
    summary:
      "V-1042 cas_hmw (speed-band score 2.4, session risk 0.91) in mapped corridor HYD-CBD-01. headway warning (cas_hmw) with short following distance. Live kinematics and a historical hotspot fired together. Citations: GL-HMW-02, GL-ZONE-06.",
    recommended_action: "Increase following distance; review the last HMW cluster on this vehicle.",
    citations: [
      { section_id: "GL-HMW-02", title: "Headway warning (cas_hmw)" },
      { section_id: "GL-ZONE-06", title: "Historical hotspots" },
    ],
    lat: 17.386,
    lon: 78.487,
  },
];

export const DEMO_EVAL = {
  timestamp: "2026-08-21T08:00:00Z",
  n: 10,
  accuracy: 0.9,
  precision: 1.0,
  recall: 0.88,
  f1: 0.93,
  false_positive_rate: 0.0,
  narrative_faithfulness: 1.0,
  tp: 8,
  fp: 0,
  tn: 2,
  fn: 0,
  confusion: { tp: 8, fp: 0, tn: 2, fn: 0 },
  snapshot_baselines: [
    { model: "random_forest", accuracy: 0.96, precision: 0.95, recall: 0.97, f1: 0.96 },
    { model: "linear_svm", accuracy: 0.92, precision: 0.91, recall: 0.94, f1: 0.92 },
    { model: "logistic_regression", accuracy: 0.9, precision: 0.89, recall: 0.93, f1: 0.91 },
    { model: "decision_tree", accuracy: 0.88, precision: 0.86, recall: 0.9, f1: 0.88 },
  ],
};
