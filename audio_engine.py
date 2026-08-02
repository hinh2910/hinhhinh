import os
import sys
import re
import glob
import random
import asyncio
import tempfile
import numpy as np
import soundfile as sf
import edge_tts
import av
from faster_whisper import WhisperModel

# Initialize Whisper Model (GPU preferred)
whisper_model = None

def clean_tts_speech(txt):
    if not txt: return ""
    txt = re.sub(r'_{2,}', '', txt)
    txt = re.sub(r'\.{3,}', '', txt)
    return txt.strip()

PRAISE_PHRASES = [
    "Great job!",
    "Well done!",
    "Nice work!",
    "Perfect!",
    "Awesome!",
    "Keep it going!"
]



def mix_bgm_into_section(section_audio, sample_rate=44100, volume=0.08):
    """
    Mix background music from video/*no-copyright-music*.mp3 into section_audio at soft volume (8%).
    Strictly excludes sound effects (clock ticking, sfx) from BGM selection!
    """
    all_mp3s = glob.glob("video/*.mp3")
    # Only select background music files
    bgm_files = [
        f for f in all_mp3s 
        if ("music" in f.lower() or "bgm" in f.lower() or "dreamy" in f.lower() or "gameplay" in f.lower() or "thing" in f.lower())
        and not any(k in f.lower() for k in ["clock", "tick", "sfx", "effect"])
    ]
    if not bgm_files:
        return section_audio
    
    bgm_path = random.choice(bgm_files)
    try:
# av imported at top
        container = av.open(bgm_path)
        resampler = av.AudioResampler(format='flt', layout='mono', rate=sample_rate)
        bgm_samples = []
        for frame in container.decode(audio=0):
            resampled = resampler.resample(frame)
            for r in resampled:
                bgm_samples.append(r.to_ndarray())
        if not bgm_samples:
            return section_audio
            
        bgm_audio = np.concatenate(bgm_samples, axis=1).flatten()
        bgm_audio = bgm_audio * volume
        
        needed_len = len(section_audio)
        if len(bgm_audio) > needed_len:
            max_start = len(bgm_audio) - needed_len
            rand_start = random.randint(0, max_start)
            bgm_slice = bgm_audio[rand_start : rand_start + needed_len]
        else:
            n_repeats = (needed_len // len(bgm_audio)) + 1
            bgm_audio = np.tile(bgm_audio, n_repeats)
            bgm_slice = bgm_audio[:needed_len]
            
        return section_audio + bgm_slice
    except Exception as e:
        print(f"Warning mixing BGM {bgm_path}: {e}")
        return section_audio

def get_whisper_model():
    global whisper_model
    if whisper_model is None:
        try:
            print("Loading Faster-Whisper model on CUDA (GPU)...")
            whisper_model = WhisperModel("base", device="cuda", compute_type="float16")
            print("Faster-Whisper CUDA model loaded successfully.")
        except Exception as e:
            print(f"CUDA failed ({e}), falling back to CPU...")
            whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
            print("Faster-Whisper CPU model loaded.")
    return whisper_model

def get_pcm_audio(mp3_path, sample_rate=44100):
    """Load MP3 file and return PCM audio as a flat NumPy array.
    Uses PyAV to decode and resample to mono float32.
    """
    container = av.open(mp3_path)
    resampler = av.AudioResampler(format='flt', layout='mono', rate=sample_rate)
    audio_samples = []
    for frame in container.decode(audio=0):
        resampled = resampler.resample(frame)
        for r in resampled:
            audio_samples.append(r.to_ndarray())
    if audio_samples:
        return np.concatenate(audio_samples, axis=1).flatten()
    return np.zeros(0, dtype=np.float32)

def compute_leading_silence(mp3_p, sample_rate=44100):
    """Calculate leading silence (encoder delay) in seconds for an MP3.
    It compares the total PCM duration with the end timestamp of the last
    Whisper‑detected word. Returns a non‑negative offset.
    """
    audio = get_pcm_audio(mp3_p, sample_rate)
    total_dur = len(audio) / sample_rate
    try:
        w_list = align_audio_with_whisper(mp3_p)
        if w_list:
            last_end = max(w["end"] for w in w_list)
            return max(0.0, total_dur - last_end)
    except Exception as e:
        print(f"Whisper align warning in compute_leading_silence: {e}")
    return 0.0

def mix_sfx(audio_buffer, sfx_name, timestamp_sec, sample_rate=44100, volume=0.35):
    """
    Mix sound effect WAV audio from assets/sfx/ into main audio_buffer at specific timestamp.
    """
    sfx_path = os.path.join("assets", "sfx", f"{sfx_name}.wav")
    if not os.path.exists(sfx_path):
        return audio_buffer
    try:
        sfx_data, _ = sf.read(sfx_path)
        if len(sfx_data.shape) > 1:
            sfx_data = sfx_data.mean(axis=1)
        sfx_data = sfx_data * volume
        
        start_idx = int(timestamp_sec * sample_rate)
        end_idx = start_idx + len(sfx_data)
        
        if end_idx < len(audio_buffer):
            audio_buffer[start_idx:end_idx] += sfx_data[:end_idx - start_idx]
        elif start_idx < len(audio_buffer):
            rem = len(audio_buffer) - start_idx
            audio_buffer[start_idx:] += sfx_data[:rem]
    except Exception as e:
        print(f"Warning mixing SFX {sfx_name}: {e}")
    return audio_buffer

def strip_emojis(text):
    """
    Remove emoji icons (e.g. 🚩, 🌍, 🏆) from text so Edge-TTS and Pillow render clean text.
    """
    if not text:
        return ""
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"
        "\U0001f300-\U0001f5ff"
        "\U0001f680-\U0001f6ff"
        "\U0001f1e0-\U0001f1ff"
        "\U00002702-\U000027b0"
        "\U000024c2-\U0001f251"
        "\U0001f900-\U0001f9ff"
        "\U0001fa70-\U0001faf6"
        "\u2600-\u26FF"
        "\u2700-\u27BF"
        "]+", flags=re.UNICODE
    )
    return emoji_pattern.sub('', text).strip()

def format_srt_time(seconds):
    """Format seconds into SRT timestamp string format: HH:MM:SS,mmm"""
    millis = int(round((seconds - int(seconds)) * 1000))
    seconds = int(seconds)
    minutes = seconds // 60
    hours = minutes // 60
    minutes = minutes % 60
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

def generate_srt_file(timeline, output_srt_path, intro_offset_sec=0.0):
    """
    Generate standard .srt Subtitle File from timeline slides.
    Supports time offset for intro.mp4 video padding.
    Handles Shadowing, Short, and Sentence video modes.
    """
    srt_entries = []
    
    for slide in timeline:
        # Skip pause sections (silent practice gaps)
        if slide.get("is_pause", False):
            continue
            
        # Get slide text depending on mode / keys present
        text = slide.get("text", "").strip()
        if not text:
            state = slide.get("active_state", "")
            if state in ["INTRO", "OUTRO"]:
                text = slide.get("explanation", "") or slide.get("main_sentence", "")
            elif state == "MAIN_SENTENCE":
                text = slide.get("main_sentence", "")
            elif state == "EXPLANATION":
                text = slide.get("explanation", "")
            elif state == "EXAMPLE_INTRO":
                text = "Example,"
            elif state in ["DEMO_Q", "PRACTICE_Q_SPEAKING"]:
                text = slide.get("dialogue_question", "")
            elif state in ["DEMO_A", "PRACTICE_A_SPEAKING"]:
                text = slide.get("dialogue_answer", "")
            elif state == "REPEAT_INSTR":
                text = "Now, repeat after me."

        text = strip_emojis(text).strip()
        if not text:
            continue

        start_t = slide.get("start_time", 0.0) + intro_offset_sec
        end_t = slide.get("end_time", 0.0) + intro_offset_sec
        
        if end_t <= start_t:
            continue
            
        srt_entries.append({
            "start_time": start_t,
            "end_time": end_t,
            "text": text
        })
        
    with open(output_srt_path, "w", encoding="utf-8") as f:
        for idx, entry in enumerate(srt_entries, 1):
            start_str = format_srt_time(entry["start_time"])
            end_str = format_srt_time(entry["end_time"])
            f.write(f"{idx}\n{start_str} --> {end_str}\n{entry['text']}\n\n")

    return output_srt_path

