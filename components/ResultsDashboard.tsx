import React from 'react';
import { IMG_HEATMAP_FULL } from '../constants';
import { WorkflowSidebar } from './WorkflowSidebar';
import { WORKFLOW_STEPS_RESULTS } from '../constants';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts';
import type { SimulationResults } from '../types';
import { artifactUrl } from '../services/agentService';

interface Props { onCompare: () => void; simulationResults?: SimulationResults | null; }

const MOCK_DATA = [{ name: '10am', temp: 30 },{ name: '12pm', temp: 35 },{ name: '2pm', temp: 38.2 },{ name: '4pm', temp: 34 },{ name: '6pm', temp: 31 }];

function chartData(r: SimulationResults | null | undefined) {
  if (!r?.pet_time_summary?.length) return MOCK_DATA;
  return r.pet_time_summary.map(e => ({ name: e.time_token ?? '', temp: Number(e.max_value?.toFixed(1) ?? 0) }));
}
function maxPET(r: SimulationResults | null | undefined) {
  if (!r?.pet_time_summary?.length) return '38.2';
  return Math.max(...r.pet_time_summary.map(s => s.max_value)).toFixed(1);
}
function heatmap(r: SimulationResults | null | undefined) {
  if (!r) return IMG_HEATMAP_FULL;
  if (r.screenshots?.length) return artifactUrl(r.screenshots[0].url);
  if (r.visualization_files?.length) return artifactUrl(r.visualization_files[0].url);
  return IMG_HEATMAP_FULL;
}
function cp(r: SimulationResults | null | undefined, k: string, fb: string) { return r?.cfd_parameters?.[k] != null ? String(r.cfd_parameters[k]) : fb; }

