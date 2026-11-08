"""Measure local Whisper transcription on labelled Korean kiosk utterances."""

import argparse
import json
import platform
import statistics
import sys
import time
import unicodedata
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SAMPLES = ROOT / "recordings" / "whisper-benchmark"
MODEL_ID = "openai/whisper-large-v3-turbo"
MODEL_REVISION = "41f01f3fe87f28c78e2fbf8b568835947dd65ed9"
SAMPLE_RATE = 16_000


def normalize(text):
    return "".join(char for char in unicodedata.normalize("NFKC", text).casefold() if char.isalnum())


def edit_distance(reference, hypothesis):
    previous = list(range(len(hypothesis) + 1))
    for index, expected in enumerate(reference, 1):
        current = [index]
        for offset, actual in enumerate(hypothesis, 1):
            current.append(min(previous[offset] + 1, current[-1] + 1, previous[offset - 1] + (expected != actual)))
        previous = current
    return previous[-1]


def read_wave(path):
    import numpy as np

    with wave.open(str(path), "rb") as stream:
        if (stream.getframerate(), stream.getnchannels(), stream.getsampwidth()) != (SAMPLE_RATE, 1, 2):
            raise ValueError(f"Expected 16 kHz mono PCM16 WAV: {path}")
        return np.frombuffer(stream.readframes(stream.getnframes()), dtype="<i2").astype(np.float32) / 32768


def transcribe(recognizer, audio):
    start = time.perf_counter()
    result = recognizer({"array": audio, "sampling_rate": SAMPLE_RATE},
                        generate_kwargs={"language": "ko", "task": "transcribe", "num_beams": 1})
    return result["text"].strip(), time.perf_counter() - start


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=ROOT / "models" / "whisper-large-v3-turbo")
    parser.add_argument("--audio-dir", type=Path, default=SAMPLES)
    parser.add_argument("--report", type=Path, default=SAMPLES / "report.json")
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--warm-repeats", type=int, default=2)
    args = parser.parse_args()
    if args.threads < 1 or args.warm_repeats < 1:
        parser.error("threads and warm-repeats must be positive")

    import_start = time.perf_counter()
    import psutil
    import torch
    import transformers
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
    import_seconds = time.perf_counter() - import_start

    torch.set_num_threads(args.threads)
    torch.set_num_interop_threads(1)
    samples = json.loads(Path(__file__).with_name("korean_samples.json").read_text(encoding="utf-8"))
    waveforms = [read_wave(args.audio_dir / f"{sample['id']}.wav") for sample in samples]
    available_before_load = psutil.virtual_memory().available

    start = time.perf_counter()
    processor = AutoProcessor.from_pretrained(args.model_dir, local_files_only=True)
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        args.model_dir, dtype=torch.float32, local_files_only=True, use_safetensors=True,
    )
    recognizer = pipeline("automatic-speech-recognition", model=model, tokenizer=processor.tokenizer,
                          feature_extractor=processor.feature_extractor, device=-1)
    load_seconds = time.perf_counter() - start
    print(f"Model loaded in {load_seconds:.2f} s", file=sys.stderr, flush=True)
    first_text, first_seconds = transcribe(recognizer, waveforms[0])
    print(f"First transcription completed in {first_seconds:.2f} s", file=sys.stderr, flush=True)

    for sample, audio in zip(samples, waveforms):
        calls = [transcribe(recognizer, audio) for _ in range(args.warm_repeats)]
        hypothesis = normalize(calls[0][0])
        reference = normalize(sample["reference"])
        sample.update({
            "audio_seconds": len(audio) / SAMPLE_RATE,
            "transcripts": [text for text, _ in calls],
            "warm_seconds": [elapsed for _, elapsed in calls],
            "exact": hypothesis == reference,
            "keyword_match": normalize(sample["keyword"]) in hypothesis,
            "edits": edit_distance(reference, hypothesis),
            "reference_characters": len(reference),
        })
        print(f"Measured {sample['id']}", file=sys.stderr, flush=True)

    warm_seconds = [elapsed for sample in samples for elapsed in sample["warm_seconds"]]
    report = {
        "model": MODEL_ID, "revision": MODEL_REVISION, "python": platform.python_version(),
        "torch": torch.__version__, "transformers": transformers.__version__,
        "device": "cpu", "dtype": "float32", "threads": args.threads,
        "available_memory_gib_before_load": available_before_load / 2**30,
        "process_rss_gib_at_finish": psutil.Process().memory_info().rss / 2**30,
        "import_seconds": import_seconds, "load_seconds": load_seconds,
        "first_seconds": first_seconds, "first_transcript": first_text,
        "warm_median_seconds": statistics.median(warm_seconds),
        "warm_min_seconds": min(warm_seconds), "warm_max_seconds": max(warm_seconds),
        "exact_count": sum(sample["exact"] for sample in samples),
        "keyword_count": sum(sample["keyword_match"] for sample in samples),
        "character_error_rate": sum(sample["edits"] for sample in samples) / sum(sample["reference_characters"] for sample in samples),
        "samples": samples,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    output = json.dumps(report, ensure_ascii=False, indent=2)
    args.report.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
