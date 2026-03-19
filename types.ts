export type ViewState = 'setup' | 'results' | 'comparison';

export interface Message {
  id: string;
  sender: 'user' | 'agent';
  text?: string;
  timestamp: string;
  type: 'text' | 'form' | 'status';
  formData?: {
    type: 'resolution';
    options: Array<{
      id: string;
      label: string;
      time: string;
      desc: string;
    }>;
  };
}

export interface SimulationMetric {
  label: string;
  value: string;
  unit?: string;
  source: string;
  isLive?: boolean;
  isAi?: boolean;
  icon: string;
  color: string;
}

export interface WorkflowStep {
  id: string;
  label: string;
  desc: string;
  status: 'completed' | 'active' | 'pending';
}

export interface BackendStatus {
  status: 'queued' | 'started' | 'running' | 'completed' | 'error';
  sessionId: string;
  stage?: string;
  progress?: number;
  message?: string;
}

export interface PETTimeSummary {
  time_token: string;
  max_value: number;
  location?: number[];
  building_id?: string;
}

export interface GeometryInfo {
  statistics: Record<string, any>;
  footprints: Array<Record<string, any>>;
  visualizations: Array<{ label: string; url: string }>;
}

export interface FileRef {
  solver?: string;
  url: string;
  filename?: string;
  label?: string;
}

export interface LiveParams {
  required_solvers?: string[];
  config_parameters?: Record<string, any>;
  solver_parameters?: Record<string, any>;
  external_parameters?: Record<string, any>;
  weather_snapshot?: Record<string, any>;
  weather?: {
    temperature_c?: number;
    relative_humidity_pct?: number;
    wind_speed_ms?: number;
    wind_direction_deg?: number;
  };
  resolved_time?: string;
  building_count?: number;
  geometry_statistics?: Record<string, any>;
  building_envelopes?: Array<Record<string, any>>;
  cfd_success?: boolean;
  solar_success?: boolean;
  cfd_parameters?: Record<string, any>;
  cfd_metrics?: Record<string, any>;
  solar_metrics?: Record<string, any>;
  cfd_error?: string;
  solar_error?: string;
  pet_time_summary?: PETTimeSummary[];
  mrt_time_summary?: PETTimeSummary[];
  pet_time_buckets?: Record<string, any>;
  mrt_time_buckets?: Record<string, any>;
}

export interface SimulationResults {
  success: boolean;
  response: string;
  building_analysis: string;
  metrics: Record<string, any>;
  pet_time_summary: PETTimeSummary[];
  mrt_time_summary: PETTimeSummary[];
  pet_time_buckets: Record<string, any>;
  mrt_time_buckets: Record<string, any>;
  cfd_parameters: Record<string, any>;
  geometry: GeometryInfo;
  visualization_files: FileRef[];
  screenshots: FileRef[];
  artifact_files: FileRef[];
  csv_files: FileRef[];
  output_directory: string;
}
