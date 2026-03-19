import React, { useState, useEffect, useRef, useCallback } from 'react';
import type { ViewState, Message, SimulationResults, WorkflowStep, LiveParams } from './types';
import { IMG_USER_AVATAR } from './constants';
import {
  checkBackendHealth, startSimulation, getSimulationMessages,
  getSimulationResults, getSimulationParams, type ProgressMessage,
} from './services/agentService';
import { WorkflowSidebar } from './components/WorkflowSidebar';
import { ChatInterface } from './components/ChatInterface';
import { ParamSidebar } from './components/ParamSidebar';
import { ResultsDashboard } from './components/ResultsDashboard';
import { ComparisonView } from './components/ComparisonView';

function ts() { return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }
let mc = 0;
function nid() { return `m-${Date.now()}-${++mc}`; }

const STAGE_ORDER = ['intent_analysis', 'geometry_analysis', 'solver_running', 'result_integration', 'complete'];
const STAGE_LABELS = ['Intent Analysis', 'Geometry Analysis', 'Solver Orchestration', 'Result Integration'];
const STAGE_DESCS = ['Parse query & determine solvers', 'Analyze STL geometry', 'Run CFD / solar solvers', 'Generate narrative report'];

function buildSteps(stage: string): WorkflowStep[] {
  const idx = STAGE_ORDER.indexOf(stage);
  return STAGE_LABELS.map((label, i) => ({
    id: String(i + 1), label, desc: STAGE_DESCS[i],
    status: i < idx ? 'completed' as const : i === idx ? 'active' as const : 'pending' as const,
  }));
}
const IDLE = STAGE_LABELS.map((label, i) => ({ id: String(i + 1), label, desc: STAGE_DESCS[i], status: 'pending' as const }));

