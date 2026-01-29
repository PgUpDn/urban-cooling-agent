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