async def generate_single_tts(text, voice="en-GB-LibbyNeural", rate="-13%", pitch="+0Hz", output_path=None):
    """
    Generate audio file for text using SSML prosody rate & pitch.
    """
    if not output_path:
        fd, output_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
    
    # Bulletproof rate parameter validation
    if not rate or not isinstance(rate, str) or not rate.strip():
        rate = "-13%"

    rate = rate.strip()
    if not (rate.startswith("+") or rate.startswith("-")):
        rate = f"-{rate}"
    if not rate.endswith("%"):
        rate = f"{rate}%"

    clean_text = strip_emojis(text)
    if not clean_text:
        clean_text = "Let's continue."

    try:
        communicate = edge_tts.Communicate(clean_text, voice, rate=rate, pitch=pitch)
        await communicate.save(output_path)

    except Exception as e:
        print(f"TTS warning for voice {voice} ({e}), falling back to en-GB-LibbyNeural...")
        communicate = edge_tts.Communicate(clean_text, "en-GB-LibbyNeural", rate=rate, pitch=pitch)
        await communicate.save(output_path)

    return output_path

def generate_tts_sync(text, voice="en-GB-LibbyNeural", rate="+0%", pitch="+0Hz", output_path=None):
    """Synchronous wrapper for generate_single_tts."""
    return asyncio.run(generate_single_tts(text, voice=voice, rate=rate, pitch=pitch, output_path=output_path))

def create_silence(duration_sec, sample_rate=44100):
    """Generate a silent numpy audio array."""
    num_samples = int(duration_sec * sample_rate)
    return np.zeros(num_samples, dtype=np.float32)

def align_audio_with_whisper(audio_path):
    """
    Run Faster-Whisper on audio file to extract word-level timestamps.
    Returns list of dicts: [{'word': word, 'start': start_sec, 'end': end_sec}]
    """
    model = get_whisper_model()
    segments, info = model.transcribe(audio_path, word_timestamps=True)
    
    word_timestamps = []
    for seg in segments:
        if seg.words:
            for w in seg.words:
                word_timestamps.append({
                    'word': w.word.strip(),
                    'start': round(w.start, 3),
                    'end': round(w.end, 3)
                })
    return word_timestamps

def extract_encouragement_prefix(text):
    """
    Check if text starts with an encouragement phrase (e.g. 'Brilliant!', 'Awesome!').
    Returns tuple: (encouragement_prefix, clean_sentence)
    """
    patterns = [
        r"^(brilliant[!\.]?)\s*(.*)",
        r"^(excellent[!\.]?)\s*(.*)",
        r"^(awesome[!\.]?)\s*(.*)",
        r"^(amazing[!\.]?)\s*(.*)",
        r"^(great job[!\.]?)\s*(.*)",
        r"^(great[!\.]?)\s*(.*)",
        r"^(nice[!\.]?)\s*(.*)",
        r"^(fantastic[!\.]?)\s*(.*)",
        r"^(wonderful[!\.]?)\s*(.*)",
        r"^(don't give up[!\.]?)\s*(.*)",
        r"^(you're doing so well[!\.]?)\s*(.*)",
        r"^(that's 10 sentences done[!.]? keep going[!.]?)\s*(.*)"
    ]
    for pat in patterns:
        m = re.match(pat, text, flags=re.IGNORECASE)
        if m:
            prefix = m.group(1).strip()
            rest = m.group(2).strip()
            if rest:
                return prefix, rest
    return None, text

def group_words_into_slides(words, max_words=5):
    """
    Group word-level timestamps into clean 1-line subtitle slides (max 4-5 words per slide)
    so Intro & Outro subtitles display on a single line of max 5 words!
    """
    if not words:
        return []

    slides = []
    curr_words = []
    curr_text_list = []

    for w in words:
        curr_words.append(w)
        curr_text_list.append(w['word'])

        has_punct = bool(re.search(r'[\.\?!,;]', w['word']))
        if len(curr_words) >= max_words or (has_punct and len(curr_words) >= 3):
            slide_start = curr_words[0]['start']
            slide_end = curr_words[-1]['end']
            slide_text = " ".join(curr_text_list)
            slides.append({
                "start_time": slide_start,
                "end_time": slide_end,
                "text": slide_text,
                "words": list(curr_words)
            })
            curr_words = []
            curr_text_list = []

    if curr_words:
        slide_start = curr_words[0]['start']
        slide_end = curr_words[-1]['end']
        slide_text = " ".join(curr_text_list)
        slides.append({
            "start_time": slide_start,
            "end_time": slide_end,
            "text": slide_text,
            "words": list(curr_words)
        })

    return slides

