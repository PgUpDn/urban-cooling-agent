import React from 'react';
import { IMG_HEATMAP_FULL } from '../constants';
import { WorkflowSidebar } from './WorkflowSidebar';
import { WORKFLOW_STEPS_RESULTS } from '../constants';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts';

interface ResultsDashboardProps {
  onCompare: () => void;
}

const data = [
    { name: '10am', temp: 30 },
    { name: '12pm', temp: 35 },
    { name: '2pm', temp: 38.2 },
    { name: '4pm', temp: 34 },
    { name: '6pm', temp: 31 },
];

export const ResultsDashboard: React.FC<ResultsDashboardProps> = ({ onCompare }) => {
  return (
    <div className="flex-1 flex overflow-hidden">
      <WorkflowSidebar steps={WORKFLOW_STEPS_RESULTS} title="Simulation Workflow" subtitle="Project: Urban Climate Research" />
      
      {/* Center Panel */}
      <section className="flex-1 flex flex-col bg-slate-50 dark:bg-slate-900 overflow-y-auto">
        <div className="p-8 pb-4">
            <div className="flex justify-between items-end mb-6">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight text-slate-900 font-display">Simulation Analysis & Final Report</h2>
                    <p className="text-slate-500 text-lg">15:00 SGT Scenario - Thermal Comfort Performance</p>
                </div>
                <div className="flex gap-3">
                    <button 
                        onClick={onCompare}
                        className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-300 rounded-lg text-sm font-bold text-slate-700 shadow-sm hover:bg-slate-50 transition-colors">
                        <span className="material-symbols-outlined">compare_arrows</span>
                        Compare Scenarios
                    </button>
                    <button className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg text-sm font-bold shadow-sm hover:bg-primary-hover transition-colors">
                         <span className="material-symbols-outlined">picture_as_pdf</span>
                         Export PDF Report
                    </button>
                </div>
            </div>

            {/* Status Banner */}
            <div className="mb-6 bg-green-50 border border-green-200 rounded-xl p-5 flex items-center gap-4">
                <div className="bg-green-100 p-2 rounded-full text-green-600">
                    <span className="material-symbols-outlined text-2xl filled-icon">verified</span>
                </div>
                <div>
                    <h3 className="text-base font-bold text-slate-900">Simulation completed successfully</h3>
                    <p className="text-sm text-slate-600">The central courtyard exceeds the thermal comfort threshold (PET {'>'} 35°C) based on current parameters.</p>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pb-8">
                {/* Findings Card */}
                <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
                     <div className="flex items-center gap-2 mb-4 text-slate-900">
                        <span className="material-symbols-outlined text-primary">insights</span>
                        <h3 className="text-lg font-bold">Key Findings</h3>
                     </div>
                     <div className="flex gap-6">
                        <div className="flex-1 space-y-4">
                            <p className="text-sm text-slate-500 leading-relaxed">
                                Wind stagnation observed in the north-east corner. Solar gain peaks between 13:00 and 15:00, leading to significant thermal storage.
                            </p>
                            <ul className="space-y-2 text-sm text-slate-700">
                                <li className="flex items-center gap-2"><span className="w-1.5 h-1.5 bg-primary rounded-full"></span> Wind speed: {'<'} 0.5m/s in courtyard</li>
                                <li className="flex items-center gap-2"><span className="w-1.5 h-1.5 bg-primary rounded-full"></span> Solar irradiance: 850 W/m² peak</li>
                                <li className="flex items-center gap-2"><span className="w-1.5 h-1.5 bg-primary rounded-full"></span> Humidity: 75% average daily</li>
                            </ul>
                        </div>
                        <div className="w-40 bg-slate-50 rounded-lg p-4 border border-dashed border-slate-300 flex flex-col items-center justify-center text-center">
                             <div className="w-full h-16">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={data}>
                                        <Bar dataKey="temp" fill="#2563EB" radius={[2,2,0,0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                             </div>
                             <p className="text-2xl font-bold text-slate-900 mt-2">38.2°C</p>
                             <p className="text-xs text-red-500 font-bold">Max PET Observed</p>
                        </div>
                     </div>
                </div>

                {/* Synthesis Card */}
                 <div className="bg-blue-50/50 border-l-4 border-primary rounded-xl p-6">
                     <div className="flex items-center gap-2 mb-3 text-primary">
                        <span className="material-symbols-outlined filled-icon">lightbulb</span>
                        <h3 className="text-lg font-bold">Synthesis Recommendation</h3>
                     </div>
                     <p className="text-slate-800 text-base font-medium leading-relaxed mb-4">
                         "Increasing canopy cover by <span className="text-primary font-bold">20%</span> via broad-leaf native species in the north-east quadrant is predicted to reduce PET by <span className="text-primary font-bold">2.4°C</span>."
                     </p>
                     <div className="flex gap-4">
                         <button className="text-sm font-bold text-primary hover:underline underline-offset-4">Run Sensitivity Analysis</button>
                         <button className="text-sm font-bold text-primary hover:underline underline-offset-4">Apply Recommendation</button>
                     </div>
                 </div>
            </div>
        </div>
      </section>

      {/* Right Visualizer */}
      <aside className="w-[420px] bg-white border-l border-slate-200 flex flex-col">
        <div className="flex border-b border-slate-200">
             <button className="flex-1 py-4 text-sm font-bold text-primary border-b-2 border-primary bg-primary/5">Results</button>
             <button className="flex-1 py-4 text-sm font-medium text-slate-500 hover:bg-slate-50">Parameters</button>
             <button className="flex-1 py-4 text-sm font-medium text-slate-500 hover:bg-slate-50">Logs</button>
        </div>
        <div className="p-6 flex-1 overflow-y-auto">
             <div className="relative group rounded-xl overflow-hidden bg-slate-100 border border-slate-200 shadow-inner">
                 <img src={IMG_HEATMAP_FULL} alt="Heatmap" className="w-full aspect-[4/3] object-cover" />
                 {/* Legend */}
                 <div className="absolute right-3 top-3 bg-white/90 p-2 rounded-lg border border-slate-200 shadow-sm backdrop-blur">
                     <p className="text-[10px] font-bold text-slate-500 mb-1">PET INDEX (°C)</p>
                     <div className="h-24 w-3 bg-gradient-to-t from-blue-500 via-yellow-400 to-red-600 rounded-full mx-auto relative">
                        <span className="absolute -left-5 top-0 text-[9px] font-bold">45</span>
                        <span className="absolute -left-5 bottom-0 text-[9px] font-bold">20</span>
                     </div>
                 </div>
                 <div className="absolute bottom-3 left-3 flex gap-2">
                     <button className="bg-white/90 p-1.5 rounded-lg shadow hover:bg-white"><span className="material-symbols-outlined text-sm">zoom_in</span></button>
                     <button className="bg-white/90 p-1.5 rounded-lg shadow hover:bg-white"><span className="material-symbols-outlined text-sm">layers</span></button>
                 </div>
             </div>

             {/* Time Slider */}
             <div className="mt-8">
                 <div className="flex justify-between items-center mb-2">
                     <p className="text-sm font-bold text-slate-900">Temporal Profile</p>
                     <p className="text-sm font-black text-primary">15:00 SGT</p>
                 </div>
                 <div className="relative h-2 bg-slate-200 rounded-full mb-2">
                     <div className="absolute top-0 left-0 h-full w-2/3 bg-primary rounded-full">
                         <div className="absolute right-0 -top-1.5 w-5 h-5 bg-white border-2 border-primary rounded-full shadow-md cursor-pointer hover:scale-110 transition-transform"></div>
                     </div>
                 </div>
                 <div className="flex justify-between text-[10px] font-bold text-slate-400">
                     <span>09:00</span><span>12:00</span><span>15:00</span><span>18:00</span>
                 </div>
             </div>

             {/* Artifacts */}
             <div className="mt-10 pt-6 border-t border-slate-200">
                 <p className="text-sm font-bold text-slate-900 mb-4">Download Artifacts</p>
                 <div className="space-y-3">
                     {['thermal_comfort.vtk', 'wind_vectors.csv'].map((file, i) => (
                         <div key={i} className="flex items-center justify-between p-3 rounded-lg border border-slate-200 hover:bg-slate-50 cursor-pointer group">
                             <div className="flex items-center gap-3">
                                 <span className="material-symbols-outlined text-primary group-hover:scale-110 transition-transform">{i===0 ? 'description' : 'table_chart'}</span>
                                 <div>
                                     <p className="text-xs font-bold text-slate-900">{file}</p>
                                     <p className="text-[10px] text-slate-500">3D Field Data • 42.1 MB</p>
                                 </div>
                             </div>
                             <span className="material-symbols-outlined text-primary text-lg">download</span>
                         </div>
                     ))}
                 </div>
             </div>
        </div>
      </aside>
    </div>
  );
};