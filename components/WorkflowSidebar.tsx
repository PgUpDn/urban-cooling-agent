import React from 'react';
import { WorkflowStep } from '../types';

interface WorkflowSidebarProps {
  steps: WorkflowStep[];
  title: string;
  subtitle?: string;
  compact?: boolean;
}

export const WorkflowSidebar: React.FC<WorkflowSidebarProps> = ({ steps, title, subtitle, compact }) => {
  return (
    <aside className={`bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col shrink-0 overflow-y-auto ${compact ? 'w-64 p-6' : 'w-64 p-5'}`}>
      <div className="mb-6">
        <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">{title}</h2>
        {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      </div>
      
      <div className="relative pl-2">
        {/* Connector Line */}
        <div className="absolute left-2.5 top-2 bottom-2 w-0.5 bg-slate-200 dark:bg-slate-800 -z-10"></div>
        
        {steps.map((step, idx) => (
          <div key={step.id} className={`flex gap-4 mb-8 group ${step.status === 'pending' ? 'opacity-50' : ''}`}>
            <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 border-2 z-10 
              ${step.status === 'completed' ? 'bg-green-100 border-green-500 text-green-600' : 
                step.status === 'active' ? 'bg-white border-primary shadow-[0_0_0_4px_rgba(37,99,235,0.2)]' : 
                'bg-slate-100 border-slate-300'}`}>
              
              {step.status === 'completed' && <span className="material-icons-outlined text-sm font-bold">check</span>}
              {step.status === 'active' && (
                 <svg className="animate-spin h-3.5 w-3.5 text-primary" fill="none" viewBox="0 0 24 24">
                   <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                   <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                 </svg>
              )}
              {step.status === 'pending' && <span className="block w-1.5 h-1.5 bg-slate-400 rounded-full"></span>}
            </div>
            <div>
              <h3 className={`text-sm font-medium ${step.status === 'active' ? 'text-primary font-bold' : 'text-slate-900 dark:text-white'}`}>
                {step.label}
              </h3>
              {step.desc && (
                <p className={`text-xs mt-1 ${step.status === 'active' ? 'text-slate-500 animate-pulse' : 'text-slate-500'}`}>
                  {step.desc}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
};