def build_lesson_audio_and_timeline(sections, intro_voice="en-GB-LibbyNeural", shadowing_voice="en-GB-SoniaNeural", praise_voice="en-US-AvaNeural", rate="-10%", output_audio_path="output_lesson.wav", progress_callback=None):
    """
    Process all sections of the script.
    SINGLE CONTINUOUS PARAGRAPH BLOCK FOR INTRO & OUTRO ("text": "..."):
    - Synthesizes entire intro/outro monologues in ONE single TTS call.
    - Shadowing 3X Practice:
      * Rep 1: -10%, Rep 2: -13%, Rep 3: -17% + Host Praise ("Brilliant!", "Awesome job!").
    """
    timeline = []
    combined_audio_frames = []
    chime_sfx_times = []
    whoosh_sfx_times = []
    sample_rate = 44100
    current_time = 0.0
    
    rep_rates = ["-16%", "-10%", "-5%"]
    temp_dir = tempfile.mkdtemp(prefix="shadow_tts_")
    praise_idx = 0

    total_sections = len(sections)
    section_timestamps = {}

    for sec_idx, sec in enumerate(sections):
        sec_type = sec.get("type", "intro_story")
        items = sec.get("items", [])
        whoosh_sfx_times.append(current_time)

        # Record exact section start timestamps
        if sec_type in ["intro_story", "intro"] and "Part 1: Introduction" not in section_timestamps:
            section_timestamps["Part 1: Introduction"] = current_time
        elif sec_type in ["intro_quiz", "quiz", "questions"] and "Part 2: Question" not in section_timestamps:
            section_timestamps["Part 2: Question"] = current_time
        elif sec_type in ["shadowing_practice", "practice", "shadowing"] and "Part 3: Shadowing Practice" not in section_timestamps:
            section_timestamps["Part 3: Shadowing Practice"] = current_time
        elif sec_type in ["review", "conclusion", "outro"] and "Part 4: Conclusion" not in section_timestamps:
            section_timestamps["Part 4: Conclusion"] = current_time

        if progress_callback:
            progress_callback(f"Processing Section {sec_idx+1}/{total_sections} ({sec_type})...", round((sec_idx / max(1, total_sections)) * 0.4, 2))

        if sec_type in ["intro_story", "intro_quiz", "review"]:
            questions_list = sec.get("questions", [])
            
        if sec_type in ["intro_story", "intro_quiz", "review"]:
            questions_list = sec.get("questions", [])
            
            if questions_list:
                # -------------------------------------------------------------
                # STRUCTURED QUIZ SYNTHESIS (Part 2: Question - Starts IMMEDIATELY on Card Image)
                # -------------------------------------------------------------
                for q_idx, q in enumerate(questions_list):
                    q_num = q.get("q_num", q_idx + 1)
                    q_str = q.get("question", "")
                    oa = q.get("option_a", "")
                    ob = q.get("option_b", "")
                    oc = q.get("option_c", "")
                    od = q.get("option_d", "")
                    c_opt = str(q.get("correct_option", "A")).strip().upper()
                    exp = q.get("explanation", "")
                    is_c = q.get("is_challenge", False)
                    opt_map = {"A": oa, "B": ob, "C": oc, "D": od}
                    c_text = opt_map.get(c_opt, oa)

                    q_start_time = current_time
                    opt_times = {}
                    all_quiz_words = []

                    # 1. TTS for Question Text (Inserts 1.5s silent pause at blank ______ without saying 'blank')
                    q_full_text = f"Question {q_num}: {q_str}"
                    blank_match = re.search(r'(.*?)(?:_{2,}|\.{3,}|\[blank\])(.*)', q_full_text)

                    if blank_match:
                        p1_text = blank_match.group(1).strip()
                        p2_text = blank_match.group(2).strip()

                        # Part 1 TTS
                        tmp_q1 = os.path.join(temp_dir, f"sec_{sec_idx}_q{q_idx}_q1.mp3")
                        generate_tts_sync(strip_emojis(p1_text), voice=intro_voice, rate="-5%", pitch="+0Hz", output_path=tmp_q1)
                        container = av.open(tmp_q1)
                        resampler = av.AudioResampler(format='flt', layout='mono', rate=sample_rate)
                        samples = [r.to_ndarray() for frame in container.decode(audio=0) for r in resampler.resample(frame)]
                        q1_audio = np.concatenate(samples, axis=1).flatten() if samples else np.zeros(0, dtype=np.float32)
                        q1_dur = len(q1_audio) / sample_rate

                        raw_q1_words = align_audio_with_whisper(tmp_q1)
                        for w in raw_q1_words:
                            all_quiz_words.append({
                                'word': w['word'],
                                'start': round(current_time + w['start'], 3),
                                'end': round(current_time + w['end'], 3),
                                'part': 'question'
                            })
                        combined_audio_frames.append(q1_audio)
                        current_time += q1_dur
                        try: os.remove(tmp_q1)
                        except: pass

                        # 1.5 Second Pause at Blank Spot
                        blank_pause_dur = 1.5
                        blank_pause_audio = create_silence(blank_pause_dur, sample_rate)
                        combined_audio_frames.append(blank_pause_audio)
                        current_time += blank_pause_dur

                        # Part 2 TTS (if text exists after blank)
                        if p2_text:
                            tmp_q2 = os.path.join(temp_dir, f"sec_{sec_idx}_q{q_idx}_q2.mp3")
                            generate_tts_sync(strip_emojis(p2_text), voice=intro_voice, rate="-5%", pitch="+0Hz", output_path=tmp_q2)
                            container = av.open(tmp_q2)
                            resampler = av.AudioResampler(format='flt', layout='mono', rate=sample_rate)
                            samples = [r.to_ndarray() for frame in container.decode(audio=0) for r in resampler.resample(frame)]
                            q2_audio = np.concatenate(samples, axis=1).flatten() if samples else np.zeros(0, dtype=np.float32)
                            q2_dur = len(q2_audio) / sample_rate

                            raw_q2_words = align_audio_with_whisper(tmp_q2)
                            for w in raw_q2_words:
                                all_quiz_words.append({
                                    'word': w['word'],
                                    'start': round(current_time + w['start'], 3),
                                    'end': round(current_time + w['end'], 3),
                                    'part': 'question'
                                })
                            combined_audio_frames.append(q2_audio)
                            current_time += q2_dur
                            try: os.remove(tmp_q2)
                            except: pass
                    else:
                        tmp_q = os.path.join(temp_dir, f"sec_{sec_idx}_q{q_idx}_qtext.mp3")
                        generate_tts_sync(strip_emojis(q_full_text), voice=intro_voice, rate="-5%", pitch="+0Hz", output_path=tmp_q)
                        container = av.open(tmp_q)
                        resampler = av.AudioResampler(format='flt', layout='mono', rate=sample_rate)
                        samples = [r.to_ndarray() for frame in container.decode(audio=0) for r in resampler.resample(frame)]
                        q_audio = np.concatenate(samples, axis=1).flatten() if samples else np.zeros(0, dtype=np.float32)
                        q_dur = len(q_audio) / sample_rate

                        raw_q_words = align_audio_with_whisper(tmp_q)
                        for w in raw_q_words:
                            all_quiz_words.append({
                                'word': w['word'],
                                'start': round(current_time + w['start'], 3),
                                'end': round(current_time + w['end'], 3),
                                'part': 'question'
                            })
                        combined_audio_frames.append(q_audio)
                        current_time += q_dur
                        try: os.remove(tmp_q)
                        except: pass

                    # 2. TTS for Options A, B, C, D (Recorded with Exact Time Windows)
                    for letter, opt_val in [("A", oa), ("B", ob), ("C", oc), ("D", od)]:
                        opt_tts_str = clean_tts_speech(f"Option {letter}: {opt_val}.")
                        tmp_opt = os.path.join(temp_dir, f"sec_{sec_idx}_q{q_idx}_opt_{letter}.mp3")
                        generate_tts_sync(strip_emojis(opt_tts_str), voice=intro_voice, rate="-5%", pitch="+0Hz", output_path=tmp_opt)
                        
                        container = av.open(tmp_opt)
                        resampler = av.AudioResampler(format='flt', layout='mono', rate=sample_rate)
                        samples = [r.to_ndarray() for frame in container.decode(audio=0) for r in resampler.resample(frame)]
                        opt_audio = np.concatenate(samples, axis=1).flatten() if samples else np.zeros(0, dtype=np.float32)
                        opt_dur = len(opt_audio) / sample_rate

                        opt_start = current_time
                        opt_end = opt_start + opt_dur
                        opt_times[letter] = (round(opt_start, 3), round(opt_end, 3))

                        raw_opt_words = align_audio_with_whisper(tmp_opt)
                        for w in raw_opt_words:
                            all_quiz_words.append({
                                'word': w['word'],
                                'start': round(opt_start + w['start'], 3),
                                'end': round(opt_start + w['end'], 3),
                                'part': f"option_{letter}"
                            })

                        combined_audio_frames.append(opt_audio)
                        current_time += opt_dur
                        try: os.remove(tmp_opt)
                        except: pass

                    # 3. Phase 2: 3-Second Ticking Clock Silence / SFX
                    pause_dur = 3.0
                    pause_audio = create_silence(pause_dur, sample_rate)
                    pause_audio = mix_sfx(pause_audio, "clock_tick", 0.0, sample_rate=sample_rate, volume=0.55)
                    combined_audio_frames.append(pause_audio)
                    current_time += pause_dur

                    reveal_start_time = current_time

                    # 4. Phase 3: Answer Reveal & Explanation TTS
                    if not is_c:
                        reveal_text = clean_tts_speech(f"The correct answer is Option {c_opt}: {c_text}! {exp}")
                    else:
                        reveal_text = f"Question {q_num} is your hard challenge for today! Comment your answer A, B, C, or D below right now!"
                    
                    tmp_ans = os.path.join(temp_dir, f"sec_{sec_idx}_q{q_idx}_ans.mp3")
                    generate_tts_sync(strip_emojis(reveal_text), voice=intro_voice, rate="-5%", pitch="+0Hz", output_path=tmp_ans)
                    
                    container = av.open(tmp_ans)
                    resampler = av.AudioResampler(format='flt', layout='mono', rate=sample_rate)
                    samples = [r.to_ndarray() for frame in container.decode(audio=0) for r in resampler.resample(frame)]
                    ans_audio = np.concatenate(samples, axis=1).flatten() if samples else np.zeros(0, dtype=np.float32)
                    ans_dur = len(ans_audio) / sample_rate

                    raw_ans_words = align_audio_with_whisper(tmp_ans)
                    for w in raw_ans_words:
                        all_quiz_words.append({
                            'word': w['word'],
                            'start': round(reveal_start_time + w['start'], 3),
                            'end': round(reveal_start_time + w['end'], 3),
                            'part': 'reveal'
                        })

                    # Play chime SFX on correct answer reveal
                    if not is_c:
                        ans_audio = mix_sfx(ans_audio, "chime", 0.1, sample_rate=sample_rate, volume=0.45)
                    
                    combined_audio_frames.append(ans_audio)
                    current_time += ans_dur
                    try: os.remove(tmp_ans)
                    except: pass

                    # Add Single Continuous Quiz Slide to Timeline
                    timeline.append({
                        "start_time": q_start_time,
                        "end_time": current_time,
                        "is_talking": True,
                        "text": f"Question {q_num}: {q_str}",
                        "is_quiz_slide": True,
                        "quiz_data": {
                            "q_num": q_num,
                            "question": q_str,
                            "option_a": oa,
                            "option_b": ob,
                            "option_c": oc,
                            "option_d": od,
                            "correct_option": c_opt,
                            "correct_text": c_text,
                            "explanation": exp,
                            "reveal_start": reveal_start_time,
                            "is_challenge": is_c,
                            "opt_times": opt_times,
                            "words": all_quiz_words
                        },
                        "section_type": "intro_quiz"
                    })

                # Transition Message TTS into Part 3 Shadowing Practice (With Whisper word-level red highlighting)
                tr_msg = sec.get("transition_msg", "Now let's move on to Shadowing Practice! Take a deep breath, listen carefully, and get ready to repeat each sentence out loud.")
                tmp_tr = os.path.join(temp_dir, f"sec_{sec_idx}_tr.mp3")
                generate_tts_sync(strip_emojis(tr_msg), voice=intro_voice, rate="-5%", pitch="+0Hz", output_path=tmp_tr)
                
                container = av.open(tmp_tr)
                resampler = av.AudioResampler(format='flt', layout='mono', rate=sample_rate)
                samples = [r.to_ndarray() for frame in container.decode(audio=0) for r in resampler.resample(frame)]
                tr_audio = np.concatenate(samples, axis=1).flatten() if samples else np.zeros(0, dtype=np.float32)
                tr_dur = len(tr_audio) / sample_rate

                raw_tr_words = align_audio_with_whisper(tmp_tr)
                adj_tr_words = [{
                    'word': w['word'],
                    'start': round(current_time + w['start'], 3),
                    'end': round(current_time + w['end'], 3)
                } for w in raw_tr_words]

                tr_slides = group_words_into_slides(adj_tr_words, max_words=16)
                if tr_slides:
                    for slide in tr_slides:
                        timeline.append({
                            "start_time": slide["start_time"],
                            "end_time": slide["end_time"],
                            "is_talking": True,
                            "text": slide["text"],
                            "words": slide["words"],
                            "section_type": "intro_quiz",
                            "is_encouragement": False
                        })
                else:
                    timeline.append({
                        "start_time": current_time,
                        "end_time": current_time + tr_dur,
                        "is_talking": True,
                        "text": tr_msg,
                        "words": [],
                        "section_type": "intro_quiz"
                    })

                combined_audio_frames.append(tr_audio)
                current_time += tr_dur
                try: os.remove(tmp_tr)
                except: pass

                continue

            raw_text = sec.get("text", "").strip()
            if not raw_text and items:
                raw_text = " ".join([strip_emojis(item.get("sentence", "").strip()) for item in items if item.get("sentence", "").strip()])
            
            full_paragraph_text = strip_emojis(raw_text)
            if not full_paragraph_text:
                continue

            tmp_mp3 = os.path.join(temp_dir, f"section_{sec_idx}_full.mp3")

            generate_tts_sync(full_paragraph_text, voice=intro_voice, rate="-5%", pitch="+0Hz", output_path=tmp_mp3)

