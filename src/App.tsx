import React, { useState, useEffect, useRef } from 'react';
import {
  Activity,
  CheckCircle2,
  AlertCircle,
  Settings2,
  Monitor,
  Zap,
  Target,
  ChevronDown,
  LayoutDashboard,
  Cpu,
  History,
  Play,
  Pause,
  RefreshCw,
  Eye
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

// --- Types ---
type SystemState = 'IDLE' | 'GATHER' | 'RISE' | 'APEX' | 'RELEASE_WINDOW' | 'FOLLOW_THROUGH';
type ToolStatus = 'GREEN' | 'YELLOW' | 'RED';

// --- Mock Stats ---
const MOCK_LATENCY = 112; // ms
const MOCK_FPS = 144;

export default function App() {
  const [status, setStatus] = useState<ToolStatus>('GREEN');
  const [isActive, setIsActive] = useState(true);
  const [currentPhase, setCurrentPhase] = useState<SystemState>('IDLE');
  const [latency, setLatency] = useState(MOCK_LATENCY);
  const [successRate, setSuccessRate] = useState(96.4);
  const [shotsTaken, setShotsTaken] = useState(248);

  // Simulation Logic
  useEffect(() => {
    if (!isActive) {
      setCurrentPhase('IDLE');
      return;
    }

    const interval = setInterval(() => {
      // Randomly trigger a "shot" simulation
      if (Math.random() > 0.98) {
        runShotSequence();
      }
    }, 100);

    return () => clearInterval(interval);
  }, [isActive]);

  const runShotSequence = async () => {
    const phases: SystemState[] = ['GATHER', 'RISE', 'APEX', 'RELEASE_WINDOW', 'FOLLOW_THROUGH', 'IDLE'];
    for (const phase of phases) {
      setCurrentPhase(phase);
      await new Promise(r => setTimeout(r, phase === 'RISE' ? 400 : 150));
    }
  };

  return (
    <div className="min-h-screen bg-[#0d0d0f] text-gray-100 font-sans selection:bg-emerald-500/30">
      {/* Top Header / Status Panel - Section 8.1 */}
      <header className="border-b border-white/5 bg-black/40 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className={`w-3 h-3 rounded-full ${
                status === 'GREEN' ? 'bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.5)]' :
                status === 'YELLOW' ? 'bg-amber-500' : 'bg-rose-500'
              }`} />
              <div className={`absolute -inset-1 rounded-full animate-ping opacity-20 ${
                status === 'GREEN' ? 'bg-emerald-500' : 'bg-rose-500'
              }`} />
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-tight uppercase text-white/90">NBA 2K26 CV Timing Tool</h1>
              <div className="flex gap-4 mt-0.5 text-[10px] font-mono text-gray-500 uppercase tracking-widest">
                <span>Shots: {shotsTaken}</span>
                <span className="text-emerald-400 font-bold">{successRate}% Excellent</span>
                <span>Latency: {latency}ms</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsActive(!isActive)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                isActive
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20'
                  : 'bg-rose-500/10 text-rose-400 border border-rose-500/20 hover:bg-rose-500/20'
              }`}
            >
              {isActive ? <Play size={14} fill="currentColor" /> : <Pause size={14} fill="currentColor" />}
              {isActive ? 'ACTIVE' : 'STANDBY'} (F8)
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 grid grid-cols-12 gap-6">
        {/* Left Column: Config & Setup */}
        <div className="col-span-12 lg:col-span-4 space-y-6">
          {/* Setup Panel - Section 8.2 */}
          <section className="bg-white/5 rounded-2xl border border-white/10 p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold flex items-center gap-2 uppercase tracking-wider">
                <Settings2 size={16} className="text-gray-400" />
                Setup Progress
              </h2>
              <button className="text-[10px] text-emerald-400 hover:underline">RUN WIZARD</button>
            </div>
            <div className="space-y-3">
              <SetupItem label="Xbox Cloud Window" checked />
              <SetupItem label="Render Rect (1080p)" checked />
              <SetupItem label="Latency Calibrated" checked />
              <SetupItem label="Meter ROI Detected" checked />
              <SetupItem label="Green Zone Sampled" checked />
              <SetupItem label="Gather Buffer (14ms)" checked />
            </div>
          </section>

          {/* Profile Panel - Section 8.3 */}
          <section className="bg-white/5 rounded-2xl border border-white/10 p-5">
            <h2 className="text-sm font-bold flex items-center gap-2 mb-4 uppercase tracking-wider">
              <Zap size={16} className="text-gray-400" />
              Timing Profile
            </h2>
            <div className="space-y-4">
              <div>
                <label className="text-[10px] font-bold text-gray-500 uppercase block mb-1.5">Input Binding</label>
                <div className="relative">
                  <select className="w-full bg-black/40 border border-white/10 rounded-lg py-2 px-3 text-xs appearance-none focus:outline-none focus:border-emerald-500/50">
                    <option>R3 Click (Xbox RS)</option>
                    <option>Square / X Button</option>
                    <option>Pro Stick Down/Hold</option>
                  </select>
                  <ChevronDown className="absolute right-3 top-2.5 text-gray-500" size={14} />
                </div>
              </div>

              <div>
                <label className="text-[10px] font-bold text-gray-500 uppercase block mb-1.5 flex justify-between">
                  Aggressiveness
                  <span className="text-emerald-400">Level 8</span>
                </label>
                <input type="range" className="w-full accent-emerald-500 h-1.5" />
                <div className="flex justify-between mt-1 pt-1 text-[8px] text-gray-600 font-mono">
                  <span>LOOSE</span>
                  <span>PRECISE</span>
                </div>
              </div>

              <div>
                <label className="text-[10px] font-bold text-gray-500 uppercase block mb-1.5">Meter Mode</label>
                <div className="grid grid-cols-3 gap-2">
                  <ModeButton label="ON" active />
                  <ModeButton label="OFF" />
                  <ModeButton label="AUTO" />
                </div>
              </div>
            </div>
          </section>
        </div>

        {/* Right Column: Diagnostics - Section 8.4 */}
        <div className="col-span-12 lg:col-span-8 space-y-6">
          {/* Diagnostic Canvas / Simulator */}
          <section className="bg-black/80 rounded-2xl border border-white/10 overflow-hidden relative group">
            <div className="absolute top-4 left-4 z-20 flex gap-2">
              <span className="text-[9px] bg-black/60 backdrop-blur px-2 py-1 rounded text-white/80 font-mono border border-white/10 flex items-center gap-1.5">
                <Monitor size={10} /> {MOCK_FPS} FPS
              </span>
              <span className="text-[9px] bg-black/60 backdrop-blur px-2 py-1 rounded text-white/80 font-mono border border-white/10 flex items-center gap-1.5">
                <Cpu size={10} /> {currentPhase}
              </span>
            </div>

            <div className="aspect-video bg-[#1a1a1f] relative flex items-center justify-center overflow-hidden">
              {/* This represents the "Render Rect" */}
              <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-transparent" />

              {/* Mock Player Silhouette */}
              <motion.div
                animate={{
                  y: currentPhase === 'RISE' ? -40 : currentPhase === 'APEX' ? -50 : 0,
                  scale: currentPhase === 'GATHER' ? 1.05 : 1
                }}
                className="w-16 h-32 border-2 border-dashed border-blue-500/30 rounded-xl relative flex items-center justify-center bg-blue-500/5"
              >
                <div className="text-[8px] absolute -top-4 text-blue-400 font-mono uppercase font-bold">Player_ROI</div>

                {/* Shooting Hand / Ball */}
                <motion.div
                   animate={{
                     y: currentPhase === 'RISE' ? -30 : currentPhase === 'APEX' ? -60 : currentPhase === 'RELEASE_WINDOW' ? -80 : 0,
                     opacity: currentPhase === 'IDLE' ? 0.3 : 1
                   }}
                   className="w-4 h-4 bg-orange-500 rounded-full absolute"
                />
              </motion.div>

              {/* Section 5.2: Meter ROI Layout */}
              <div className="absolute right-12 top-1/2 -translate-y-1/2 w-48 h-6 border border-yellow-500/50 bg-black/40 rounded flex items-center px-1">
                <div className="text-[8px] absolute -top-4 right-0 text-yellow-500 font-mono uppercase font-bold text-right">Meter_ROI [HSV ACTIVE]</div>

                {/* Green Zone */}
                <div className="h-4 w-6 bg-emerald-500/30 border-x border-emerald-500 absolute left-[65%]" />

                {/* Moving Marker */}
                <motion.div
                  animate={{
                    left: currentPhase === 'IDLE' ? '0%' :
                          currentPhase === 'GATHER' ? '5%' :
                          currentPhase === 'RISE' ? '40%' :
                          currentPhase === 'APEX' ? '60%' :
                          currentPhase === 'RELEASE_WINDOW' ? '68%' : '100%',
                    opacity: currentPhase === 'IDLE' ? 0.2 : 1
                  }}
                  className="w-1.5 h-4 bg-white absolute shadow-[0_0_8px_white]"
                />

                {/* Predictor Arrow */}
                <AnimatePresence>
                  {(currentPhase === 'RISE' || currentPhase === 'APEX') && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="absolute left-[65%] -top-8 flex flex-col items-center"
                    >
                      <span className="text-[8px] text-emerald-400 font-bold mb-1">PREDICTION: -12ms</span>
                      <div className="w-[1px] h-4 bg-emerald-400 animate-pulse" />
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Overlay Flash on Release */}
              <AnimatePresence>
                {currentPhase === 'RELEASE_WINDOW' && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 0.15 }}
                    exit={{ opacity: 0 }}
                    className="absolute inset-0 bg-emerald-400 z-10"
                  />
                )}
              </AnimatePresence>
            </div>

            {/* Diagnostic Footer */}
            <div className="grid grid-cols-4 border-t border-white/10 bg-black/40 backdrop-blur py-3 px-6 gap-6">
              <Stat label="CV Jitter" value="0.4ms" color="text-emerald-400" />
              <Stat label="Total Delay" value={`${MOCK_LATENCY}ms`} color="text-emerald-400" />
              <Stat label="CPU Load" value="4.2%" color="text-emerald-400" />
              <Stat label="VRAM" value="214MB" color="text-gray-400" />
            </div>
          </section>

          {/* Bottom Row - History & Hotkeys */}
          <div className="grid grid-cols-2 gap-6">
            <section className="bg-white/5 rounded-2xl border border-white/10 p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest flex items-center gap-2">
                  <History size={14} /> Shot Logs
                </h2>
                <button className="p-1 hover:bg-white/5 rounded text-gray-500">
                  <RefreshCw size={12} />
                </button>
              </div>
              <div className="space-y-2 max-h-40 overflow-y-auto pr-2 custom-scrollbar">
                <LogEntry time="11:04:12" result="EXCELLENT" offset="+2ms" />
                <LogEntry time="11:03:55" result="EXCELLENT" offset="-1ms" />
                <LogEntry time="11:03:41" result="SLIGHTLY EARLY" offset="-8ms" warning />
                <LogEntry time="11:03:22" result="EXCELLENT" offset="+4ms" />
              </div>
            </section>

            <section className="bg-white/5 rounded-2xl border border-white/10 p-5">
              <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest flex items-center gap-2 mb-4">
                <LayoutDashboard size={14} /> Hotkeys
              </h2>
              <div className="grid grid-cols-1 gap-2.5">
                <Hotkey keyName="F8" action="Toggle Active" />
                <Hotkey keyName="F9" action="Re-detect Window" />
                <Hotkey keyName="F10" action="Manual Calibration Sample" />
                <Hotkey keyName="Ctrl+Shift+L" action="Open Logs" />
              </div>
            </section>
          </div>
        </div>
      </main>

      <style>{`
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
      `}</style>
    </div>
  );
}