const App: React.FC = () => {
  const [view, setView] = useState<ViewState>('setup');
  const [messages, setMessages] = useState<Message[]>([]);
  const [backendReady, setBackendReady] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [simResults, setSimResults] = useState<SimulationResults | null>(null);
  const [steps, setSteps] = useState<WorkflowStep[]>(IDLE);
  const [simRunning, setSimRunning] = useState(false);
  const [liveParams, setLiveParams] = useState<LiveParams>({});
  const [chatLoading, setChatLoading] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const miRef = useRef(0);

  useEffect(() => {
    let c = false;
    (async () => {
      const ok = await checkBackendHealth();
      if (!c) {
        setBackendReady(ok);
        setMessages([{
          id: nid(), sender: 'agent', timestamp: ts(), type: 'text',
          text: ok
            ? 'Urban Cooling Agent ready. I can run CFD wind simulations, solar irradiance analysis, and thermal comfort (PET/MRT) assessments for urban districts.\n\nExample prompt:\n\u2022 "Run a fully coupled CFD + solar audit for the inter-monsoon period, emphasizing district comfort and energy demand"'
            : 'Backend not reachable. Start the server with:\ncd /home/ubuntu/urban_agent && source .venv/bin/activate\nuvicorn api_server:app --host 0.0.0.0 --port 8000',
        }]);
      }
    })();
    return () => { c = true; };
  }, []);

  const stopPoll = useCallback(() => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } }, []);
  const startPoll = useCallback((sid: string) => {
    stopPoll(); miRef.current = 0;
    pollRef.current = setInterval(async () => {
      try {
        const { messages: nm, total, status } = await getSimulationMessages(sid, miRef.current);
        if (nm.length > 0) {
          miRef.current = total;
          const msgs: Message[] = nm.filter((m: ProgressMessage) => m.type !== 'agent_report').map((m: ProgressMessage) => ({
            id: nid(), sender: 'agent' as const, text: m.text,
            timestamp: new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            type: m.type === 'status' || m.type === 'info' ? 'status' as const : 'text' as const,
          }));
          if (msgs.length) setMessages(p => [...p, ...msgs]);
        }
        try {
          const { getSimulationStatus } = await import('./services/agentService');
          const sr = await getSimulationStatus(sid).then(d => ({ ok: true, json: () => d })).catch(() => ({ ok: false, json: () => ({}) }));
          if (sr.ok) { const sd = await sr.json(); if (sd.stage) setSteps(buildSteps(sd.stage)); }
          const pd = await getSimulationParams(sid);
          if (pd.params) setLiveParams(pd.params);
        } catch {}
        if (status === 'completed') {
          stopPoll();
          const res = await getSimulationResults(sid);
          if (res.results) {
            setSimResults(res.results);
            const rpt = res.results.response;
            if (rpt) {
              const preview = rpt.length > 800 ? rpt.slice(0, 800) + '\u2026' : rpt;
              setMessages(p => [...p, { id: nid(), sender: 'agent', text: `**Analysis Complete**\n\n${preview}\n\n\u2192 Switch to Dashboard to see full results.`, timestamp: ts(), type: 'text' }]);
            }
            setSteps(buildSteps('complete'));
          }
          setSimRunning(false);
        } else if (status === 'error') { stopPoll(); setSimRunning(false); }
      } catch {}
    }, 2000);
  }, [stopPoll]);
  useEffect(() => stopPoll, [stopPoll]);

  const handleSend = useCallback(async (text: string) => {
    if (chatLoading || simRunning) return;
    setMessages(p => [...p, { id: nid(), sender: 'user', text, timestamp: ts(), type: 'text' }]);
    if (!backendReady) { setMessages(p => [...p, { id: nid(), sender: 'agent', text: 'Backend not connected.', timestamp: ts(), type: 'text' }]); return; }
    setChatLoading(true);
    try {
      const { sendChatMessage } = await import('./services/agentService');
      const hist = messages.filter(m => m.text && m.type === 'text').slice(-20).map(m => ({ role: m.sender === 'user' ? 'user' as const : 'agent' as const, content: m.text! }));
      const result = await sendChatMessage(text, hist, sessionId);
      if (result.action === 'analyze') {
        setChatLoading(false);
        const q = result.query || text;
        setSimRunning(true); setSimResults(null); setLiveParams({}); setSteps(buildSteps('intent_analysis'));
        setMessages(p => [...p, { id: nid(), sender: 'agent', text: `Starting analysis pipeline\u2026`, timestamp: ts(), type: 'status' }]);
        try {
          const { sessionId: sid } = await startSimulation({ query: q });
          setSessionId(sid); startPoll(sid);
        } catch (e: any) { setSimRunning(false); setSteps(IDLE); setMessages(p => [...p, { id: nid(), sender: 'agent', text: `Failed: ${e?.message}`, timestamp: ts(), type: 'text' }]); }
      } else {
        setMessages(p => [...p, { id: nid(), sender: 'agent', text: result.response || '', timestamp: ts(), type: 'text' }]);
      }
    } catch { setMessages(p => [...p, { id: nid(), sender: 'agent', text: 'Failed to get response.', timestamp: ts(), type: 'text' }]); }
    finally { setChatLoading(false); }
  }, [backendReady, chatLoading, simRunning, messages, sessionId, startPoll]);

  const handleNew = useCallback(() => { setSimResults(null); setSessionId(null); setLiveParams({}); setSteps(IDLE); setMessages(p => [...p, { id: nid(), sender: 'agent', text: 'Ready for a new analysis.', timestamp: ts(), type: 'status' }]); }, []);

  return (
    <div className="flex flex-col h-full bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-white">
      <header className="h-16 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between px-6 shadow-sm z-30 shrink-0">
        <div className="flex items-center gap-3 cursor-pointer" onClick={() => setView('setup')}>
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center text-white shadow-lg shadow-primary/30">
            <span className="material-icons-outlined text-xl">architecture</span>
          </div>
          <h1 className="font-semibold text-lg tracking-tight font-display">Urban Cooling Agent <span className="text-slate-400 font-normal">| {view === 'setup' ? 'Chat' : view === 'results' ? 'Dashboard' : 'Comparison'}</span></h1>
        </div>
        <div className="hidden md:flex gap-8 text-sm font-medium text-slate-500">
          <button onClick={() => setView('setup')} className={`hover:text-primary transition-colors ${view === 'setup' ? 'text-primary' : ''}`}>Chat</button>
          <button onClick={() => setView('results')} className={`hover:text-primary transition-colors ${view === 'results' ? 'text-primary' : ''}`} disabled={!simResults}>Dashboard</button>
          <button onClick={() => setView('comparison')} className={`hover:text-primary transition-colors ${view === 'comparison' ? 'text-primary' : ''}`}>Comparison</button>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-sm text-slate-500 flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${backendReady ? 'bg-green-500 animate-pulse' : 'bg-amber-400'}`}></span>
            <span className="hidden sm:inline">{backendReady ? 'Backend Connected' : 'Disconnected'}</span>
          </div>
          {simRunning && <div className="text-sm text-primary flex items-center gap-2 font-medium"><span className="material-icons-outlined text-sm animate-spin">autorenew</span>Running</div>}
          <div className="w-9 h-9 rounded-full bg-slate-200 overflow-hidden border border-slate-300"><img src={IMG_USER_AVATAR} alt="User" className="w-full h-full object-cover" /></div>
        </div>
      </header>
      <main className="flex-1 flex overflow-hidden relative">
        {view === 'setup' && (<>
          <WorkflowSidebar steps={steps} title="Execution Plan" />
          <ChatInterface messages={messages} onSend={handleSend} simRunning={simRunning} chatLoading={chatLoading} simCompleted={!!simResults} backendReady={backendReady} onViewDashboard={() => setView('results')} onNewAnalysis={handleNew} />
          <ParamSidebar simulationResults={simResults} liveParams={liveParams} simRunning={simRunning} />
        </>)}
        {view === 'results' && <ResultsDashboard onCompare={() => setView('comparison')} simulationResults={simResults} />}
        {view === 'comparison' && <ComparisonView />}
      </main>
    </div>
  );
};
export default App;