export const ResultsDashboard: React.FC<Props> = ({ onCompare, simulationResults: r }) => {
  const cd = chartData(r); const mp = maxPET(r); const hm = heatmap(r); const real = !!r?.success;
  const narrative = r?.response ?? '';
  const findings = real ? narrative.slice(0,500)+(narrative.length>500?'\u2026':'') : 'Wind stagnation observed in the north-east corner. Solar gain peaks between 13:00 and 15:00.';
  const ws = cp(r,'u_inflow','1.2'); const temp = cp(r,'T2m_C','30'); const hum = cp(r,'RH2m_percent','75');
  const files = real ? [...(r!.artifact_files??[]),...(r!.csv_files??[])] : [{filename:'thermal_comfort.vtk',url:'#'},{filename:'wind_vectors.csv',url:'#'}];

  return (
    <div className="flex-1 flex overflow-hidden">
      <WorkflowSidebar steps={WORKFLOW_STEPS_RESULTS} title="Simulation Workflow" subtitle="Project: Urban Climate Research" />
      <section className="flex-1 flex flex-col bg-slate-50 dark:bg-slate-900 overflow-y-auto">
        <div className="p-8 pb-4">
          <div className="flex justify-between items-end mb-6">
            <div><h2 className="text-3xl font-bold tracking-tight text-slate-900 font-display">Simulation Analysis & Final Report</h2><p className="text-slate-500 text-lg">{real?'Backend Agent Results':'Demo'} - Thermal Comfort</p></div>
            <div className="flex gap-3">
              <button onClick={onCompare} className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-300 rounded-lg text-sm font-bold text-slate-700 shadow-sm hover:bg-slate-50"><span className="material-symbols-outlined">compare_arrows</span>Compare</button>
              <button className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg text-sm font-bold shadow-sm hover:bg-primary-hover"><span className="material-symbols-outlined">picture_as_pdf</span>Export PDF</button>
            </div>
          </div>
          <div className="mb-6 bg-green-50 border border-green-200 rounded-xl p-5 flex items-center gap-4">
            <div className="bg-green-100 p-2 rounded-full text-green-600"><span className="material-symbols-outlined text-2xl filled-icon">verified</span></div>
            <div><h3 className="text-base font-bold text-slate-900">{real?'Simulation completed via backend agent':'Simulation completed'}</h3><p className="text-sm text-slate-600">{real?`Max PET: ${mp}\u00B0C | Wind: ${ws} m/s | Humidity: ${hum}%`:'Demo data shown.'}</p></div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pb-8">
            <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
              <div className="flex items-center gap-2 mb-4 text-slate-900"><span className="material-symbols-outlined text-primary">insights</span><h3 className="text-lg font-bold">Key Findings</h3></div>
              <div className="flex gap-6"><div className="flex-1 space-y-4"><p className="text-sm text-slate-500 leading-relaxed">{findings}</p><ul className="space-y-2 text-sm text-slate-700"><li className="flex items-center gap-2"><span className="w-1.5 h-1.5 bg-primary rounded-full"></span>Wind: {ws} m/s</li><li className="flex items-center gap-2"><span className="w-1.5 h-1.5 bg-primary rounded-full"></span>Temp: {temp}\u00B0C</li><li className="flex items-center gap-2"><span className="w-1.5 h-1.5 bg-primary rounded-full"></span>Humidity: {hum}%</li></ul></div>
              <div className="w-40 bg-slate-50 rounded-lg p-4 border border-dashed border-slate-300 flex flex-col items-center justify-center text-center"><div className="w-full h-16"><ResponsiveContainer width="100%" height="100%"><BarChart data={cd}><Bar dataKey="temp" fill="#2563EB" radius={[2,2,0,0]} /></BarChart></ResponsiveContainer></div><p className="text-2xl font-bold text-slate-900 mt-2">{mp}\u00B0C</p><p className="text-xs text-red-500 font-bold">Max PET</p></div></div>
            </div>
            <div className="bg-blue-50/50 border-l-4 border-primary rounded-xl p-6">
              <div className="flex items-center gap-2 mb-3 text-primary"><span className="material-symbols-outlined filled-icon">lightbulb</span><h3 className="text-lg font-bold">Synthesis</h3></div>
              <p className="text-slate-800 text-base font-medium leading-relaxed mb-4">{real ? (r!.building_analysis?.slice(0,300)||'See full report.') : 'Increasing canopy cover by 20% is predicted to reduce PET by 2.4\u00B0C.'}</p>
            </div>
          </div>
          {real && narrative && <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm mb-8"><div className="flex items-center gap-2 mb-4 text-slate-900"><span className="material-symbols-outlined text-primary">description</span><h3 className="text-lg font-bold">Full Agent Report</h3></div><div className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto">{narrative}</div></div>}
        </div>
      </section>
      <aside className="w-[420px] bg-white border-l border-slate-200 flex flex-col">
        <div className="flex border-b border-slate-200"><button className="flex-1 py-4 text-sm font-bold text-primary border-b-2 border-primary bg-primary/5">Results</button><button className="flex-1 py-4 text-sm font-medium text-slate-500">Logs</button></div>
        <div className="p-6 flex-1 overflow-y-auto">
          <div className="relative group rounded-xl overflow-hidden bg-slate-100 border border-slate-200 shadow-inner"><img src={hm} alt="Heatmap" className="w-full aspect-[4/3] object-cover" /><div className="absolute right-3 top-3 bg-white/90 p-2 rounded-lg border border-slate-200 shadow-sm backdrop-blur"><p className="text-[10px] font-bold text-slate-500 mb-1">PET (\u00B0C)</p><div className="h-24 w-3 bg-gradient-to-t from-blue-500 via-yellow-400 to-red-600 rounded-full mx-auto relative"><span className="absolute -left-5 top-0 text-[9px] font-bold">45</span><span className="absolute -left-5 bottom-0 text-[9px] font-bold">20</span></div></div></div>
          <div className="mt-8"><div className="flex justify-between items-center mb-2"><p className="text-sm font-bold text-slate-900">Temporal Profile</p></div><div className="w-full h-24"><ResponsiveContainer width="100%" height="100%"><BarChart data={cd}><XAxis dataKey="name" tick={{fontSize:10}} /><YAxis domain={['dataMin-2','dataMax+2']} tick={{fontSize:10}} /><Tooltip /><Bar dataKey="temp" fill="#2563EB" radius={[3,3,0,0]} /></BarChart></ResponsiveContainer></div></div>
          <div className="mt-10 pt-6 border-t border-slate-200"><p className="text-sm font-bold text-slate-900 mb-4">Download Artifacts</p><div className="space-y-3">{files.slice(0,6).map((f:any,i:number) => { const n=f.filename??`artifact_${i}`; const u=f.url??'#'; return <a key={i} href={u!=='#'?artifactUrl(u):'#'} target="_blank" rel="noopener noreferrer" className="flex items-center justify-between p-3 rounded-lg border border-slate-200 hover:bg-slate-50 cursor-pointer group"><div className="flex items-center gap-3"><span className="material-symbols-outlined text-primary group-hover:scale-110 transition-transform">{n.endsWith('.vtk')?'description':'table_chart'}</span><div><p className="text-xs font-bold text-slate-900">{n}</p></div></div><span className="material-symbols-outlined text-primary text-lg">download</span></a>; })}</div></div>
        </div>
      </aside>
    </div>
  );
};
