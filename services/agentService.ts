/**
 * Urban Cooling Agent Backend Service
 * 
 * This service connects to your deployed backend agent.
 * Update BACKEND_API_URL in your .env.local file with your deployed backend URL.
 */

// Backend API base URL - configured via environment variable
const BACKEND_API_URL = process.env.BACKEND_API_URL || '';

export interface SimulationRequest {
  query: string;
  parameters?: {
    resolution?: 'high' | 'standard';
    windSpeed?: number;
    solarIrradiance?: number;
    humidity?: number;
    albedo?: number;
  };
  geometry?: {
    stlFile?: string;
    bounds?: {
      minX: number;
      maxX: number;
      minY: number;
      maxY: number;
    };
  };
}

export interface SimulationResponse {
  status: 'success' | 'error' | 'pending';
  sessionId: string;
  message: string;
  results?: {
    meanPET: number;
    maxPET: number;
    windSpeed: number;
    heatmapUrl?: string;
    recommendations?: string[];
  };
  progress?: number;
}

export interface AgentMessage {
  role: 'user' | 'agent';
  content: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

/**
 * Check if backend is configured and available
 */
export const isBackendConfigured = (): boolean => {
  return !!BACKEND_API_URL && BACKEND_API_URL.length > 0;
};

/**
 * Health check for the backend service
 */
export const checkBackendHealth = async (): Promise<boolean> => {
  if (!isBackendConfigured()) {
    console.warn('Backend API URL not configured. Running in demo mode.');
    return false;
  }

  try {
    const response = await fetch(`${BACKEND_API_URL}/health`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.ok;
  } catch (error) {
    console.error('Backend health check failed:', error);
    return false;
  }
};

/**
 * Send a message to the Urban Cooling Agent
 */
export const sendAgentMessage = async (
  message: string,
  conversationHistory: AgentMessage[] = []
): Promise<AgentMessage> => {
  if (!isBackendConfigured()) {
    // Demo mode fallback
    return {
      role: 'agent',
      content: `[Demo Mode] I received your message: "${message}". To enable full agent functionality, please deploy your backend and configure BACKEND_API_URL.`,
      timestamp: new Date().toISOString(),
    };
  }

  try {
    const response = await fetch(`${BACKEND_API_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message,
        history: conversationHistory,
      }),
    });

    if (!response.ok) {
      throw new Error(`Backend responded with status: ${response.status}`);
    }

    const data = await response.json();
    return {
      role: 'agent',
      content: data.response || data.message,
      timestamp: new Date().toISOString(),
      metadata: data.metadata,
    };
  } catch (error) {
    console.error('Error sending message to agent:', error);
    return {
      role: 'agent',
      content: 'Sorry, I encountered an error connecting to the backend. Please check if the server is running.',
      timestamp: new Date().toISOString(),
    };
  }
};

/**
 * Start a new simulation
 */
export const startSimulation = async (
  request: SimulationRequest
): Promise<SimulationResponse> => {
  if (!isBackendConfigured()) {
    // Demo mode fallback
    return {
      status: 'pending',
      sessionId: `demo-${Date.now()}`,
      message: '[Demo Mode] Simulation would start here. Configure BACKEND_API_URL to run actual simulations.',
      progress: 0,
    };
  }

  try {
    const response = await fetch(`${BACKEND_API_URL}/simulation/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`Failed to start simulation: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error starting simulation:', error);
    return {
      status: 'error',
      sessionId: '',
      message: 'Failed to start simulation. Please check your backend connection.',
    };
  }
};

/**
 * Get simulation status/progress
 */
export const getSimulationStatus = async (
  sessionId: string
): Promise<SimulationResponse> => {
  if (!isBackendConfigured()) {
    return {
      status: 'pending',
      sessionId,
      message: '[Demo Mode] No backend configured.',
      progress: 0,
    };
  }

  try {
    const response = await fetch(`${BACKEND_API_URL}/simulation/${sessionId}/status`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to get status: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error getting simulation status:', error);
    return {
      status: 'error',
      sessionId,
      message: 'Failed to retrieve simulation status.',
    };
  }
};

/**
 * Get simulation results
 */
export const getSimulationResults = async (
  sessionId: string
): Promise<SimulationResponse> => {
  if (!isBackendConfigured()) {
    // Return mock results for demo
    return {
      status: 'success',
      sessionId,
      message: '[Demo Mode] Showing mock results.',
      results: {
        meanPET: 35.2,
        maxPET: 38.5,
        windSpeed: 1.2,
        recommendations: [
          'Increase canopy cover by 20% in the north-east quadrant',
          'Consider adding water features for evaporative cooling',
          'Install high-albedo materials on exposed surfaces',
        ],
      },
    };
  }

  try {
    const response = await fetch(`${BACKEND_API_URL}/simulation/${sessionId}/results`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to get results: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error getting simulation results:', error);
    return {
      status: 'error',
      sessionId,
      message: 'Failed to retrieve simulation results.',
    };
  }
};

/**
 * Export simulation report
 */
export const exportReport = async (
  sessionId: string,
  format: 'pdf' | 'csv' | 'vtk' = 'pdf'
): Promise<Blob | null> => {
  if (!isBackendConfigured()) {
    console.warn('Backend not configured. Cannot export report.');
    return null;
  }

  try {
    const response = await fetch(`${BACKEND_API_URL}/simulation/${sessionId}/export?format=${format}`, {
      method: 'GET',
    });

    if (!response.ok) {
      throw new Error(`Failed to export report: ${response.status}`);
    }

    return await response.blob();
  } catch (error) {
    console.error('Error exporting report:', error);
    return null;
  }
};
