from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
import shutil

from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from .config import UPLOAD_DIR, STORAGE_DIR, MAX_UPLOAD_BYTES, ENABLE_DEPTH, ENABLE_OCR
from .store import init_db, create_job, get_job, delete_job
from .pipeline import analyze_job, warm_up_models
from .video import inspect_video


@asynccontextmanager
async def lifespan(app: FastAPI):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    init_db()
    warm_up_models()
    yield


app = FastAPI(title='Video Forensics Research API', lifespan=lifespan)
app.add_middleware(CORSMiddleware,
                   allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
                   allow_credentials=False, allow_methods=['GET','POST','DELETE'], allow_headers=['*'])


@app.get('/api/health')
def health():
    return {'status': 'ok', 'detectors': {'text_consistency': ENABLE_OCR,
            'depth_consistency': ENABLE_DEPTH, 'background_motion': True, 'optical_flow': True, 'color_consistency': True}}


@app.post('/api/videos', status_code=202)
async def upload_video(background_tasks: BackgroundTasks, video: UploadFile = File(...)):
    allowed = {'.mp4', '.mov', '.m4v', '.webm', '.avi'}
    suffix = Path(video.filename or '').suffix.lower()
    if suffix not in allowed:
        raise HTTPException(400, 'Only MP4, MOV, M4V, WEBM and AVI videos are supported')
    job_id = uuid4().hex
    path = UPLOAD_DIR / f'{job_id}{suffix}'
    size = 0
    try:
        with open(path, 'wb') as out:
            while chunk := await video.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, 'Maximum upload size is 100 MB')
                out.write(chunk)
        try:
            inspect_video(path)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        create_job(job_id, Path(video.filename or 'video').name, path)
        background_tasks.add_task(analyze_job, job_id)
        return {'video_id': job_id, 'status': 'queued'}
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await video.close()


@app.get('/api/videos/{video_id}/status')
def status(video_id: str):
    job = get_job(video_id)
    if job is None:
        raise HTTPException(404, 'Analysis not found')
    return {'video_id': video_id, 'status': job['status'], 'error': job['error']}


@app.get('/api/videos/{video_id}/results')
def results(video_id: str):
    job = get_job(video_id)
    if job is None:
        raise HTTPException(404, 'Analysis not found')
    if job['status'] != 'completed':
        raise HTTPException(409, f'Analysis not completed ({job["status"]})')
    return {'video_id': video_id, **job['result']}


@app.get('/api/videos/{video_id}/media')
def media(video_id: str):
    job = get_job(video_id)
    if job is None:
        raise HTTPException(404, 'Video not found')
    return FileResponse(job['path'], media_type='video/mp4' if job['path'].endswith('.mp4') else None)


@app.delete('/api/videos/{video_id}', status_code=204)
def remove(video_id: str):
    job = get_job(video_id)
    if job is None:
        raise HTTPException(404, 'Video not found')
    if job['status'] in ('queued', 'running'):
        raise HTTPException(409, 'Cannot delete while analysis is running')
    Path(job['path']).unlink(missing_ok=True)
    shutil.rmtree(STORAGE_DIR / 'artifacts' / video_id, ignore_errors=True)
    delete_job(video_id)


@app.get('/api/videos/{video_id}/artifacts/{name}')
def artifact(video_id: str, name: str):
    job = get_job(video_id)
    if job is None or job['status'] != 'completed':
        raise HTTPException(404, 'Analysis artifact not found')
    if name not in {'first_frame', 'optical_flow', 'depth_map', 'gamma_shadows', 'saturation_boost', 'optical_flow_evidence', 'facial_consistency_evidence'} or name not in job['result'].get('artifacts', []):
        raise HTTPException(404, 'Analysis artifact not found')
    path = STORAGE_DIR / 'artifacts' / video_id / f'{name}.jpg'
    if not path.is_file():
        raise HTTPException(404, 'Analysis artifact not found')
    return FileResponse(path, media_type='image/jpeg')
