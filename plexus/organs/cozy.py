"""The Cozy organ, written new against ComfyUI's own HTTP API. The only file under plexus/ that may name engine words."""

from __future__ import annotations

import copy
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from plexus.organs.protocol import AssetRecord, Job, JobHandle, Organ, OrganError, OrganProfile, Progress

ORGAN_ID = "cozy"
ORGAN_VERSION = "0.1.0"
SEED_INPUTS = ("seed", "noise_seed")
COLORSPACES = ("acescg", "srgb", "linear", "raw")
INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1
HTTP_TIMEOUT_S = 60.0


@dataclass(frozen=True)
class _Submitted:
    """What the organ remembers of one job. It stays in here: core never sees the engine's id."""

    prompt_id: str
    seed: int | None
    colorspace: str


class CozyOrgan(Organ):
    def __init__(self, endpoint: str, output_dir: Path, *, poll_s: float = 0.2, deadline_s: float = 3600.0):
        self._endpoint = endpoint.rstrip('/')
        self._output_dir = Path(output_dir).resolve()
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._poll_s = poll_s
        self._deadline_s = deadline_s
        self._jobs = {}
        self._nodes = None

    def profile(self) -> OrganProfile:
        return OrganProfile(ORGAN_ID, 'comfyui', self._endpoint, self.capabilities(), 'free')

    def capabilities(self) -> list[str]:
        if self._nodes is None:
            info = self._get_json('/object_info')
            self._nodes = sorted(info.keys())
        return self._nodes

    def submit(self, job: Job) -> JobHandle:
        if job.correlation_id in self._jobs:
            raise OrganError(f"Job with correlation id {job.correlation_id} already submitted")
        if job.colorspace not in COLORSPACES:
            raise OrganError(f"Colorspace {job.colorspace} is not in {COLORSPACES}")
        if not (INT64_MIN <= job.seed <= INT64_MAX):
            raise OrganError(f"Seed {job.seed} is outside the range [{INT64_MIN}, {INT64_MAX}]")

        graph = copy.deepcopy(job.graph)
        seed_written = False
        for node in graph.values():
            for name in SEED_INPUTS:
                if isinstance(node['inputs'].get(name), int):
                    node['inputs'][name] = job.seed
                    seed_written = True

        for node in graph.values():
            if node['class_type'] not in self.capabilities():
                raise OrganError(f"Engine does not support node class {node['class_type']}")

        try:
            body = json.dumps({'prompt': graph}).encode('utf-8')
            req = urllib.request.Request(self._endpoint + '/prompt', data=body)
            req.add_header('Content-Type', 'application/json')
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as response:
                result = json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            # For 4xx errors, include the body in the error message
            if 400 <= e.code < 500:
                try:
                    error_body = json.loads(e.read().decode('utf-8'))
                    raise OrganError(f"Failed to submit job to {self._endpoint}/prompt: {error_body}")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    raise OrganError(f"Failed to submit job to {self._endpoint}/prompt: HTTP Error {e.code}: Bad Request")
            else:
                raise OrganError(f"Failed to submit job to {self._endpoint}/prompt: HTTP Error {e.code}: {str(e)}")
        except (urllib.error.URLError, OSError) as e:
            raise OrganError(f"Failed to submit job to {self._endpoint}/prompt: {str(e)}")

        prompt_id = result['prompt_id']
        self._jobs[job.correlation_id] = _Submitted(prompt_id, job.seed if seed_written else None, job.colorspace)
        return JobHandle(job.correlation_id)

    def stream(self, handle: JobHandle) -> Iterator[Progress]:
        job = self._jobs.get(handle.correlation_id)
        if not job:
            raise OrganError(f"Unknown job handle with correlation id {handle.correlation_id}")
        deadline = time.monotonic() + self._deadline_s
        while True:
            entry = self._history_entry(job.prompt_id)
            if time.monotonic() > deadline:
                raise OrganError("Job timed out")
            if entry is None:
                time.sleep(self._poll_s)
                continue
            status = entry.get('status', {}).get('status_str')
            if status == 'error':
                yield Progress(handle.correlation_id, 'failed')
                return
            state = 'done' if status == 'success' else 'queued'
            yield Progress(handle.correlation_id, state)
            if state == 'done':
                break

    def result(self, handle: JobHandle) -> AssetRecord:
        job = self._jobs.get(handle.correlation_id)
        if not job:
            raise OrganError(f"Unknown job handle with correlation id {handle.correlation_id}")
        deadline = time.monotonic() + self._deadline_s
        while True:
            entry = self._history_entry(job.prompt_id)
            if time.monotonic() > deadline:
                raise OrganError("Job timed out")
            if entry is None:
                time.sleep(self._poll_s)
                continue
            status = entry.get('status', {}).get('status_str')
            if status == 'error':
                raise OrganError(f"Job failed with error status: {entry}")
            break

        # Find the first image with type 'output'
        output_image = None
        for node_outputs in entry['outputs'].values():
            for img in node_outputs.get('images', []):
                if img.get('type') == 'output':
                    output_image = img
                    break
            if output_image:
                break

        if not output_image:
            raise OrganError("No output image found in job result")

        path = self._fetch_file(output_image)
        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()

        metadata = {
            'engine': ORGAN_ID,
            'engineJobId': job.prompt_id,
            'envFingerprint': self._env_fingerprint(),
            'organVersion': ORGAN_VERSION,
            'modelHashes': [],
            'colorspace': job.colorspace,
            'createdAt': datetime.now(timezone.utc).isoformat(timespec='seconds')
        }
        if job.seed is not None:
            metadata['seed'] = job.seed

        return AssetRecord(path, sha256, metadata)

    def _get_json(self, route: str) -> dict:
        """GET the endpoint plus route, as JSON. A URL or HTTP failure is an OrganError."""
        try:
            with urllib.request.urlopen(self._endpoint + route, timeout=HTTP_TIMEOUT_S) as response:
                return json.loads(response.read().decode())
        except (urllib.error.URLError, OSError) as e:
            raise OrganError(f"Failed to GET {self._endpoint}{route}: {str(e)}")

    def _history_entry(self, prompt_id: str) -> dict | None:
        """This job's entry in /history/<prompt_id>, or None while the engine's history does not have it or the engine cannot answer."""
        try:
            with urllib.request.urlopen(self._endpoint + f'/history/{prompt_id}', timeout=HTTP_TIMEOUT_S) as response:
                result = json.loads(response.read().decode())
                return result.get(prompt_id)
        except urllib.error.HTTPError as e:
            if 500 <= e.code:
                # 5xx error, treat as not yet
                return None
            elif e.code == 404:
                # 404 means the history entry doesn't exist yet
                raise OrganError(f"Failed to GET /history/{prompt_id}: HTTP Error {e.code}: Not Found")
            else:
                raise OrganError(f"Failed to GET /history/{prompt_id}: HTTP Error {e.code}: {str(e)}")
        except (urllib.error.URLError, OSError) as e:
            # URLError or OSError means no connection or timeout
            return None

    def _fetch_file(self, image: dict) -> Path:
        """GET /view for one output and write it under output_dir. Returns the path of the file on disk."""
        filename = image['filename']
        subfolder = image.get('subfolder', '')
        type_ = image.get('type', 'output')
        query = urllib.parse.urlencode({
            'filename': filename,
            'subfolder': subfolder,
            'type': type_
        })
        url = self._endpoint + '/view?' + query
        try:
            with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_S) as response:
                data = response.read()
        except (urllib.error.URLError, OSError) as e:
            raise OrganError(f"Failed to fetch image {filename}: {str(e)}")

        # Generate a unique filename to avoid overwrites
        unique_filename = f"{uuid.uuid4().hex}_{Path(filename).name}"
        path = self._output_dir / unique_filename
        path.write_bytes(data)
        return path

    def _env_fingerprint(self) -> str:
        """SHA-256 hex over the engine's environment, from /system_stats and /object_info."""
        system = self._get_json('/system_stats')
        info = self._get_json('/object_info')

        # Hash only the required fields
        fingerprint_data = {
            'system': {
                'os': system['system']['os'],
                'comfyui_version': system['system']['comfyui_version'],
                'python_version': system['system']['python_version'],
                'pytorch_version': system['system']['pytorch_version']
            },
            'devices': [
                {'name': d['name'], 'type': d['type']} for d in system['devices']
            ],
            'node_classes': sorted(info.keys())
        }

        fingerprint_json = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.sha256(fingerprint_json.encode()).hexdigest()