# av imported at top
            container = av.open(tmp_mp3)
            resampler = av.AudioResampler(format='flt', layout='mono', rate=sample_rate)
            audio_samples = []
            for frame in container.decode(audio=0):
                resampled = resampler.resample(frame)
                for r in resampled:
                    audio_samples.append(r.to_ndarray())
            
            if audio_samples:
                section_audio = np.concatenate(audio_samples, axis=1).flatten()
            else:
                section_audio = np.zeros(0, dtype=np.float32)

            dur = len(section_audio) / sample_rate
            sec_start_time = current_time

            all_word_ts = align_audio_with_whisper(tmp_mp3)

            # Re-apply BGM to intro_story / review
            section_audio = mix_bgm_into_section(section_audio, sample_rate=sample_rate, volume=0.12)

            adjusted_words = []
            for w in all_word_ts:
                adjusted_words.append({
                    'word': w['word'],
                    'start': round(sec_start_time + w['start'], 3),
                    'end': round(sec_start_time + w['end'], 3)
                })

            slides = group_words_into_slides(adjusted_words, max_words=16)

            for slide in slides:
                timeline.append({
                    "start_time": slide["start_time"],
                    "end_time": slide["end_time"],
                    "is_talking": True,
                    "text": slide["text"],
                    "words": slide["words"],
                    "section_type": sec_type,
                    "is_encouragement": False
                })

            combined_audio_frames.append(section_audio)
            current_time += dur

            try: os.remove(tmp_mp3)
            except: pass

        elif sec_type == "shadowing_practice":
            for item_idx, item in enumerate(items):
                raw_sentence = item.get("sentence", "").strip()
                # Sanitize any raw JSON string artifacts
                raw_sentence = re.sub(r'["\'],?\s*["\']?target_word["\']?\s*:.*', '', raw_sentence, flags=re.IGNORECASE)
                raw_sentence = re.sub(r'["\'],?\s*["\']?meaning["\']?\s*:.*', '', raw_sentence, flags=re.IGNORECASE)
                raw_sentence = strip_emojis(raw_sentence.strip(' "\''))
                if not raw_sentence:
                    continue

                target_word = item.get("target_word", "").strip()
                meaning = item.get("meaning", "").strip()

                pause_sec = float(item.get("pause_sec", 4.2))

                prefix, clean_text = extract_encouragement_prefix(raw_sentence)
                if prefix:
                    tmp_mp3_enc = os.path.join(temp_dir, f"sec_{sec_idx}_item_{item_idx}_prefix.mp3")
                    generate_tts_sync(prefix, voice=praise_voice, rate="+0%", pitch="+0Hz", output_path=tmp_mp3_enc)

                    # av already imported
                    container = av.open(tmp_mp3_enc)
                    resampler = av.AudioResampler(format='flt', layout='mono', rate=sample_rate)
                    audio_samples = []
                    for frame in container.decode(audio=0):
                        resampled = resampler.resample(frame)
                        for r in resampled:
                            audio_samples.append(r.to_ndarray())
                    
                    enc_audio = np.concatenate(audio_samples, axis=1).flatten() if audio_samples else np.zeros(0, dtype=np.float32)
                    enc_word_ts = align_audio_with_whisper(tmp_mp3_enc)
                    enc_dur = len(enc_audio) / sample_rate

                    enc_start = current_time
                    enc_end = enc_start + enc_dur

                    adj_enc_words = [{'word': w['word'], 'start': round(enc_start + w['start'], 3), 'end': round(enc_start + w['end'], 3)} for w in enc_word_ts]
                    
                    timeline.append({
                        "start_time": round(enc_start, 3),
                        "end_time": round(enc_end, 3),
                        "is_talking": True,
                        "text": prefix,
                        "words": adj_enc_words,
                        "section_type": sec_type,
                        "is_encouragement": True
                    })
                    combined_audio_frames.append(enc_audio)
                    current_time = enc_end

                    try: os.remove(tmp_mp3_enc)
                    except: pass

                # 3X Progressive Repetitions (-10%, -13%, -17%)
                for rep in range(3):
                    current_rate = rep_rates[rep]
                    tmp_mp3_rep = os.path.join(temp_dir, f"sec_{sec_idx}_item_{item_idx}_rep_{rep}.mp3")
                    
                    generate_tts_sync(clean_text, voice=shadowing_voice, rate=current_rate, pitch="+2Hz", output_path=tmp_mp3_rep)

                    # av already imported
                    container = av.open(tmp_mp3_rep)
                    resampler = av.AudioResampler(format='flt', layout='mono', rate=sample_rate)
                    audio_samples = []
                    for frame in container.decode(audio=0):
                        resampled = resampler.resample(frame)
                        for r in resampled:
                            audio_samples.append(r.to_ndarray())
                    
                    rep_audio = np.concatenate(audio_samples, axis=1).flatten() if audio_samples else np.zeros(0, dtype=np.float32)
                    rep_word_ts = align_audio_with_whisper(tmp_mp3_rep)
                    rep_dur = len(rep_audio) / sample_rate

                    rep_start = current_time
                    rep_end = rep_start + rep_dur

                    adj_rep_words = [{'word': w['word'], 'start': round(rep_start + w['start'], 3), 'end': round(rep_start + w['end'], 3)} for w in rep_word_ts]

                    timeline.append({
                        "start_time": round(rep_start, 3),
                        "end_time": round(rep_end, 3),
                        "is_talking": True,
                        "text": clean_text,
                        "words": adj_rep_words,
                        "section_type": sec_type,
                        "target_word": target_word,
                        "meaning": meaning,
                        "is_encouragement": False
                    })

                    combined_audio_frames.append(rep_audio)
                    current_time = rep_end

                    # Pause gap for student shadowing practice
                    pause_dur = max(3.5, pause_sec)
                    pause_start = current_time
                    pause_end = pause_start + pause_dur

                    timeline.append({
                        "start_time": round(pause_start, 3),
                        "end_time": round(pause_end, 3),
                        "is_talking": False,
                        "text": clean_text,
                        "words": [],
                        "section_type": sec_type,
                        "target_word": target_word,
                        "meaning": meaning,
                        "is_encouragement": False
                    })

                    silence_samples = create_silence(pause_dur, sample_rate)
                    combined_audio_frames.append(silence_samples)
                    current_time = pause_end

                    try: os.remove(tmp_mp3_rep)
                    except: pass

                # Host Annie Praise Item immediately after 3X Shadowing!
                praise_word = PRAISE_PHRASES[praise_idx % len(PRAISE_PHRASES)]
                praise_idx += 1

                tmp_mp3_praise = os.path.join(temp_dir, f"sec_{sec_idx}_item_{item_idx}_praise.mp3")
                generate_tts_sync(praise_word, voice=praise_voice, rate="+0%", pitch="+0Hz", output_path=tmp_mp3_praise)

                # av already imported
                container = av.open(tmp_mp3_praise)
                resampler = av.AudioResampler(format='flt', layout='mono', rate=sample_rate)
                audio_samples = []
                for frame in container.decode(audio=0):
                    resampled = resampler.resample(frame)
                    for r in resampled:
                        audio_samples.append(r.to_ndarray())

                praise_audio = np.concatenate(audio_samples, axis=1).flatten() if audio_samples else np.zeros(0, dtype=np.float32)
                praise_word_ts = align_audio_with_whisper(tmp_mp3_praise)
                praise_dur = len(praise_audio) / sample_rate

                pr_start = current_time
                pr_end = pr_start + praise_dur

                adj_pr_words = [{'word': w['word'], 'start': round(pr_start + w['start'], 3), 'end': round(pr_start + w['end'], 3)} for w in praise_word_ts]

                timeline.append({
                    "start_time": round(pr_start, 3),
                    "end_time": round(pr_end, 3),
                    "is_talking": True,
                    "text": praise_word,
                    "words": adj_pr_words,
                    "section_type": sec_type,
                    "is_encouragement": True
                })

                chime_sfx_times.append(pr_start)

                combined_audio_frames.append(praise_audio)
                current_time = pr_end

                silence_praise = create_silence(0.3, sample_rate)
                combined_audio_frames.append(silence_praise)
                current_time += 0.3

                try: os.remove(tmp_mp3_praise)
                except: pass

    if combined_audio_frames:
        final_audio = np.concatenate(combined_audio_frames)
    else:
        final_audio = create_silence(1.0, sample_rate)

    # Mix Sound Effects (Chime on praise/outro, Whoosh on transition)
    for ts in chime_sfx_times:
        final_audio = mix_sfx(final_audio, "chime", ts, sample_rate=sample_rate, volume=0.3)
    # Write 100% exact YouTube chapter timestamps manifest
    os.makedirs("output", exist_ok=True)
    intro_dur = 0.0
    if os.path.exists("video/intro.mp4"):
        try:
            c_intro = av.open("video/intro.mp4")
            intro_dur = float(c_intro.duration) / 1000000.0 if c_intro.duration else 5.0
        except:
            intro_dur = 5.0

    lines = []
    def format_mmss(sec):
        s = int(round(sec))
        return f"{s//60:02d}:{s%60:02d}"

    if intro_dur > 0:
        lines.append("00:00 - Intro & Channel Hook")
    
    first = True
    for name, s_t in section_timestamps.items():
        actual_s = s_t + intro_dur
        t_str = "00:00" if (intro_dur == 0 and first) else format_mmss(actual_s)
        first = False
        lines.append(f"{t_str} - {name}")

    chapters_manifest = "\n".join(lines)
    with open("output/youtube_chapters.txt", "w", encoding="utf-8") as f:
        f.write(chapters_manifest + "\n")

    print("\n" + "="*60)
    print("100% EXACT YOUTUBE CHAPTER TIMESTAMPS GENERATED:")
    print("="*60)
    print(chapters_manifest)
    print("="*60 + "\n")

    sf.write(output_audio_path, final_audio, sample_rate)
    return output_audio_path, timeline, current_time

