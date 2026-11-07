"""Run the Whisper model once and accept PCM audio from a private API backend."""

import argparse
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import BoundedSemaphore
from typing import Callable

from app.services.voice.audio import MAX_AUDIO_SECONDS, PCM_SAMPLE_BYTES, SAMPLE_RATE_HZ

MAX_PCM_BYTES = MAX_AUDIO_SECONDS * SAMPLE_RATE_HZ * PCM_SAMPLE_BYTES
logger = logging.getLogger(__name__)


def load_whisper(model_dir: Path, device: str, threads: int) -> Callable[[bytes], str]:
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

    def transcribe(pcm_s16le: bytes) -> str:
        samples = np.frombuffer(pcm_s16le, dtype="<i2").astype(np.float32) / 32768
        if not np.any(samples):
            return ""
        result = recognizer({"array": samples, "sampling_rate": SAMPLE_RATE_HZ},
                            generate_kwargs={"language": "ko", "task": "transcribe", "num_beams": 1})
        return result["text"].strip()

    return transcribe


class WhisperWorker(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], transcribe: Callable[[bytes], str]):
        super().__init__(address, WhisperHandler)
        self.transcribe = transcribe
        self.slot = BoundedSemaphore(1)


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
        if not self.server.slot.acquire(blocking=False):
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
            self.server.slot.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--threads", type=int, default=8)
    args = parser.parse_args()
    if args.threads < 1:
        parser.error("threads must be positive")
    transcribe = load_whisper(args.model_dir, args.device, args.threads)
    with WhisperWorker((args.host, args.port), transcribe) as server:
        print(f"Whisper worker ready on {args.host}:{args.port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
