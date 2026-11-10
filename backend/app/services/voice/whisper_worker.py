"""Run the Whisper model once and accept PCM audio from a private API backend."""

import argparse
import json
import logging
from concurrent.futures import Future, ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import BoundedSemaphore, Condition
from typing import Callable

from app.services.voice.audio import MAX_AUDIO_SECONDS, PCM_SAMPLE_BYTES, SAMPLE_RATE_HZ

MAX_PCM_BYTES = MAX_AUDIO_SECONDS * SAMPLE_RATE_HZ * PCM_SAMPLE_BYTES
BATCH_WINDOW_SECONDS = 0.15
logger = logging.getLogger(__name__)


def load_whisper(model_dir: Path, device: str, threads: int) -> Callable[[list[bytes]], list[str]]:
    import numpy as np
    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

    torch.set_num_threads(threads)
    torch.set_num_interop_threads(1)
    dtype = torch.float16 if device == "cuda" else torch.float32
    processor = AutoProcessor.from_pretrained(model_dir, local_files_only=True)
    model = AutoModelForSpeechSeq2Seq.from_pretrained(model_dir, dtype=dtype, local_files_only=True, use_safetensors=True)
    recognizer = pipeline("automatic-speech-recognition", model=model, tokenizer=processor.tokenizer,
                          feature_extractor=processor.feature_extractor, device=0 if device == "cuda" else -1)

    def transcribe_batch(recordings: list[bytes]) -> list[str]:
        transcripts = [""] * len(recordings)
        inputs = []
        positions = []
        for index, pcm_s16le in enumerate(recordings):
            samples = np.frombuffer(pcm_s16le, dtype="<i2").astype(np.float32) / 32768
            if np.any(samples):
                inputs.append({"array": samples, "sampling_rate": SAMPLE_RATE_HZ})
                positions.append(index)

        if inputs:
            results = recognizer(
                inputs, batch_size=len(inputs), num_workers=0,
                generate_kwargs={"language": "ko", "task": "transcribe", "num_beams": 1},
            )
            for index, result in zip(positions, results, strict=True):
                transcripts[index] = result["text"].strip()
        return transcripts

    return transcribe_batch


class WhisperWorker(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], transcribe_batch: Callable[[list[bytes]], list[str]],
                 batch_size: int = 2):
        self._inference = ThreadPoolExecutor(max_workers=1)
        super().__init__(address, WhisperHandler)
        self.slots = BoundedSemaphore(batch_size)
        self._batch_size = batch_size
        self._transcribe_batch = transcribe_batch
        self._batch_ready = Condition()
        self._pending: list[tuple[bytes, Future[str]]] = []

    def transcribe(self, pcm: bytes) -> str:
        result: Future[str] = Future()
        with self._batch_ready:
            # Only the first pending request schedules inference for the group.
            if not self._pending:
                self._inference.submit(self._process_batch)
            self._pending.append((pcm, result))
            self._batch_ready.notify()
        return result.result()

    def _process_batch(self):
        with self._batch_ready:
            self._batch_ready.wait_for(lambda: len(self._pending) == self._batch_size, timeout=BATCH_WINDOW_SECONDS)
            batch, self._pending = self._pending, []
        recordings, responses = zip(*batch)
        try:
            transcripts = self._transcribe_batch(list(recordings))
            if len(transcripts) != len(responses):
                raise ValueError("Unexpected number of Whisper transcripts")
        except Exception as error:
            for response in responses:
                response.set_exception(error)
        else:
            for response, transcript in zip(responses, transcripts):
                response.set_result(transcript)

    def server_close(self):
        super().server_close()
        self._inference.shutdown()


class WhisperHandler(BaseHTTPRequestHandler):
    server: WhisperWorker

    def _respond(self, status: int, payload: dict):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        if self.path != "/transcribe":
            self._respond(404, {"error": "NOT_FOUND"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            size = 0
        if (self.headers.get_content_type() != "application/octet-stream"
                or not 0 < size <= MAX_PCM_BYTES or size % PCM_SAMPLE_BYTES):
            self._respond(400, {"error": "INVALID_PCM"})
            return
        if not self.server.slots.acquire(blocking=False):
            self._respond(503, {"error": "WORKER_BUSY"})
            return
        try:
            self.connection.settimeout(5)
            pcm = self.rfile.read(size)
            if len(pcm) != size:
                self._respond(400, {"error": "INVALID_PCM"})
                return
            self._respond(200, {"transcript": self.server.transcribe(pcm)})
        except TimeoutError:
            self._respond(408, {"error": "UPLOAD_TIMEOUT"})
        except Exception as error:
            logger.error("Whisper transcription failed (%s)", type(error).__name__)
            self._respond(500, {"error": "TRANSCRIPTION_FAILED"})
        finally:
            self.server.slots.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--batch-size", type=int, choices=(1, 2), default=2,
                        help="Maximum simultaneous recordings per model (default: 2)")
    args = parser.parse_args()
    if args.threads < 1:
        parser.error("threads must be positive")
    transcribe_batch = load_whisper(args.model_dir, args.device, args.threads)
    with WhisperWorker((args.host, args.port), transcribe_batch, args.batch_size) as server:
        print(f"Whisper worker ready on {args.host}:{args.port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