def build_short_audio_and_timeline(text, voice="en-GB-LibbyNeural", rate="-10%", output_audio_path="output_short.wav", progress_callback=None):
    """
    Synthesize audio for a Short story and align word-level timestamps using Faster-Whisper.
    """
    if progress_callback:
        progress_callback("Synthesizing Short Audio with Edge-TTS...", 0.1)

    temp_dir = tempfile.mkdtemp(prefix="short_tts_")
    tmp_mp3 = os.path.join(temp_dir, "short_speech.mp3")

    clean_story_text = strip_emojis(text.strip())
    generate_tts_sync(clean_story_text, voice=voice, rate=rate, pitch="+0Hz", output_path=tmp_mp3)

    sample_rate = 44100
# av imported at top
    container = av.open(tmp_mp3)
    resampler = av.AudioResampler(format='flt', layout='mono', rate=sample_rate)
    audio_samples = []
    for frame in container.decode(audio=0):
        resampled = resampler.resample(frame)
        for r in resampled:
            audio_samples.append(r.to_ndarray())
    
    if audio_samples:
        short_audio = np.concatenate(audio_samples, axis=1).flatten()
    else:
        short_audio = np.zeros(0, dtype=np.float32)

    # Mix background music (-28dB / volume=0.12) matching long video logic
    short_audio = mix_bgm_into_section(short_audio, sample_rate=sample_rate, volume=0.12)

    total_dur = len(short_audio) / sample_rate
    sf.write(output_audio_path, short_audio, sample_rate)

    all_words = align_audio_with_whisper(tmp_mp3)

    return output_audio_path, clean_story_text, all_words, total_dur


