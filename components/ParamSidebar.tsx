import React from 'react';
import { SimulationMetric } from '../types';
import { MOCK_ENV_METRICS, MOCK_MATERIAL_METRICS, IMG_URBAN_TEXTURE } from '../constants';

export const ParamSidebar: React.FC = () => {
  return (
    <aside className="w-80 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col shrink-0 mb-4 mr-4 overflow-hidden">
      <div className="flex border-b border-slate-200 dark:border-slate-800">
        <button className="flex-1 py-3 text-sm font-medium text-primary border-b-2 border-primary bg-blue-50/50">Parameters</button>
        <button className="flex-1 py-3 text-sm font-medium text-slate-500 hover:text-slate-700 transition-colors">Geometry</button>
        <button className="flex-1 py-3 text-sm font-medium text-slate-500 hover:text-slate-700 transition-colors">Settings</button>
      </div>

      <div className="p-5 overflow-y-auto space-y-6 flex-1">
        
        {/* Environment Section */}
        <div>
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Environment (Boundary)</h3>
          <div className="space-y-3">
            {MOCK_ENV_METRICS.map((metric, idx) => (
              <div key={idx} className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-3 border border-slate-200 dark:border-slate-700">
                <div className="flex items-start justify-between mb-1">
                  <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
                    <span className={`material-icons-outlined text-lg ${metric.color}`}>{metric.icon}</span>
                    <span className="text-sm font-medium">{metric.label}</span>
                  </div>
                  <span className="text-sm font-bold text-slate-900 dark:text-white">{metric.value} {metric.unit}</span>
                </div>
                <div className="flex items-center gap-1.5">
                    {metric.isLive && (
                        <span className="px-1.5 py-0.5 bg-green-100 text-green-700 text-[10px] rounded border border-green-200">Live</span>
                    )}
                    <span className="text-[10px] text-slate-500">Source: {metric.source}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Material Section */}
        <div>
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Material Properties</h3>
          <div className="space-y-3">
            {MOCK_MATERIAL_METRICS.map((metric, idx) => (
               <div key={idx} className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-3 border border-slate-200 dark:border-slate-700">
               <div className="flex items-start justify-between mb-1">
                 <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
                   <span className={`material-icons-outlined text-lg ${metric.color}`}>{metric.icon}</span>
                   <span className="text-sm font-medium">{metric.label}</span>
                 </div>
                 <span className="text-sm font-bold text-slate-900 dark:text-white">{metric.value} {metric.unit}</span>
               </div>
               <div className="flex items-center gap-1.5">
                   {metric.isAi && (
                       <span className="px-1.5 py-0.5 bg-indigo-100 text-indigo-700 text-[10px] rounded border border-indigo-200">AI</span>
                   )}
                   <span className="text-[10px] text-slate-500">Source: {metric.source}</span>
               </div>
             </div>
            ))}
          </div>

          <div className="mt-4 border border-slate-200 rounded-lg overflow-hidden h-32 relative group cursor-pointer">
              <img src={IMG_URBAN_TEXTURE} alt="Texture" className="w-full h-full object-cover opacity-80 group-hover:scale-105 transition-transform duration-500" />
              <div className="absolute inset-0 bg-gradient-to-t from-slate-900/80 to-transparent flex items-end p-3">
                  <span className="text-xs text-white font-medium flex items-center gap-1">
                      <span className="material-icons-outlined text-sm">visibility</span>
                      Preview Context
                  </span>
              </div>
          </div>
        </div>

      </div>
    </aside>
  );
};