import axios from 'axios'
export const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type DetectorStatus = 'ok' | 'insufficient_data' | 'not_enabled' | 'not_available' | 'error'
export type EvidenceEvent = {
  timestamp: number
  type: string
  severity: number
  detail: string
  detector?: string
}
export type DetectorResult = {
  name: string
  status: DetectorStatus
  anomaly_index: number | null
  segments?: {timestamp: number; raw_value: number; confidence?: number}[]
  events: EvidenceEvent[]
  metrics: Record<string, string | number>
  note: string
}
export type AnalysisResult = {
  video_id: string
  classification: string
  ai_probability: number | null
  message: string
  artifacts: string[]
  video: {duration_seconds: number; fps: number; sampled_frames: number}
  detectors: Record<string, DetectorResult>
  timeline: EvidenceEvent[]
}
export type JobStatus = {video_id: string; status: 'queued' | 'running' | 'failed' | 'completed'; error?: string}

export async function uploadVideo(file: File) {
  const form = new FormData()
  form.append('video', file)
  const { data } = await axios.post<{video_id: string; status: string}>(`${API}/api/videos`, form)
  return data
}
export async function getJobStatus(id: string) {
  const { data } = await axios.get<JobStatus>(`${API}/api/videos/${id}/status`)
  return data
}
export async function getAnalysis(id: string) {
  const { data } = await axios.get<AnalysisResult>(`${API}/api/videos/${id}/results`)
  return data
}
export function getMediaUrl(id: string) {return `${API}/api/videos/${id}/media`}
export function getArtifactUrl(id: string, kind: string) {return `${API}/api/videos/${id}/artifacts/${kind}`}
