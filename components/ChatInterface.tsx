import React, { useState, useRef, useEffect } from 'react';
import type { Message } from '../types';
import { IMG_AGENT_AVATAR, IMG_USER_AVATAR } from '../constants';

interface ChatInterfaceProps {
  messages: Message[];
  onSend: (text: string) => void;
  simRunning: boolean;
  chatLoading: boolean;
  simCompleted: boolean;
  backendReady: boolean;
  onViewDashboard: () => void;
  onNewAnalysis: () => void;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ messages, onSend, simRunning, chatLoading, simCompleted, backendReady, onViewDashboard, onNewAnalysis }) => {
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);
  const busy = simRunning || chatLoading;
  const send = () => { const t = input.trim(); if (!t) return; setInput(''); onSend(t); };
  const kd = (e: React.KeyboardEvent) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } };

  return (
    <section className="flex-1 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col overflow-hidden relative mx-4 mb-4">
      <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center bg-slate-50/50 dark:bg-slate-900/50 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-slate-600 dark:text-slate-300">Agent Chat</span>
          {backendReady ? <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-green-100 text-green-700 border border-green-200">Connected</span> : <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-red-100 text-red-700 border border-red-200">Offline</span>}
          {simRunning && <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-blue-100 text-blue-700 border border-blue-200 flex items-center gap-1"><span className="material-icons-outlined text-xs animate-spin">autorenew</span>Simulating</span>}
        </div>
        <div className="flex gap-2">
          {simCompleted && (<>
            <button onClick={onViewDashboard} className="text-xs font-bold text-primary bg-blue-50 px-3 py-1.5 rounded-lg hover:bg-blue-100 transition-colors flex items-center gap-1"><span className="material-icons-outlined text-sm">dashboard</span>View Dashboard</button>
            <button onClick={onNewAnalysis} className="text-xs font-bold text-slate-600 bg-slate-100 px-3 py-1.5 rounded-lg hover:bg-slate-200 transition-colors flex items-center gap-1"><span className="material-icons-outlined text-sm">add</span>New Analysis</button>
          </>)}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.map(msg => (
          <div key={msg.id}>
            {msg.type === 'status' && <div className="flex justify-center my-2"><div className="px-3 py-1 bg-slate-100 dark:bg-slate-800 rounded-full border border-slate-200 dark:border-slate-700 text-xs text-slate-500 flex items-center gap-1.5 max-w-[80%]"><span className="material-icons-outlined text-[14px]">cloud_sync</span><span className="truncate">{msg.text}</span></div></div>}
            {msg.type === 'text' && (
              <div className={`flex gap-3 ${msg.sender === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className="w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden shrink-0 border border-slate-300"><img src={msg.sender === 'agent' ? IMG_AGENT_AVATAR : IMG_USER_AVATAR} alt={msg.sender} className="w-full h-full object-cover" /></div>
                <div className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'} max-w-[80%]`}>
                  <div className={`p-4 rounded-2xl shadow-sm text-sm leading-relaxed whitespace-pre-wrap ${msg.sender === 'user' ? 'bg-primary text-white rounded-tr-sm' : 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 rounded-tl-sm'}`}>{msg.text}</div>
                  <span className="text-[10px] text-slate-400 mt-1 mx-1">{msg.timestamp}</span>
                </div>
              </div>
            )}
          </div>
        ))}
        {busy && <div className="flex gap-3"><div className="w-8 h-8 rounded-full bg-slate-200 border border-slate-300 flex items-center justify-center"><span className="material-icons-outlined text-sm">smart_toy</span></div><div className="bg-white border border-slate-200 p-3 rounded-2xl rounded-tl-sm shadow-sm"><div className="flex gap-1"><span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></span><span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{animationDelay:'75ms'}}></span><span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{animationDelay:'150ms'}}></span></div></div></div>}
        <div ref={bottomRef} />
      </div>
      <div className="p-4 bg-white dark:bg-slate-800 border-t border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-2">
          <input type="text" value={input} onChange={e => setInput(e.target.value)} onKeyDown={kd} disabled={busy} placeholder={simRunning ? 'Analysis in progress\u2026' : 'Ask a question or describe an analysis to run\u2026'} className="flex-1 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg px-4 py-3 text-sm focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all shadow-sm disabled:opacity-50" />
          <button onClick={send} disabled={busy || !input.trim()} className="p-2.5 bg-primary text-white rounded-lg hover:bg-primary-hover transition-colors shadow-sm disabled:opacity-40 shrink-0"><span className="material-icons-outlined text-lg">send</span></button>
        </div>
      </div>
    </section>
  );
};
