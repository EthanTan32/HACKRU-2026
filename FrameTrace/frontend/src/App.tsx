import { useEffect, useRef, useState } from 'react'
import { Activity, AlertCircle, ArrowUpRight, CheckCircle2, Clapperboard, FileVideo, Fingerprint, SlidersHorizontal, Layers3, ScanText, UploadCloud, Waves, X } from 'lucide-react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AnalysisResult, API, DetectorResult, getAnalysis, getJobStatus, getMediaUrl, getArtifactUrl, uploadVideo } from './api'

type UploadState = 'idle' | 'uploading' | 'queued' | 'running' | 'completed' | 'failed'
const detectors = [
  {key:'facial_consistency', name:'Facial Consistency', icon:Fingerprint, desc:'Pose-normalized temporal facial geometry'},
  {key:'text_consistency', name:'Text Consistency', icon:ScanText, desc:'OCR character stability over time'},
  {key:'background_motion', name:'Background Motion', icon:Layers3, desc:'Dominant-scene geometric coherence'},
  {key:'depth_consistency', name:'Depth Consistency', icon:Fingerprint, desc:'Motion-aligned relative depth'},
  {key:'optical_flow', name:'Optical Flow', icon:Waves, desc:'Tracked-feature trajectory changes'},
  {key:'color_consistency', name:'Gamma / Saturation', icon:SlidersHorizontal, desc:'Aligned brightness and color residuals'},
]

function formatValue(v: number | null) { return v === null ? '—' : v.toFixed(3) }
function statusText(d?: DetectorResult) {
  if (!d) return 'Waiting'
  return ({ok:'Analyzed',insufficient_data:'Not enough evidence',not_enabled:'Disabled',not_available:'Model unavailable',error:'Error'})[d.status]
}

function AnalyzerCard({title, result, icon:Icon, description}: {title:string, result?:DetectorResult, icon:typeof ScanText, description:string}) {
  return <div className="panel min-h-42 p-5">
    <div className="flex justify-between gap-3">
      <div className="flex items-center gap-3"><div className="rounded-xl bg-cyan-400/10 p-2.5 text-cyan-300"><Icon size={19}/></div>
        <div><h3 className="font-semibold">{title}</h3><p className="text-xs text-slate-400">{description}</p></div></div>
      <span className="text-xs text-slate-400 whitespace-nowrap">{statusText(result)}</span>
    </div>
    <div className="mt-6 flex items-end justify-between"><div>
      <p className="text-xs uppercase tracking-wide text-slate-500">Anomaly index</p>
      <p className="mt-1 text-3xl font-semibold tracking-tight">{formatValue(result?.anomaly_index ?? null)}</p></div>
      <p className="text-xs text-slate-400">{result?.events.length ?? 0} flagged moments</p>
    </div>
    {result?.metrics && <details className="mt-3 text-xs text-slate-400"><summary>Raw measurements and evidence quality</summary>{Object.entries(result.metrics).map(([key,value]) => <p key={key}>{key.replaceAll('_',' ')}: {typeof value === 'number' ? value.toFixed(3) : value}</p>)}</details>}
    <p className="mt-3 text-xs leading-relaxed text-slate-400">{result?.note ?? 'Analysis results appear after processing.'}</p>
  </div>
}

