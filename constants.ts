import { SimulationMetric, WorkflowStep } from './types';

export const MOCK_ENV_METRICS: SimulationMetric[] = [
  {
    label: 'Wind Speed',
    value: '3.2',
    unit: 'm/s',
    source: 'NEA Weather',
    isLive: true,
    icon: 'air',
    color: 'text-blue-500'
  },
  {
    label: 'Solar Irradiance',
    value: '850',
    unit: 'W/m²',
    source: 'IWEC Database',
    isLive: false,
    icon: 'wb_sunny',
    color: 'text-orange-500'
  },
  {
    label: 'Relative Humidity',
    value: '78',
    unit: '%',
    source: 'NEA Weather',
    isLive: true,
    icon: 'water_drop',
    color: 'text-cyan-500'
  }
];

export const MOCK_MATERIAL_METRICS: SimulationMetric[] = [
  {
    label: 'Surface Albedo',
    value: '0.3',
    unit: '',
    source: 'LLM Suggestion',
    isAi: true,
    icon: 'texture',
    color: 'text-gray-500'
  }
];

export const WORKFLOW_STEPS_SETUP: WorkflowStep[] = [
  { id: '1', label: 'Intent Analysis', desc: 'Parsed query & objectives', status: 'completed' },
  { id: '2', label: 'Geometry Analysis', desc: 'STL parsed, bounds set', status: 'completed' },
  { id: '3', label: 'Solver Orchestration', desc: 'Configuring CFD parameters...', status: 'active' },
  { id: '4', label: 'Result Integration', desc: 'Heat maps & comfort index', status: 'pending' },
];

export const WORKFLOW_STEPS_RESULTS: WorkflowStep[] = [
  { id: '1', label: 'Intent Analysis', desc: 'Completed', status: 'completed' },
  { id: '2', label: 'Geometry Analysis', desc: 'Completed', status: 'completed' },
  { id: '3', label: 'Solver Orchestration', desc: 'Completed', status: 'completed' },
  { id: '4', label: 'Result Integration', desc: 'Active Stage', status: 'active' },
];

// URLs from the original HTML provided by user
export const IMG_USER_AVATAR = "https://lh3.googleusercontent.com/aida-public/AB6AXuBDu6EITmoWtr7hBaOqawoaVP6wTAGObEr0f834CHV0WrbEiw_4ua-wAPOOkFieFAPWzEurdYTCBeGK43R0eviZ7lKGCWlIvH28nErOQJMPS7PAt0-O3dgkhPtrlcU6c0j6nDhWG5j6F0W-9U3xe_jUKwW46wZ7SdOqlj0P7R6bPX_MU0dReii1LSW7-4QfxKeD671ljhcmRb8Vhr3bS8N4dWv4Xug1-kLX-rX7-Qsst1iMH5zeyPSZF9Y4EyD-XYL79Th6ZpGhdEQE";
export const IMG_AGENT_AVATAR = "https://lh3.googleusercontent.com/aida-public/AB6AXuB7MLSxM1oINlN3BL3d4Q75MuXZqW2oJ2r9A5WyoZt61aedEizaDFCzWb6mP9IgsWcX5hUrlfEHISeK2Byjq25Kv-KdXfnsWcX9KeJEAQMu7mJqDujxvCtZBtj_eRxM0gFNwdRo84tyUeV0fy1pVYYWEWjpim2oKp_uQHd91ewzEajKZfWSt9qFEondq9qSaa4SCUidvvMbU2oE7ybbeBgEK9h9jxBNmYRwNnK4T31uNUhWIhrOV5oHwJ6pKMofKjgnZkclZbvhxOh3";
export const IMG_URBAN_TEXTURE = "https://lh3.googleusercontent.com/aida-public/AB6AXuC--bIswdvb0bosFfCFpwH8ylyZL5nH6Wvvxc6VhuWliwCAtMolQ81ufoO3okAnnN8x42z9UlHDvA-PHfy3308GeS6_pR1x90REhcUhzGPsfuIc-2kz88zXEqCKzzVFedJkMWoEv7_oIphMbVTMVikTBgiDn-1UIGhbkXZDABLafmQ2McqfRK_ObmGro5Ee-FMv7MXbGCGl_2t9FAzgRHe5gt5GZZldcgtLQwhIs65qELXOXlW9NLhlEBEDaCSadGdD6rc4dULFYM1l";
export const IMG_HEATMAP_FULL = "https://lh3.googleusercontent.com/aida-public/AB6AXuAzcB1JitQC1QZCwdO8T_869ccoJWaT6CLEOKSYRQ8LlRe9KDpTiyylzbCGdHfgjNSPVs438EE5pIo41fbGlytdx3fFZd94G-4nW3gV65hBFdH-yP4JOYUBj6oCilklCIy2ZD9Fb6gFBh52Ampl0bChEsfo5jAD8WUH6uVEB9E4RKfNYuHAJb8FZMIlwF39BJGUb3JFt8BMoePqyK3eUyAofoDujiB_EX8iYBo0oC-T-5HoIAGyS6vfhvRZE2-d5eEKeUt-JYRn3cxW";
export const IMG_COMPARISON_BASELINE = "https://placeholder.pics/svg/600x800/EF4444/FFFFFF/Baseline%20Hotspot";
export const IMG_COMPARISON_SCENARIO = "https://placeholder.pics/svg/600x800/22C55E/FFFFFF/Scenario%20B%20Cooling";
