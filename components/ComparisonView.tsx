import React, { useState } from 'react';
import { IMG_COMPARISON_BASELINE, IMG_COMPARISON_SCENARIO } from '../constants';

export const ComparisonView: React.FC = () => {
  const [sliderPosition, setSliderPosition] = useState(50);
  const [isDragging, setIsDragging] = useState(false);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDragging) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    setSliderPosition((x / rect.width) * 100);
  };

  return (
    <div className="flex h-full overflow-hidden font-display">
      {/* Sidebar - Scenario Manager */}
      <aside className="w-72 bg-white border-r border-slate-200 flex flex-col overflow-y-auto z-20 shadow-lg">
        <div className="p-6">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-6">Simulation Workflow</h3>
             {/* Simple vertical steps */}
             <div className="border-l-2 border-green-500 pl-4 space-y-6 ml-2">
                {[
                    {t: 'Data Ingestion', d: 'Mar 12', c: 'text-slate-900'},
                    {t: 'Base Simulation', d: 'Mar 14', c: 'text-slate-900'},
                    {t: 'Scenario Modeling', d: 'Mar 15', c: 'text-slate-900'},
                ].map((s, i) => (
                    <div key={i} className="relative">
                        <span className="absolute -left-[23px] top-0 bg-white text-green-500 material-symbols-outlined text-lg filled-icon">check_circle</span>
                        <p className="text-sm font-semibold">{s.t}</p>
                        <p className="text-xs text-slate-500">Completed {s.d}</p>
                    </div>
                ))}
                <div className="relative">
                     <span className="absolute -left-[23px] top-0 bg-white text-primary material-symbols-outlined text-lg animate-pulse filled-icon">play_circle</span>
                     <p className="text-sm font-semibold text-primary">Scenario Comparison</p>
                     <p className="text-xs text-primary font-medium">Active Stage</p>
                </div>
             </div>
        </div>

        <div className="mt-auto border-t border-slate-200 p-6 bg-slate-50">
            <h3 className="text-sm font-bold mb-4">Scenario Manager</h3>
            <div className="space-y-2">
                <div className="flex items-center gap-3 p-2 rounded-lg bg-white border border-slate-200 shadow-sm">
                    <input type="checkbox" checked readOnly className="rounded text-primary focus:ring-primary" />
                    <span className="text-sm font-medium">Baseline (Default)</span>
                </div>
                <div className="flex items-center gap-3 p-2 rounded-lg bg-white border border-slate-200 shadow-sm">
                    <input type="checkbox" checked readOnly className="rounded text-primary focus:ring-primary" />
                    <span className="text-sm font-medium">Scenario B (20% Canopy)</span>
                </div>
                <div className="flex items-center gap-3 p-2 rounded-lg opacity-50">
                    <input type="checkbox" disabled className="rounded text-primary" />
                    <span className="text-sm font-medium">Scenario C (White Roofs)</span>
                </div>
            </div>
            <button className="mt-4 w-full py-2 border border-dashed border-slate-300 rounded-lg text-xs font-semibold text-slate-500 hover:border-primary hover:text-primary transition-colors flex items-center justify-center gap-2">
                <span className="material-symbols-outlined text-sm">add</span> Add Scenario
            </button>
        </div>
      </aside>

      {/* Middle - Agent Analysis */}
      <section className="w-96 bg-slate-50 border-r border-slate-200 flex flex-col z-10">
          <div className="p-6 flex-1 overflow-y-auto">
              <div className="flex items-center gap-3 mb-6">
                  <div className="size-10 rounded-full bg-primary/10 flex items-center justify-center text-primary">
                      <span className="material-symbols-outlined filled-icon">smart_toy</span>
                  </div>
                  <div>
                      <h1 className="text-lg font-bold text-slate-900">Analysis Agent</h1>
                      <p className="text-xs text-slate-500">Real-time Comparative Insights</p>
                  </div>
              </div>

              <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200 mb-6">
                  <p className="text-sm leading-relaxed mb-4 text-slate-700">
                      Based on the simulation results, <span className="font-bold text-primary">Scenario B</span> significantly mitigates the heat island effect. 
                      By increasing canopy by 20%, we observe a notable drop in surface temperature.
                  </p>
                  <p className="text-sm leading-relaxed mb-4 text-slate-700">
                      Would you like to run a <span className="font-medium underline decoration-primary underline-offset-4">cost-benefit analysis</span>?
                  </p>
                  <div className="flex gap-2">
                      <button className="px-4 py-2 bg-primary text-white text-xs font-bold rounded-lg hover:bg-primary-hover shadow-sm">Run Cost Analysis</button>
                      <button className="px-4 py-2 bg-slate-100 text-xs font-bold rounded-lg hover:bg-slate-200 text-slate-700">Export Summary</button>
                  </div>
              </div>

              {/* Delta Table */}
              <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
                  <div className="px-4 py-3 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                      <h4 className="text-sm font-bold text-slate-800">Delta Overview</h4>
                      <span className="text-[10px] font-bold px-2 py-0.5 bg-green-100 text-green-700 rounded">Improved</span>
                  </div>
                  <table className="w-full text-left text-sm">
                      <thead className="bg-slate-50 text-slate-500">
                          <tr>
                              <th className="px-4 py-2 font-medium">Metric</th>
                              <th className="px-4 py-2 font-medium">Base</th>
                              <th className="px-4 py-2 font-medium">Scen B</th>
                              <th className="px-4 py-2 font-medium">Δ</th>
                          </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                          <tr><td className="px-4 py-3 font-medium">Mean PET</td><td className="px-4 py-3">35.2°</td><td className="px-4 py-3">32.8°</td><td className="px-4 py-3 text-green-600 font-bold">-6.8%</td></tr>
                          <tr><td className="px-4 py-3 font-medium">Peak Temp</td><td className="px-4 py-3">38.5°</td><td className="px-4 py-3">34.1°</td><td className="px-4 py-3 text-green-600 font-bold">-11.4%</td></tr>
                          <tr><td className="px-4 py-3 font-medium">Wind Flow</td><td className="px-4 py-3">1.2m/s</td><td className="px-4 py-3">1.1m/s</td><td className="px-4 py-3 text-red-500 font-bold">-8.3%</td></tr>
                      </tbody>
                  </table>
              </div>
          </div>
          <div className="p-4 border-t border-slate-200 bg-white">
              <div className="relative">
                  <input className="w-full bg-white border border-slate-300 rounded-lg px-4 py-3 pr-10 text-sm focus:ring-2 focus:ring-primary outline-none" placeholder="Ask a follow-up question..." />
                  <span className="material-symbols-outlined absolute right-3 top-3 text-primary cursor-pointer">send</span>
              </div>
          </div>
      </section>

      {/* Right - Visualization Split */}
      <div 
        className="flex-1 relative bg-slate-200 cursor-col-resize overflow-hidden group select-none"
        onMouseDown={() => setIsDragging(true)}
        onMouseUp={() => setIsDragging(false)}
        onMouseLeave={() => setIsDragging(false)}
        onMouseMove={handleMouseMove}
      >
         {/* Baseline Layer (Left) */}
         <div className="absolute inset-0 bg-cover bg-center" style={{ backgroundImage: `url(${IMG_COMPARISON_BASELINE})` }}>
            <div className="absolute top-4 left-4 bg-white/90 px-3 py-1.5 rounded-lg text-xs font-bold shadow-lg text-slate-800">BASELINE</div>
         </div>

         {/* Scenario B Layer (Right - Clipped) */}
         <div 
            className="absolute inset-0 bg-cover bg-center border-l-2 border-white shadow-[0_0_20px_rgba(0,0,0,0.3)]" 
            style={{ 
                backgroundImage: `url(${IMG_COMPARISON_SCENARIO})`,
                clipPath: `inset(0 0 0 ${sliderPosition}%)`
            }}
         >
             <div className="absolute top-4 right-4 bg-white/90 px-3 py-1.5 rounded-lg text-xs font-bold shadow-lg text-primary">SCENARIO B</div>
         </div>

         {/* Slider Handle */}
         <div className="absolute top-0 bottom-0 w-1 bg-white cursor-col-resize z-30 shadow-2xl" style={{ left: `${sliderPosition}%` }}>
             <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 size-10 bg-white rounded-full flex items-center justify-center shadow-xl border-2 border-slate-200">
                 <span className="material-symbols-outlined text-slate-500">unfold_more</span>
             </div>
         </div>
         
         {/* Floating Legend */}
         <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex items-center gap-4 bg-white/95 backdrop-blur p-2 rounded-xl shadow-2xl border border-slate-200 z-20">
             <button className="flex items-center gap-2 px-3 py-1.5 bg-primary text-white text-xs font-bold rounded-lg shadow-md">
                 <span className="material-symbols-outlined text-sm">layers</span>
                 Difference Map
             </button>
             <div className="h-6 w-px bg-slate-300"></div>
             <div className="flex gap-1">
                 <button className="p-1.5 hover:bg-slate-100 rounded-lg"><span className="material-symbols-outlined text-lg text-slate-600">zoom_in</span></button>
                 <button className="p-1.5 hover:bg-slate-100 rounded-lg"><span className="material-symbols-outlined text-lg text-slate-600">3d_rotation</span></button>
             </div>
         </div>

      </div>
    </div>
  );
};