def build_sentence_audio_and_timeline(
    script_data,
    host_voice="en-US-JennyNeural",
    speaker_a_voice="en-US-AvaNeural",
    speaker_b_voice="en-GB-SoniaNeural",
    rate="-8%",
    output_audio_path="output_sentence.wav",
    progress_callback=None
):
    """
    Synthesize audio and generate frame timeline for Type 3: 20 Essential Sentences format.
    Includes Intro -> Retention Hook -> 3 Parts Loop (Sentences 1-7, 8-14, 15-20) -> Outro.
    Uses rate="-8%" for clear, natural pronunciation speed and extended practice pause gaps.
    """
    if progress_callback:
        progress_callback("Synthesizing Sentence Video Audio & Building Timeline...", 0.05)

    sample_rate = 44100
    temp_dir = tempfile.mkdtemp(prefix="sent_tts_")
    combined_audio_frames = []
    current_time = 0.0
    timeline = []
    section_timestamps = {}

    def get_audio_from_mp3(mp3_p):
        container = av.open(mp3_p)
        resampler = av.AudioResampler(format='flt', layout='mono', rate=sample_rate)
        samples = []
        for frame in container.decode(audio=0):
            resampled = resampler.resample(frame)
            for r in resampled:
                samples.append(r.to_ndarray())
        if samples:
            return np.concatenate(samples, axis=1).flatten()
        return np.zeros(0, dtype=np.float32)
        """Return the amount of leading silence (in seconds) present in the MP3.
        Calculated as total audio duration minus the end timestamp of the last
        Whisper‑detected word. This captures the encoder delay that Whisper ignores.
        """
        # Load full PCM audio duration
        audio = get_audio_from_mp3(mp3_p)
