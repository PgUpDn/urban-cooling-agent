import type { BackendStatus, LiveParams, SimulationResults } from '../types';

const BACKEND_API_URL: string = process.env.BACKEND_API_URL || '';
function api(): string {
  if (BACKEND_API_URL) return BACKEND_API_URL;
  // Detect if running under /cooling/ path (production nginx)
  if (typeof window !== 'undefined' && window.location.pathname.startsWith('/cooling')) {
    return '/cooling';
  }
  return '';
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${api()}/api/health`);
    if (!res.ok) return false;
    const data = await res.json();
    return data.status === 'ok' && data.agent_ready === true;
  } catch { return false; }
}

export interface ChatHistoryEntry { role: 'user' | 'agent'; content: string; }
export interface ChatResponse { action: 'chat' | 'analyze'; response?: string; query?: string; }

export async function sendChatMessage(
  message: string, history: ChatHistoryEntry[] = [], sessionId?: string | null,
): Promise<ChatResponse> {
  const res = await fetch(`${api()}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history, session_id: sessionId ?? undefined }),
  });
  if (!res.ok) { const text = await res.text(); throw new Error(`Chat failed (${res.status}): ${text}`); }
  return res.json();
}

export interface StartSimulationParams { query: string; stl_directory?: string; parameters?: Record<string, any>; }

export async function startSimulation(params: StartSimulationParams): Promise<{ sessionId: string; message: string }> {
  const res = await fetch(`${api()}/api/simulation/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(params) });
  if (!res.ok) throw new Error(`Start simulation failed: ${res.status}`);
  const data = await res.json();
  return { sessionId: data.sessionId, message: data.message };
}

export async function getSimulationStatus(sessionId: string): Promise<BackendStatus> {
  const res = await fetch(`${api()}/api/simulation/${sessionId}/status`);
  if (!res.ok) throw new Error(`Status fetch failed: ${res.status}`);
  return res.json();
}

export interface ProgressMessage { type: 'status' | 'info' | 'warning' | 'error' | 'agent_report'; text: string; timestamp: string; }

export async function getSimulationMessages(sessionId: string, after: number = 0): Promise<{ messages: ProgressMessage[]; total: number; status: string }> {
  const res = await fetch(`${api()}/api/simulation/${sessionId}/messages?after=${after}`);
  if (!res.ok) throw new Error(`Messages fetch failed: ${res.status}`);
  return res.json();
}

export async function getSimulationParams(sessionId: string): Promise<{ stage: string; status: string; params: LiveParams }> {
  const res = await fetch(`${api()}/api/simulation/${sessionId}/params`);
  if (!res.ok) throw new Error(`Params fetch failed: ${res.status}`);
  return res.json();
}

export async function getSimulationResults(sessionId: string): Promise<{ status: string; results?: SimulationResults; message?: string }> {
  const res = await fetch(`${api()}/api/simulation/${sessionId}/results`);
  if (!res.ok) throw new Error(`Results fetch failed: ${res.status}`);
  return res.json();
}

export function artifactUrl(relativePath: string): string { return `${api()}${relativePath}`; }

export async function listStlDirectories(): Promise<{ name: string; path: string }[]> {
  try { const res = await fetch(`${api()}/api/stl-directories`); if (!res.ok) return []; const data = await res.json(); return data.directories ?? []; } catch { return []; }
}