// --- Internal Components ---

function SetupItem({ label, checked }: { label: string; checked?: boolean }) {
  return (
    <div className="flex items-center justify-between p-2.5 bg-black/30 rounded-lg border border-white/5 group transition-colors hover:border-white/10">
      <span className="text-[11px] text-gray-400 font-medium">{label}</span>
      {checked ? <CheckCircle2 size={14} className="text-emerald-500" /> : <AlertCircle size={14} className="text-rose-500 shadow-[0_0_8px_rose]" />}
    </div>
  );
}

function ModeButton({ label, active }: { label: string; active?: boolean }) {
  return (
    <button className={`py-1.5 rounded-md text-[10px] font-bold transition-all ${
      active
        ? 'bg-emerald-500 text-black'
        : 'bg-white/5 text-gray-500 border border-white/10 hover:border-white/20'
    }`}>
      {label}
    </button>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[8px] font-bold text-gray-600 uppercase tracking-widest">{label}</span>
      <span className={`text-xs font-mono font-bold mt-0.5 ${color}`}>{value}</span>
    </div>
  );
}

function LogEntry({ time, result, offset, warning }: { time: string; result: string; offset: string; warning?: boolean }) {
  return (
    <div className="flex items-center justify-between text-[10px] font-mono p-1 border-b border-white/5 last:border-0 pb-2">
      <span className="text-gray-600">{time}</span>
      <span className={warning ? 'text-amber-400' : 'text-emerald-400'}>{result}</span>
      <span className="text-gray-500">{offset}</span>
    </div>
  );
}

function Hotkey({ keyName, action }: { keyName: string; action: string }) {
  return (
    <div className="flex items-center justify-between text-[11px]">
      <span className="text-gray-500">{action}</span>
      <kbd className="bg-black border border-white/20 px-1.5 py-0.5 rounded text-white/90 font-mono min-w-[30px] text-center shadow-sm">
        {keyName}
      </kbd>
    </div>
  );
}