# compute_leading_silence moved to top level
        # Get Whisper word list (may be empty)
        try:
            w_list = align_audio_with_whisper(mp3_p)
            if w_list:
                last_end = max(w["end"] for w in w_list)
                leading = max(0.0, total_dur - last_end)
                return leading
        except Exception as e:
            print(f"Whisper align warning in compute_leading_silence: {e}")
        return 0.0

    def get_words_with_offset(mp3_p, offset_sec, text_fallback=""):
        clean_t = strip_emojis(text_fallback)
        t_mod = re.sub(r'[—–]', ' ', clean_t)
        text_words = t_mod.split()
        if not text_words:
            return []

        try:
            w_list = align_audio_with_whisper(mp3_p)
            if w_list:
                res = []
                w_idx = 0
                n_w = len(w_list)

                for t_idx, tw in enumerate(text_words):
                    tw_clean = re.sub(r'[^\w]', '', tw.lower())
                    if not tw_clean:
                        prev_end = res[-1]["end"] if res else offset_sec
                        res.append({"word": tw, "start": prev_end, "end": round(prev_end + 0.1, 3)})
                        continue

                    # Look ahead up to 6 words in w_list for a fuzzy word match
                    matched_w_idx = -1
                    for lookahead in range(min(6, n_w - w_idx)):
                        curr_w_clean = re.sub(r'[^\w]', '', w_list[w_idx + lookahead]["word"].lower())
                        if curr_w_clean and (
                            tw_clean == curr_w_clean or
                            (len(tw_clean) >= 3 and len(curr_w_clean) >= 3 and (tw_clean.startswith(curr_w_clean[:3]) or curr_w_clean.startswith(tw_clean[:3])))
                        ):
                            matched_w_idx = w_idx + lookahead
                            break

                    if matched_w_idx != -1:
                        w_obj = w_list[matched_w_idx]
                        res.append({
                            "word": tw,
                            "start": round(offset_sec + w_obj["start"], 3),
                            "end":   round(offset_sec + w_obj["end"], 3)
                        })
                        w_idx = matched_w_idx + 1
                    else:
                        if w_idx < n_w:
                            w_obj = w_list[w_idx]
                            res.append({
                                "word": tw,
                                "start": round(offset_sec + w_obj["start"], 3),
                                "end":   round(offset_sec + w_obj["end"], 3)
                            })
                            w_idx += 1
                        else:
                            last_end = res[-1]["end"] if res else offset_sec
                            res.append({
                                "word": tw,
                                "start": last_end,
                                "end": round(last_end + 0.25, 3)
                            })
                return res
        except Exception as e:
            print(f"Whisper align warning in get_words_with_offset: {e}")

        # Fallback word splitting if Whisper returns no words
        aud_data = get_audio_from_mp3(mp3_p)
        tot_d = max(0.1, len(aud_data) / sample_rate)
        w_d = tot_d / len(text_words)
        res = []
        for i, w in enumerate(text_words):
            res.append({
                "word": w,
                "start": round(offset_sec + i * w_d, 3),
                "end":   round(offset_sec + (i + 1) * w_d, 3)
            })
        return res

    # Record 00:00 Intro timestamp
    section_timestamps["Intro & Lesson Structure"] = current_time

    # 1. Intro Title Section
    intro_text = script_data.get("intro_text", "Hi everyone, welcome back to Shadowing English.")
    tmp_intro = os.path.join(temp_dir, "intro.mp3")
    generate_tts_sync(intro_text, voice=host_voice, rate=rate, output_path=tmp_intro)
    audio_intro = get_audio_from_mp3(tmp_intro)
    dur_intro = len(audio_intro) / sample_rate
    intro_words = get_words_with_offset(tmp_intro, current_time, intro_text)

    combined_audio_frames.append(audio_intro)
    timeline.append({
        "start_time": current_time,
        "end_time": current_time + dur_intro,
        "sentence_num": 0,
        "main_sentence": "Welcome to Shadowing English",
        "target_word": "",
        "explanation": intro_text,
        "dialogue_question": "",
        "dialogue_answer": "",
        "active_state": "INTRO",
        "is_pause": False,
        "part_name": "Intro",
        "words": intro_words
    })
    current_time += dur_intro

    # 1b. Retention Hook Section (Bait viewer to stay until the end)
    intro_hook = script_data.get(
        "intro_hook",
        "Today, you will master 20 high-frequency English sentences divided into 3 essential parts: Part 1 for Daily Expressions, Part 2 for Natural Conversations, and Part 3 for Native Fluency. Repeat out loud during the YOUR TURN section to build instant speaking confidence!"
    )
    tmp_hook = os.path.join(temp_dir, "intro_hook.mp3")
    generate_tts_sync(intro_hook, voice=host_voice, rate=rate, output_path=tmp_hook)
    aud_hook = get_audio_from_mp3(tmp_hook)
    dur_hook = len(aud_hook) / sample_rate
    hook_words = get_words_with_offset(tmp_hook, current_time, intro_hook)

    combined_audio_frames.append(aud_hook)
    timeline.append({
        "start_time": current_time,
        "end_time": current_time + dur_hook,
        "sentence_num": 0,
        "main_sentence": "3 Parts Speaking Challenge",
        "target_word": "",
        "explanation": intro_hook,
        "dialogue_question": "",
        "dialogue_answer": "",
        "active_state": "INTRO",
        "is_pause": False,
        "part_name": "Intro",
        "words": hook_words
    })
    current_time += dur_hook + 0.6
    combined_audio_frames.append(create_silence(0.6, sample_rate))

    sentences = script_data.get("sentences", [])
    total_sentences = len(sentences)

    recorded_parts = set()

    for idx, sent in enumerate(sentences):
        num = sent.get("number", idx + 1)
        main_sent = sent.get("main_sentence", "")
        target_word = sent.get("target_word", "")
        explanation = sent.get("explanation", "")
        q_text = sent.get("dialogue_question", "")
        a_text = sent.get("dialogue_answer", "")

        # 3-Part Chapter Determination (15 Sentences Total)
        explicit_part = sent.get("part", "")
        if explicit_part:
            part_name = explicit_part
        elif num <= 5:
            part_name = "Part 1: Daily Expressions"
        elif num <= 10:
            part_name = "Part 2: Natural Conversations"
        else:
            part_name = "Part 3: Native Fluency"


        # Record timestamp for YouTube description chapter
        if part_name not in recorded_parts:
            recorded_parts.add(part_name)
            section_timestamps[part_name] = current_time

        if progress_callback and total_sentences > 0:
            prog = 0.1 + (idx / total_sentences) * 0.8
            progress_callback(f"Synthesizing Sentence {num}/{total_sentences}: '{main_sent[:25]}...'", prog)

        # a. Host reads main_sentence directly
        host_head_text = main_sent
        tmp_head = os.path.join(temp_dir, f"head_{idx}.mp3")
        generate_tts_sync(host_head_text, voice=host_voice, rate=rate, output_path=tmp_head)
        aud_head = get_audio_from_mp3(tmp_head)
        dur_head = len(aud_head) / sample_rate
        head_words = get_words_with_offset(tmp_head, current_time, main_sent)

        combined_audio_frames.append(aud_head)
        timeline.append({
            "start_time": current_time,
            "end_time": current_time + dur_head,
            "sentence_num": num,
            "main_sentence": main_sent,
            "target_word": target_word,
            "explanation": explanation,
            "dialogue_question": q_text,
            "dialogue_answer": a_text,
            "active_state": "MAIN_SENTENCE",
            "is_pause": False,
            "part_name": part_name,
            "words": head_words
        })

        current_time += dur_head + 0.3
        combined_audio_frames.append(create_silence(0.3, sample_rate))

        # b. Host reads Explanation with smooth transition phrase ("This means, ")
        if explanation:
            tmp_exp = os.path.join(temp_dir, f"exp_{idx}.mp3")
            exp_tts_text = explanation
            if not explanation.lower().startswith(("this means", "meaning", "it means", "this expression")):
                exp_tts_text = f"This means, {explanation}"

            generate_tts_sync(exp_tts_text, voice=host_voice, rate=rate, output_path=tmp_exp)
            aud_exp = get_audio_from_mp3(tmp_exp)
            dur_exp = len(aud_exp) / sample_rate
            exp_words = get_words_with_offset(tmp_exp, current_time, explanation)

            combined_audio_frames.append(aud_exp)
            timeline.append({
                "start_time": current_time,
                "end_time": current_time + dur_exp,
                "sentence_num": num,
                "main_sentence": main_sent,
                "target_word": target_word,
                "explanation": explanation,
                "dialogue_question": q_text,
                "dialogue_answer": a_text,
                "active_state": "EXPLANATION",
                "is_pause": False,
                "part_name": part_name,
                "words": exp_words
            })
            current_time += dur_exp + 0.3
            combined_audio_frames.append(create_silence(0.3, sample_rate))

        # c. Host reads "Example,"
        tmp_ex = os.path.join(temp_dir, f"ex_{idx}.mp3")
        generate_tts_sync("Example,", voice=host_voice, rate=rate, output_path=tmp_ex)
        aud_ex = get_audio_from_mp3(tmp_ex)
        dur_ex = len(aud_ex) / sample_rate
        ex_words = get_words_with_offset(tmp_ex, current_time, "Example,")

        combined_audio_frames.append(aud_ex)
        timeline.append({
            "start_time": current_time,
            "end_time": current_time + dur_ex,
            "sentence_num": num,
            "main_sentence": main_sent,
            "target_word": target_word,
            "explanation": explanation,
            "dialogue_question": q_text,
            "dialogue_answer": a_text,
            "active_state": "EXAMPLE_INTRO",
            "is_pause": False,
            "part_name": part_name,
            "words": ex_words
        })
        current_time += dur_ex + 0.2
        combined_audio_frames.append(create_silence(0.2, sample_rate))

        # d. Speaker A reads Question (Demo)
        if q_text:
            tmp_q1 = os.path.join(temp_dir, f"q1_{idx}.mp3")
            generate_tts_sync(q_text, voice=speaker_a_voice, rate=rate, output_path=tmp_q1)
            aud_q1 = get_audio_from_mp3(tmp_q1)
            dur_q1 = len(aud_q1) / sample_rate
            q1_words = get_words_with_offset(tmp_q1, current_time, q_text)

            combined_audio_frames.append(aud_q1)
            timeline.append({
                "start_time": current_time,
                "end_time": current_time + dur_q1,
                "sentence_num": num,
                "main_sentence": main_sent,
                "target_word": target_word,
                "explanation": explanation,
                "dialogue_question": q_text,
                "dialogue_answer": a_text,
                "active_state": "DEMO_Q",
                "is_pause": False,
                "part_name": part_name,
                "words": q1_words
            })
            current_time += dur_q1 + 0.2
            combined_audio_frames.append(create_silence(0.2, sample_rate))

        # e. Speaker B reads Answer (Demo)
        if a_text:
            tmp_a1 = os.path.join(temp_dir, f"a1_{idx}.mp3")
            generate_tts_sync(a_text, voice=speaker_b_voice, rate=rate, output_path=tmp_a1)
            aud_a1 = get_audio_from_mp3(tmp_a1)
            dur_a1 = len(aud_a1) / sample_rate
            a1_words = get_words_with_offset(tmp_a1, current_time, a_text)

            combined_audio_frames.append(aud_a1)
            timeline.append({
                "start_time": current_time,
                "end_time": current_time + dur_a1,
                "sentence_num": num,
                "main_sentence": main_sent,
                "target_word": target_word,
                "explanation": explanation,
                "dialogue_question": q_text,
                "dialogue_answer": a_text,
                "active_state": "DEMO_A",
                "is_pause": False,
                "part_name": part_name,
                "words": a1_words
            })
            current_time += dur_a1 + 0.4
            combined_audio_frames.append(create_silence(0.4, sample_rate))

        # f. Host reads "Now, repeat after me."
        tmp_rep = os.path.join(temp_dir, f"rep_{idx}.mp3")
        generate_tts_sync("Now, repeat after me.", voice=host_voice, rate=rate, output_path=tmp_rep)
        aud_rep = get_audio_from_mp3(tmp_rep)
        dur_rep = len(aud_rep) / sample_rate
        rep_words = get_words_with_offset(tmp_rep, current_time, "Now, repeat after me.")

        combined_audio_frames.append(aud_rep)
        timeline.append({
            "start_time": current_time,
            "end_time": current_time + dur_rep,
            "sentence_num": num,
            "main_sentence": main_sent,
            "target_word": target_word,
            "explanation": explanation,
            "dialogue_question": q_text,
            "dialogue_answer": a_text,
            "active_state": "REPEAT_INSTR",
            "is_pause": False,
            "part_name": part_name,
            "words": rep_words
        })
        current_time += dur_rep + 0.3
        combined_audio_frames.append(create_silence(0.3, sample_rate))

        # g. Speaker A reads Question + Practice Pause (Longer pause buffer for viewer to speak out loud)
        if q_text:
            tmp_q2 = os.path.join(temp_dir, f"q2_{idx}.mp3")
            generate_tts_sync(q_text, voice=speaker_a_voice, rate=rate, output_path=tmp_q2)
            aud_q2 = get_audio_from_mp3(tmp_q2)
            dur_q2 = len(aud_q2) / sample_rate
            q2_words = get_words_with_offset(tmp_q2, current_time, q_text)

            combined_audio_frames.append(aud_q2)
            timeline.append({
                "start_time": current_time,
                "end_time": current_time + dur_q2,
                "sentence_num": num,
                "main_sentence": main_sent,
                "target_word": target_word,
                "explanation": explanation,
                "dialogue_question": q_text,
                "dialogue_answer": a_text,
                "active_state": "PRACTICE_Q_SPEAKING",
                "is_pause": False,
                "part_name": part_name,
                "words": q2_words
            })
            current_time += dur_q2

            # Extended Pause gap for viewer practice: 45% longer than TTS duration + 1.2s padding (min 4.5s)
            pause_dur_q = max(4.5, dur_q2 * 1.45 + 1.2)
            sil_q = create_silence(pause_dur_q, sample_rate)
            combined_audio_frames.append(sil_q)
            timeline.append({
                "start_time": current_time,
                "end_time": current_time + pause_dur_q,
                "sentence_num": num,
                "main_sentence": main_sent,
                "target_word": target_word,
                "explanation": explanation,
                "dialogue_question": q_text,
                "dialogue_answer": a_text,
                "active_state": "PRACTICE_Q_PAUSE",
                "is_pause": True,
                "part_name": part_name,
                "words": []
            })
            current_time += pause_dur_q + 0.2
            combined_audio_frames.append(create_silence(0.2, sample_rate))

        # h. Speaker B reads Answer + Practice Pause (Longer pause buffer for viewer to speak out loud)
        if a_text:
            tmp_a2 = os.path.join(temp_dir, f"a2_{idx}.mp3")
            generate_tts_sync(a_text, voice=speaker_b_voice, rate=rate, output_path=tmp_a2)
            aud_a2 = get_audio_from_mp3(tmp_a2)
            dur_a2 = len(aud_a2) / sample_rate
            a2_words = get_words_with_offset(tmp_a2, current_time, a_text)

            combined_audio_frames.append(aud_a2)
            timeline.append({
                "start_time": current_time,
                "end_time": current_time + dur_a2,
                "sentence_num": num,
                "main_sentence": main_sent,
                "target_word": target_word,
                "explanation": explanation,
                "dialogue_question": q_text,
                "dialogue_answer": a_text,
                "active_state": "PRACTICE_A_SPEAKING",
                "is_pause": False,
                "part_name": part_name,
                "words": a2_words
            })
            current_time += dur_a2

            # Extended Pause gap for viewer practice: 45% longer than TTS duration + 1.2s padding (min 4.5s)
            pause_dur_a = max(4.5, dur_a2 * 1.45 + 1.2)
            sil_a = create_silence(pause_dur_a, sample_rate)
            combined_audio_frames.append(sil_a)
            timeline.append({
                "start_time": current_time,
                "end_time": current_time + pause_dur_a,
                "sentence_num": num,
                "main_sentence": main_sent,
                "target_word": target_word,
                "explanation": explanation,
                "dialogue_question": q_text,
                "dialogue_answer": a_text,
                "active_state": "PRACTICE_A_PAUSE",
                "is_pause": True,
                "part_name": part_name,
                "words": []
            })
            current_time += pause_dur_a + 0.3
            combined_audio_frames.append(create_silence(0.3, sample_rate))

        # i. Host Praise (Round-robin diverse praise phrases)
        praise_txt = PRAISE_PHRASES[idx % len(PRAISE_PHRASES)]
        tmp_praise = os.path.join(temp_dir, f"praise_{idx}.mp3")

        generate_tts_sync(praise_txt, voice=host_voice, rate=rate, output_path=tmp_praise)
        aud_praise = get_audio_from_mp3(tmp_praise)
        dur_praise = len(aud_praise) / sample_rate

        combined_audio_frames.append(aud_praise)
        timeline.append({
            "start_time": current_time,
            "end_time": current_time + dur_praise,
            "sentence_num": num,
            "main_sentence": main_sent,
            "target_word": target_word,
            "explanation": explanation,
            "dialogue_question": q_text,
            "dialogue_answer": a_text,
            "active_state": "PRAISE",
            "is_pause": False,
            "part_name": part_name,
            "words": []
        })
        current_time += dur_praise + 0.5
        combined_audio_frames.append(create_silence(0.5, sample_rate))

    # Outro Section
    section_timestamps["Outro & Practice Summary"] = current_time

    outro_text = script_data.get("outro_text", "Fantastic job! You've just learned 20 powerful native English sentences.")
    tmp_outro = os.path.join(temp_dir, "outro.mp3")
    generate_tts_sync(outro_text, voice=host_voice, rate=rate, output_path=tmp_outro)
    aud_outro = get_audio_from_mp3(tmp_outro)
    dur_outro = len(aud_outro) / sample_rate

    outro_words = get_words_with_offset(tmp_outro, current_time, outro_text)
    combined_audio_frames.append(aud_outro)
    timeline.append({
        "start_time": current_time,
        "end_time": current_time + dur_outro,
        "sentence_num": 0,
        "main_sentence": "Keep Speaking with Confidence!",
        "target_word": "",
        "explanation": outro_text,
        "dialogue_question": "",
        "dialogue_answer": "",
        "active_state": "OUTRO",
        "is_pause": False,
        "part_name": "Outro",
        "words": outro_words
    })

    current_time += dur_outro

    if combined_audio_frames:
        final_audio = np.concatenate(combined_audio_frames)
    else:
        final_audio = create_silence(1.0, sample_rate)

    final_audio = mix_bgm_into_section(final_audio, sample_rate=sample_rate, volume=0.08)
    sf.write(output_audio_path, final_audio, sample_rate)

    # Save chapter timestamps for YouTube
    lines = []
    for name, s_t in section_timestamps.items():
        s = int(round(s_t))
        lines.append(f"{s//60:02d}:{s%60:02d} - {name}")
    
    with open("output/youtube_chapters.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return output_audio_path, timeline, current_time



