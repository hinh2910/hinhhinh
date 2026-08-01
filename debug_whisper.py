"""
Debug script: compare Whisper timestamps vs actual audio energy peaks
to diagnose highlight sync offset.
"""
import sys, os, tempfile
sys.path.insert(0, '.')

from audio_engine import generate_tts_sync, align_audio_with_whisper
import av, numpy as np

sample_rate = 44100
tmp = os.path.join(tempfile.gettempdir(), 'debug_tts.mp3')
text = "I'd like to double-check my reservation before I check in."

print(f"Generating TTS at -13% for: '{text}'")
generate_tts_sync(text, voice='en-US-AvaNeural', rate='-13%', output_path=tmp)

# Load actual audio
container = av.open(tmp)
resampler = av.AudioResampler(format='flt', layout='mono', rate=sample_rate)
samples = []
for frame in container.decode(audio=0):
    for r in resampler.resample(frame):
        samples.append(r.to_ndarray())
audio = np.concatenate(samples, axis=1).flatten()
actual_dur = len(audio) / sample_rate
print(f"Actual audio duration: {actual_dur:.3f}s\n")

# Get Whisper timestamps
words = align_audio_with_whisper(tmp)
print(f"Whisper detected {len(words)} words from text with {len(text.split())} words:")
print(f"{'IDX':<5} {'START':>8} {'END':>8} {'WORD'}")
print("-" * 40)
for i, w in enumerate(words):
    print(f"{i:<5} {w['start']:>8.3f} {w['end']:>8.3f}  '{w['word']}'")

print()
# Check energy peaks around each Whisper word start
print("Energy check: RMS energy 30ms before vs after Whisper word start")
print(f"{'IDX':<5} {'WHISPER_START':>14} {'ENERGY_BEFORE':>14} {'ENERGY_AT':>12} {'DELTA_ms':>10}")
print("-" * 60)
window = int(0.030 * sample_rate)
for i, w in enumerate(words):
    ws = int(w['start'] * sample_rate)
    before_start = max(0, ws - window)
    at_start = min(len(audio), ws + window)
    energy_before = np.sqrt(np.mean(audio[before_start:ws]**2)) if ws > 0 else 0
    energy_at = np.sqrt(np.mean(audio[ws:at_start]**2)) if at_start > ws else 0
    # Find where energy actually rises (scan back from Whisper start)
    best_onset = ws
    for scan in range(ws, max(0, ws - int(0.3*sample_rate)), -1):
        chunk = audio[max(0,scan-window):scan]
        if len(chunk) > 0 and np.sqrt(np.mean(chunk**2)) < energy_at * 0.5:
            best_onset = scan
            break
    delta_ms = (ws - best_onset) / sample_rate * 1000
    print(f"{i:<5} {w['start']:>14.3f} {energy_before:>14.4f} {energy_at:>12.4f} {delta_ms:>10.1f}ms early")
