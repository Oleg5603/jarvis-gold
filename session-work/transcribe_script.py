import sys
from faster_whisper import WhisperModel

model = WhisperModel("base", device="cpu", compute_type="int8")
segments, info = model.transcribe(sys.argv[1], language="ru", vad_filter=True)

out_path = sys.argv[2]
with open(out_path, "w", encoding="utf-8") as f:
    for seg in segments:
        line = f"[{seg.start:.0f}s] {seg.text.strip()}"
        f.write(line + "\n")
        f.flush()
        print(line, flush=True)
print("DONE", flush=True)
