import React, { useState, useEffect } from 'react';
import { ViewState, Message } from './types';
import { WORKFLOW_STEPS_SETUP, IMG_USER_AVATAR } from './constants';
import { initializeGemini } from './services/geminiService';

// Components
import { WorkflowSidebar } from './components/WorkflowSidebar';
import { ChatInterface } from './components/ChatInterface';
import { ParamSidebar } from './components/ParamSidebar';
import { ResultsDashboard } from './components/ResultsDashboard';
import { ComparisonView } from './components/ComparisonView';

const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<ViewState>('setup');
  
  // Chat State
  const [messages, setMessages] = useState<Message[]>([
    {
        id: '1',
        sender: 'user',
        text: 'Run a fully coupled CFD + solar audit representative of the late March—May inter-monsoon window, emphasizing district comfort and energy demand.',
        timestamp: '14:58',
        type: 'text'
    },
    {
        id: '2',
        sender: 'agent',
        text: 'Using NEA weather data (15:00 SGT)',
        timestamp: '14:59',
        type: 'status'
    },
    {
        id: '3',
        sender: 'agent',
        text: "Geometry analyzed. I've retrieved weather data from NEA and identified 3 potential heat pockets in the eastern sector. Proceed with high-resolution CFD for pedestrian comfort, or run a standard preliminary pass?",
        timestamp: '15:00',
        type: 'text'
    },
    {
        id: '4',
        sender: 'agent',
        timestamp: '15:00',
        type: 'form',
        formData: {
            type: 'resolution',
            options: [
                { id: 'high', label: 'High Resolution', time: '~45 mins', desc: '0.5m mesh grid. Includes detailed pedestrian wind comfort (PET).' },
                { id: 'std', label: 'Standard', time: '~10 mins', desc: '2.0m mesh grid. General flow analysis only.' }
            ]
        }
    }
  ]);

  useEffect(() => {
    initializeGemini();
  }, []);

  const handleConfirmSimulation = () => {
    // Simulate progression to next stage
    setMessages(prev => [
        ...prev, 
        { 
            id: Date.now().toString(), 
            sender: 'user', 
            text: 'High Resolution selected. Proceed.', 
            timestamp: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}), 
            type: 'text' 
        },
        {
            id: (Date.now() + 1).toString(),
            sender: 'agent',
            text: 'Initiating solver orchestration. This may take a moment...',
            timestamp: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}),
            type: 'status'
        }
    ]);
    
    // Auto-switch to results after a short delay for effect
    setTimeout(() => {
        setCurrentView('results');
    }, 2500);
  };

  return (
    <div className="flex flex-col h-full bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-white">
      {/* Header */}
      <header className="h-16 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between px-6 shadow-sm z-30 shrink-0">
        <div className="flex items-center gap-3 cursor-pointer" onClick={() => setCurrentView('setup')}>
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center text-white shadow-lg shadow-primary/30">
            <span className="material-icons-outlined text-xl">architecture</span>
          </div>
          <h1 className="font-semibold text-lg tracking-tight font-display">
            Simulation Workspace <span className="text-slate-400 font-normal">| {currentView === 'setup' ? 'Setup & Intent' : currentView === 'results' ? 'Analysis Report' : 'Comparison'}</span>
          </h1>
        </div>
        
        {/* Nav Links (Desktop) */}
        <div className="hidden md:flex gap-8 text-sm font-medium text-slate-500">
             <button onClick={() => setCurrentView('results')} className={`hover:text-primary transition-colors ${currentView === 'results' ? 'text-primary' : ''}`}>Dashboard</button>
             <button onClick={() => setCurrentView('setup')} className={`hover:text-primary transition-colors ${currentView === 'setup' ? 'text-primary' : ''}`}>Projects</button>
             <button onClick={() => setCurrentView('comparison')} className={`hover:text-primary transition-colors ${currentView === 'comparison' ? 'text-primary' : ''}`}>Simulations</button>
             <button className="hover:text-primary transition-colors">Library</button>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-sm text-slate-500 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
            <span className="hidden sm:inline">System Operational</span>
          </div>
          <button className="p-2 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 relative">
            <span className="material-icons-outlined">notifications</span>
            <span className="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full border border-white"></span>
          </button>
          <div className="w-9 h-9 rounded-full bg-slate-200 overflow-hidden border border-slate-300">
            <img src={IMG_USER_AVATAR} alt="User Profile" className="w-full h-full object-cover" />
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 flex overflow-hidden relative">
        {currentView === 'setup' && (
            <>
                <WorkflowSidebar steps={WORKFLOW_STEPS_SETUP} title="Execution Plan" />
                <ChatInterface 
                    messages={messages} 
                    setMessages={setMessages} 
                    onConfirmSimulation={handleConfirmSimulation} 
                />
                <ParamSidebar />
            </>
        )}

        {currentView === 'results' && (
            <ResultsDashboard onCompare={() => setCurrentView('comparison')} />
        )}

        {currentView === 'comparison' && (
            <ComparisonView />
        )}
      </main>
    </div>
  );
};

export default App;