export default function App() {
  const [file, setFile] = useState<File | null>(null)
  const [id, setId] = useState<string | null>(null)
  const [status, setStatus] = useState<UploadState>('idle')
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [activeTime, setActiveTime] = useState<number | null>(null)
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    if (!id || (status !== 'queued' && status !== 'running')) return
    let alive = true
    const check = async () => {
      try {
        const job = await getJobStatus(id)
        if (!alive) return
        setStatus(job.status)
        if (job.status === 'completed') setResult(await getAnalysis(id))
        if (job.status === 'failed') setError(job.error ?? 'Analysis failed')
      } catch (err) { if (alive) setError(String(err)) }
    }
    void check()
    const timer = window.setInterval(check, 1600)
    return () => { alive = false; window.clearInterval(timer) }
  }, [id, status])

  function chooseFile(f?: File) {
    setFile(f ?? null); setId(null); setResult(null); setError(null); setStatus('idle')
  }
  async function start() {
    if (!file) return
    setStatus('uploading'); setError(null); setResult(null)
    try { const job = await uploadVideo(file); setId(job.video_id); setStatus('queued') }
    catch (err: unknown) {
      let message = 'Upload failed. Is the backend running?'
      if (typeof err === 'object' && err && 'response' in err) {
        const e = err as {response?: {data?: {detail?: string}}}
        message = e.response?.data?.detail ?? message
      }
      setError(message); setStatus('failed')
    }
  }
  function jump(time: number) {
    setActiveTime(time)
    if (videoRef.current) { videoRef.current.currentTime = time; videoRef.current.play().catch(() => {}) }
  }

  const chartData = result?.timeline.map(e => ({time:e.timestamp, severity:e.severity, type:e.type})) ?? []
  const busy = status === 'uploading' || status === 'queued' || status === 'running'

  return <div className="min-h-screen bg-[#08101f] text-slate-100">
    <header className="border-b border-slate-800/80 px-5 py-4 md:px-10">
      <div className="mx-auto flex max-w-6xl items-center justify-between">
        <div className="flex items-center gap-3"><div className="rounded-xl bg-cyan-400/15 p-2.5 text-cyan-300"><Clapperboard size={22}/></div>
          <div><p className="text-lg font-bold tracking-tight">FrameTrace</p><p className="text-[11px] uppercase tracking-[.24em] text-cyan-300/80">Video forensics lab</p></div></div>
        <span className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-400">Research prototype · V0.1</span>
      </div>
    </header>
    <main className="mx-auto max-w-6xl px-5 pb-16 pt-10 md:px-10">
      <div className="mb-9 max-w-3xl"><div className="mb-3 flex items-center gap-2 text-sm text-cyan-300"><Activity size={15}/> Six independent evidence analyzers</div>
        <h1 className="text-3xl font-bold leading-tight tracking-tight md:text-5xl">Inspect the details between frames.</h1>
        <p className="mt-4 text-slate-400 leading-relaxed">Upload a short video to examine changing text, geometric background motion, estimated depth stability, optical-flow trajectories, and gamma/saturation instability. Results are forensic measurements, not proof of AI generation.</p>
      </div>
      <section className="grid gap-6 md:grid-cols-5">
        <div className="panel p-6 md:col-span-3">
          <div onDragOver={e => { e.preventDefault(); setIsDragging(true) }} onDragLeave={() => setIsDragging(false)} onDrop={e => { e.preventDefault(); setIsDragging(false); chooseFile(e.dataTransfer.files[0]) }}
            className={`flex min-h-64 flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center transition ${isDragging ? 'border-cyan-400 bg-cyan-400/10' : 'border-slate-700 bg-slate-900/55'}`}>
            <UploadCloud size={34} className="text-cyan-300"/>
            <h2 className="mt-4 font-semibold">Drop your video here</h2>
            <p className="mt-1 text-sm text-slate-400">MP4, MOV, WEBM, AVI · Max 100 MB · Max 30 seconds</p>
            <label className="mt-5 cursor-pointer rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-sm font-medium hover:bg-slate-700">
              Choose video <input type="file" accept="video/*" className="hidden" onChange={e => chooseFile(e.target.files?.[0])}/>
            </label>
          </div>
          {file && <div className="mt-4 flex items-center justify-between gap-3 rounded-lg bg-slate-800/70 px-4 py-3">
            <div className="flex min-w-0 items-center gap-3"><FileVideo className="shrink-0 text-cyan-300" size={20}/><span className="truncate text-sm">{file.name}</span></div>
            <button disabled={busy} onClick={() => chooseFile(undefined)} className="text-slate-400 hover:text-white"><X size={17}/></button>
          </div>}
          <button onClick={start} disabled={!file || busy} className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-cyan-400 px-5 py-3 font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-40 hover:bg-cyan-300">
            <Activity size={18}/>{busy ? `Analysis: ${status}…` : 'Start analysis'}
          </button>
          {error && <div className="mt-4 flex items-center gap-2 text-sm text-rose-300"><AlertCircle size={16}/>{error}</div>}
          {status==='completed' && <div className="mt-4 flex items-center gap-2 text-sm text-emerald-300"><CheckCircle2 size={17}/> Analysis complete</div>}
        </div>
        <div className="panel p-6 md:col-span-2">
          <h2 className="font-semibold">Analysis pipeline</h2><p className="mt-2 text-sm text-slate-400">Our research modules independently evaluate frame-to-frame evidence.</p>
          <div className="mt-6 space-y-5">{detectors.map((det, n) => <div className="flex items-center gap-3" key={det.key}>
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-800 text-xs font-semibold text-cyan-300">0{n+1}</div>
            <div><p className="text-sm font-semibold">{det.name}</p><p className="text-xs text-slate-400">{det.desc}</p></div></div>)}</div>
        </div>
      </section>
      {result && <section className="mt-9 space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-bold">Analysis report</h2><p className="mt-1 text-sm text-slate-400">{result.video.duration_seconds}s · {result.video.sampled_frames} sampled frames</p></div>
          <span className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">{result.classification === 'not_trained'
            ? 'No trained AI/real classifier'
            : `${result.classification.replaceAll('_', ' ')}${result.ai_probability != null ? ` · ${(result.ai_probability*100).toFixed(1)}% estimated AI probability` : ''}`}</span></div>
        <p className="text-xs text-slate-400">{result.message}</p>
        <div className="grid gap-4 md:grid-cols-2">{detectors.map(d => <AnalyzerCard key={d.key} title={d.name} description={d.desc} result={result.detectors[d.key]} icon={d.icon}/>)}</div>
        {detectors.filter(d => result.detectors[d.key]?.segments?.length).map(d => <div className="panel p-5" key={d.key}><h3>{d.name}: raw segment measurements (not AI probability)</h3><ResponsiveContainer width="100%" height={180}><LineChart data={result.detectors[d.key].segments}><XAxis dataKey="timestamp" type="number" domain={['dataMin','dataMax']}/><YAxis domain={['auto','auto']}/><Tooltip/><Line dataKey="raw_value" stroke="#51d8df" dot={false}/></LineChart></ResponsiveContainer></div>)}
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="panel p-5"><h3 className="mb-4 font-semibold">Video playback</h3><video ref={videoRef} controls preload="metadata" src={getMediaUrl(result.video_id)} className="max-h-80 w-full rounded-xl bg-black" />
            {activeTime !== null && <p className="mt-3 text-xs text-slate-400">Jumped to {activeTime.toFixed(2)}s</p>}</div>
          <div className="panel p-5"><h3 className="mb-4 font-semibold">Anomaly timeline</h3>
            {chartData.length ? <ResponsiveContainer width="100%" height={210}><LineChart data={chartData}><CartesianGrid stroke="#243249" strokeDasharray="4 4"/><XAxis dataKey="time" stroke="#94a3b8" tickFormatter={x => `${x}s`} fontSize={11}/><YAxis domain={[0,1]} stroke="#94a3b8" fontSize={11}/><Tooltip contentStyle={{background:'#142036',borderColor:'#334155'}}/><Line dataKey="severity" stroke="#51d8df" strokeWidth={2} dot/></LineChart></ResponsiveContainer> : <div className="flex h-48 items-center justify-center text-center text-sm text-slate-400">No anomaly events flagged by the enabled modules.</div>}
          </div>
        </div>
        {result.artifacts.length > 0 && <div className="panel p-5">
          <h3 className="font-semibold">Diagnostic image previews</h3>
          <p className="mt-1 text-xs text-slate-400">These are measurements and visualizations, not proof of AI generation.</p>
          <div className="mt-4 grid gap-4 md:grid-cols-3">{result.artifacts.map(kind =>
            <div key={kind}><img className="w-full rounded-lg object-contain bg-black" src={getArtifactUrl(result.video_id, kind)} alt={kind.replaceAll('_', ' ')}/>
              <p className="mt-2 text-sm text-slate-300">{kind.replaceAll('_', ' ')}</p></div>
          )}</div>
        </div>}
        <div className="panel p-5"><h3 className="font-semibold">Timestamped evidence</h3>
          {result.timeline.length ? <div className="mt-4 divide-y divide-slate-800">{result.timeline.map((event, idx) =>
            <button key={`${event.detector}-${idx}`} onClick={() => jump(event.timestamp)} className="flex w-full items-start justify-between gap-4 py-3 text-left hover:text-cyan-300">
              <div><p className="text-sm font-semibold">{event.type.replaceAll('_', ' ')}</p><p className="mt-1 text-xs text-slate-400">{event.detector?.replaceAll('_',' ')} · {event.detail}</p></div>
              <div className="flex shrink-0 items-center gap-1 text-xs">{event.timestamp.toFixed(2)}s <ArrowUpRight size={14}/></div></button>
          )}</div> : <p className="mt-3 text-sm text-slate-400">No events crossed the current heuristic thresholds. This does not imply the video is authentic.</p>}
        </div>
      </section>}
      <footer className="mt-10 text-center text-xs text-slate-500">FrameTrace · {API} · Experimental anomaly metrics must be calibrated before use as an AI detector.</footer>
    </main>
  </div>
}
