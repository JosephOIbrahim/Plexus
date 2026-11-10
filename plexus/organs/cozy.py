"""The Cozy organ, written new against ComfyUI's own HTTP API. The only file under plexus/ that may name engine words."""

from __future__ import annotations

import copy
import hashlib
import http.client
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
MIN_CALL_S = 0.5


def _json(data: bytes, route: str) -> dict:
    try:
        return json.loads(data.decode('utf-8'))
    except ValueError as e:
        raise OrganError(f"{route}: the engine's reply is not JSON") from e


def _call_timeout(deadline: float | None) -> float:
    if deadline is None:
        return HTTP_TIMEOUT_S
    return max(MIN_CALL_S, min(HTTP_TIMEOUT_S, deadline - time.monotonic()))


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
        if type(job.seed) is not int:
            raise OrganError(f"Seed {job.seed!r} is not an int")
        if job.colorspace not in COLORSPACES:
            raise OrganError(f"Colorspace {job.colorspace} is not in {COLORSPACES}")
        if not (INT64_MIN <= job.seed <= INT64_MAX):
            raise OrganError(f"Seed {job.seed} is outside the range [{INT64_MIN}, {INT64_MAX}]")

        graph = copy.deepcopy(job.graph)
        seed_written = False
        for node_id, node in graph.items():
            if not isinstance(node, dict) or not isinstance(node.get('inputs'), dict) or 'class_type' not in node:
                raise OrganError(f"Node {node_id} has no inputs or no class_type")
            for name in SEED_INPUTS:
                if isinstance(node['inputs'].get(name), int):
                    node['inputs'][name] = job.seed
                    seed_written = True

        for node in graph.values():
            if node['class_type'] not in self.capabilities():
                raise OrganError(f"Engine does not support node class {node['class_type']}")

        try:
            body = json.dumps({'prompt': graph}).encode('utf-8')
        except (TypeError, ValueError) as e:
            raise OrganError(f"The graph holds a value JSON cannot write: {e}") from e

        try:
            req = urllib.request.Request(self._endpoint + '/prompt', data=body)
            req.add_header('Content-Type', 'application/json')
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as response:
                result = _json(response.read(), '/prompt')
        except urllib.error.HTTPError as e:
            try:
                words = e.read().decode('utf-8', 'replace')
            except (OSError, http.client.HTTPException):
                words = ''
            raise OrganError(f"/prompt refused the graph ({e.code}): {words}") from e
        except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
            raise OrganError(f"Failed to submit job to {self._endpoint}/prompt: {str(e)}")

        prompt_id = result.get('prompt_id') if isinstance(result, dict) else None
        if not isinstance(prompt_id, str) or not prompt_id:
            raise OrganError("/prompt: the engine's reply holds no prompt_id that is a string")
        self._jobs[job.correlation_id] = _Submitted(prompt_id, job.seed if seed_written else None, job.colorspace)
        return JobHandle(job.correlation_id)

    def stream(self, handle: JobHandle) -> Iterator[Progress]:
        job = self._jobs.get(handle.correlation_id)
        if not job:
            raise OrganError(f"Unknown job handle with correlation id {handle.correlation_id}")
        deadline = time.monotonic() + self._deadline_s
        while True:
            entry = self._history_entry(job.prompt_id, deadline)
            if time.monotonic() > deadline:
                raise OrganError("Job timed out")
            if entry is None:
                yield Progress(handle.correlation_id, 'queued')
                time.sleep(self._poll_s)
                continue
            status = entry.get('status', {}).get('status_str')
            if status == 'error':
                yield Progress(handle.correlation_id, 'failed')
                return
            yield Progress(handle.correlation_id, 'done')
            return

    def result(self, handle: JobHandle) -> AssetRecord:
        job = self._jobs.get(handle.correlation_id)
        if not job:
            raise OrganError(f"Unknown job handle with correlation id {handle.correlation_id}")
        deadline = time.monotonic() + self._deadline_s
        while True:
            entry = self._history_entry(job.prompt_id, deadline)
            if time.monotonic() > deadline:
                raise OrganError("Job timed out")
            if entry is None:
                time.sleep(self._poll_s)
                continue
            status = entry.get('status', {}).get('status_str')
            if status == 'error':
                raise OrganError("the engine failed this job")
            break

        # Find the first image with type 'output'
        output_image = None
        outputs = entry.get('outputs')
        if not isinstance(outputs, dict):
            raise OrganError("the engine's history entry holds no outputs")
        for node_outputs in outputs.values():
            images = node_outputs.get('images', []) if isinstance(node_outputs, dict) else None
            if not isinstance(images, list) or not all(isinstance(img, dict) for img in images):
                raise OrganError("the engine's history entry holds outputs that are not objects with a list of image objects")
            for img in images:
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
            with urllib.request.urlopen(self._endpoint + route, timeout=_call_timeout(None)) as response:
                result = _json(response.read(), route)
        except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
            raise OrganError(f"Failed to GET {self._endpoint}{route}: {str(e)}")
        if not isinstance(result, dict):
            raise OrganError(f"{route}: the engine's reply is not a JSON object")
        return result

    def _history_entry(self, prompt_id: str, deadline: float | None = None) -> dict | None:
        """This job's entry in /history/<prompt_id>, or None while the engine's history does not have it or the engine cannot answer."""
        try:
            with urllib.request.urlopen(self._endpoint + f'/history/{prompt_id}', timeout=_call_timeout(deadline)) as response:
                result = _json(response.read(), '/history')
                entry = result.get(prompt_id) if isinstance(result, dict) else None
                if entry is not None and (not isinstance(entry, dict) or not isinstance(entry.get('status') or {}, dict)):
                    raise OrganError("/history: the engine's entry for this job, or its status, is not a JSON object")
                return entry
        except urllib.error.HTTPError as e:
            if 500 <= e.code:
                # 5xx error, treat as not yet
                return None
            elif e.code == 404:
                # 404 means the history entry doesn't exist yet
                raise OrganError(f"/history: {e}")
            else:
                raise OrganError(f"/history: {e}")
        except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
            # URLError or OSError means no connection or timeout
            return None
        except http.client.HTTPException as e:
            raise OrganError(f"/history: the engine's reply is not HTTP the organ can read ({type(e).__name__})") from e

    def _fetch_file(self, image: dict) -> Path:
        """GET /view for one output and write it under output_dir. Returns the path of the file on disk."""
        filename = image.get('filename')
        if not isinstance(filename, str):
            raise OrganError("the engine's output image names no filename that is a string")
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
        except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
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
        try:
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
        except (KeyError, TypeError) as e:
            raise OrganError(f"/system_stats: the engine's reply lacks a field the fingerprint reads: {e!r}") from e

        fingerprint_json = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.sha256(fingerprint_json.encode()).hexdigest()
