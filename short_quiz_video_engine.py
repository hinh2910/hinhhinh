import os
import sys
import math
import re
import time
import subprocess
import asyncio
import numpy as np
import av
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

from audio_engine import (
    generate_single_tts,
    generate_tts_sync,
    create_silence,
    strip_emojis,
    clean_tts_speech,
    generate_srt_file
)

def get_audio_from_mp3(mp3_path, sample_rate=44100):
    """Load audio PCM samples from an MP3 or audio file using PyAV."""
    try:
        container = av.open(mp3_path)
        resampler = av.AudioResampler(format='s16', layout='mono', rate=sample_rate)
        frames = []
        for frame in container.decode(audio=0):
            resampled = resampler.resample(frame)
            for r in resampled:
                frames.append(r.to_ndarray())
        container.close()
        if frames:
            return np.concatenate(frames, axis=1).flatten()
        return np.array([], dtype=np.int16)
    except Exception as e:
        print(f"Error loading audio from {mp3_path}: {e}")
        return np.array([], dtype=np.int16)

FONT_PATH_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
FONT_PATH_REG = "C:/Windows/Fonts/segoeui.ttf"

def get_quiz_fonts():
    try:
        font_title = ImageFont.truetype(FONT_PATH_BOLD, 64)
        font_hook = ImageFont.truetype(FONT_PATH_BOLD, 52)
        font_q_num = ImageFont.truetype(FONT_PATH_BOLD, 56)        # Large 56pt bold font for question number
        font_q_text = ImageFont.truetype(FONT_PATH_BOLD, 54)        # Heavy bold font matching screenshot
        font_opt_text = ImageFont.truetype(FONT_PATH_BOLD, 44)      # Prominent 44pt bold font for options
        font_timer = ImageFont.truetype(FONT_PATH_BOLD, 56)
        font_cta = ImageFont.truetype(FONT_PATH_BOLD, 48)
    except Exception as e:
        print(f"Warning loading fonts in short_quiz_video_engine ({e}), fallback to default...")
        font_title = ImageFont.load_default()
        font_hook = font_title
        font_q_num = font_title
        font_q_text = font_title
        font_opt_text = font_title
        font_timer = font_title
        font_cta = font_title

    return {
        "title": font_title,
        "hook": font_hook,
        "q_num": font_q_num,
        "q_text": font_q_text,
        "opt_text": font_opt_text,
        "timer": font_timer,
        "cta": font_cta
    }

def prepare_question_audio(q_num, q_txt, temp_dir, idx, sample_rate=44100):
    """
    Loads pre-generated TTS audio files for question text.
    If the question contains blanks ('______', '......'), inserts a 1.5s silence gap in between.
    """
    clean_q = re.sub(r'^(?:Question\s*\d+:?\s*)', '', q_txt, flags=re.IGNORECASE).strip()
    raw_parts = re.split(r'(?:_{2,}|\.{2,}|\(blank\))', clean_q)
    parts = [clean_tts_speech(p) for p in raw_parts if clean_tts_speech(p)]

    if len(parts) <= 1:
        p_q = os.path.join(temp_dir, f"q_{idx}.mp3")
        aud = get_audio_from_mp3(p_q, sample_rate=sample_rate)
        return aud, len(aud) / sample_rate

    audio_segments = []
    p_q0 = os.path.join(temp_dir, f"q_{idx}_0.mp3")
    audio_segments.append(get_audio_from_mp3(p_q0, sample_rate=sample_rate))
    audio_segments.append(create_silence(1.5, sample_rate=sample_rate))

    for p_idx, part in enumerate(parts[1:], 1):
        p_qp = os.path.join(temp_dir, f"q_{idx}_{p_idx}.mp3")
        if os.path.exists(p_qp):
            audio_segments.append(get_audio_from_mp3(p_qp, sample_rate=sample_rate))
            if p_idx < len(parts) - 1:
                audio_segments.append(create_silence(1.5, sample_rate=sample_rate))

    combined_aud = np.concatenate(audio_segments)
    return combined_aud, len(combined_aud) / sample_rate

def load_quiz_backgrounds():
    """Load and scale purple quiz background images to 1080x1920 canvas size."""
    p_solid = "short/8ea47762-8781-4432-940b-869554570d7e.png"
    p_card = "short/83308b5d-4896-47ef-b4d3-ce14eb98ae01.png"

    try:
        bg_solid = Image.open(p_solid).convert("RGBA").resize((1080, 1920), Image.Resampling.LANCZOS)
    except Exception as e:
        print(f"Warning loading solid purple bg ({e}), creating fallback...")
        bg_solid = Image.new("RGBA", (1080, 1920), (56, 28, 123, 255))

    try:
        bg_card = Image.open(p_card).convert("RGBA").resize((1080, 1920), Image.Resampling.LANCZOS)
    except Exception as e:
        print(f"Warning loading quiz card bg ({e}), creating fallback...")
        bg_card = bg_solid.copy()

    return bg_solid, bg_card

def load_clock_ticking_audio(sample_rate=44100, target_duration=3.0):
    """Load the 3-second clock ticking sound effect at soft background volume (25%)."""
    ticking_path = "video/YTSave_YouTube_Clock-Ticking-Sound-Effect_Media_o5jaeEUbpFc_009_128k.mp3"
    if not os.path.exists(ticking_path):
        print(f"Warning: Clock ticking audio not found at {ticking_path}, creating silence fallback...")
        return create_silence(target_duration, sample_rate)

    try:
        audio = get_audio_from_mp3(ticking_path, sample_rate=sample_rate)
        # Soften volume to 25%
        audio = (audio * 0.25).astype(np.int16)

        req_len = int(target_duration * sample_rate)
        if len(audio) >= req_len:
            return audio[:req_len]
        else:
            silence = np.zeros(req_len - len(audio), dtype=np.int16)
            return np.concatenate((audio, silence))
    except Exception as e:
        print(f"Error loading clock ticking audio: {e}")
        return create_silence(target_duration, sample_rate)

def build_short_quiz_audio_and_timeline(
    script_data,
    voice="en-US-JennyNeural",
    rate="-5%",
    output_audio_path="output/short_quiz_audio.wav",
    progress_callback=None
):
    """
    Synthesize audio and build frame timeline for 9:16 Short Question Video.
    """
    temp_dir = "temp_short_quiz"
    os.makedirs(temp_dir, exist_ok=True)
    sample_rate = 44100

    combined_audio_frames = []
    timeline = []
    current_time = 0.0

    questions = script_data.get("questions", [])
    intro_hook = script_data.get(
        "intro_hook",
        "If you get 10 out of 10 on this quiz, your English is AMAZING! Let's test your skills now!"
    )
    outro_text = script_data.get(
        "outro_text",
        "How many did you get right out of 10? Comment your score below!"
    )

    if progress_callback:
        progress_callback("Synthesizing Short Quiz Audio Clips in Parallel...", 0.05)

    # Pre-generate all TTS in parallel
    async def pregenerate_tts():
        sem = asyncio.Semaphore(8)
        async def sem_tts(txt, v, r, p):
            async with sem:
                if not os.path.exists(p):
                    await generate_single_tts(txt, voice=v, rate=r, output_path=p)

        tasks = []
        p_hook = os.path.join(temp_dir, "intro_hook.mp3")
        tasks.append(sem_tts(clean_tts_speech(intro_hook), voice, rate, p_hook))

        for idx, q in enumerate(questions):
            q_num = q.get("q_num", idx + 1)
            q_txt = q.get("question", "")
            c_opt = str(q.get("correct_option", "A")).upper().strip()
            c_txt = q.get("correct_text", "")
            if not c_txt:
                opt_key = f"option_{c_opt.lower()}"
                opt_val = q.get(opt_key, "")
                c_txt = f"{c_opt}: {opt_val}" if opt_val else c_opt

            clean_q = re.sub(r'^(?:Question\s*\d+:?\s*)', '', q_txt, flags=re.IGNORECASE).strip()
            raw_parts = re.split(r'(?:_{2,}|\.{2,}|\(blank\))', clean_q)
            parts = [clean_tts_speech(p) for p in raw_parts if clean_tts_speech(p)]

            if len(parts) <= 1:
                p_q = os.path.join(temp_dir, f"q_{idx}.mp3")
                tasks.append(sem_tts(clean_tts_speech(f"Question {q_num}: {q_txt}"), voice, rate, p_q))
            else:
                p_q0 = os.path.join(temp_dir, f"q_{idx}_0.mp3")
                tasks.append(sem_tts(clean_tts_speech(f"Question {q_num}: {parts[0]}"), voice, rate, p_q0))
                for p_idx, part in enumerate(parts[1:], 1):
                    p_qp = os.path.join(temp_dir, f"q_{idx}_{p_idx}.mp3")
                    tasks.append(sem_tts(clean_tts_speech(part), voice, rate, p_qp))

            p_ans = os.path.join(temp_dir, f"ans_{idx}.mp3")
            tasks.append(sem_tts(clean_tts_speech(f"Correct answer is {c_txt}"), voice, rate, p_ans))

        p_outro = os.path.join(temp_dir, "outro.mp3")
        tasks.append(sem_tts(clean_tts_speech(outro_text), voice, rate, p_outro))

        await asyncio.gather(*tasks, return_exceptions=True)

    asyncio.run(pregenerate_tts())

    ticking_audio_3s = load_clock_ticking_audio(sample_rate=sample_rate, target_duration=3.0)

    # 1. Intro Hook
    if progress_callback:
        progress_callback("Building Short Quiz Timeline...", 0.15)

    p_hook = os.path.join(temp_dir, "intro_hook.mp3")
    aud_hook = get_audio_from_mp3(p_hook, sample_rate=sample_rate)
    dur_hook = len(aud_hook) / sample_rate

    combined_audio_frames.append(aud_hook)
    timeline.append({
        "start_time": current_time,
        "end_time": current_time + dur_hook,
        "active_state": "INTRO",
        "text": intro_hook
    })
    current_time += dur_hook + 0.4
    combined_audio_frames.append(create_silence(0.4, sample_rate))

    # 2. Questions Loop
    for idx, q in enumerate(questions):
        q_num = q.get("q_num", idx + 1)
        q_txt = q.get("question", "")
        opt_a = q.get("option_a", "")
        opt_b = q.get("option_b", "")
        opt_c = q.get("option_c", "")
        opt_d = q.get("option_d", "")
        c_opt = str(q.get("correct_option", "A")).upper().strip()

        # Step 2a: Read Question Audio with 1.5s silence gap for blanks (____ / ....)
        aud_q, dur_q = prepare_question_audio(q_num, q_txt, temp_dir, idx, sample_rate=sample_rate)

        combined_audio_frames.append(aud_q)
        timeline.append({
            "start_time": current_time,
            "end_time": current_time + dur_q,
            "active_state": "QUESTION_READING",
            "q_num": q_num,
            "question": q_txt,
            "option_a": opt_a,
            "option_b": opt_b,
            "option_c": opt_c,
            "option_d": opt_d,
            "correct_option": c_opt,
            "text": f"Question {q_num}: {q_txt}"
        })
        current_time += dur_q

        # Step 2b: 3-Second Clock Ticking Sound Effect & Timer
        dur_tick = 3.0
        combined_audio_frames.append(ticking_audio_3s)
        timeline.append({
            "start_time": current_time,
            "end_time": current_time + dur_tick,
            "active_state": "QUESTION_TICKING",
            "q_num": q_num,
            "question": q_txt,
            "option_a": opt_a,
            "option_b": opt_b,
            "option_c": opt_c,
            "option_d": opt_d,
            "correct_option": c_opt,
            "text": "3... 2... 1..."
        })
        current_time += dur_tick

        # Step 2c: Reveal & Read Correct Answer Audio
        p_ans = os.path.join(temp_dir, f"ans_{idx}.mp3")
        aud_ans = get_audio_from_mp3(p_ans, sample_rate=sample_rate)
        dur_ans = len(aud_ans) / sample_rate

        combined_audio_frames.append(aud_ans)
        timeline.append({
            "start_time": current_time,
            "end_time": current_time + dur_ans,
            "active_state": "QUESTION_REVEAL",
            "q_num": q_num,
            "question": q_txt,
            "option_a": opt_a,
            "option_b": opt_b,
            "option_c": opt_c,
            "option_d": opt_d,
            "correct_option": c_opt,
            "text": f"Correct answer is {c_opt}"
        })
        current_time += dur_ans + 0.5
        combined_audio_frames.append(create_silence(0.5, sample_rate))

    # 3. Outro CTA
    p_outro = os.path.join(temp_dir, "outro.mp3")
    aud_outro = get_audio_from_mp3(p_outro, sample_rate=sample_rate)
    dur_outro = len(aud_outro) / sample_rate

    combined_audio_frames.append(aud_outro)
    timeline.append({
        "start_time": current_time,
        "end_time": current_time + dur_outro,
        "active_state": "OUTRO",
        "text": outro_text
    })
    current_time += dur_outro

    # Combine & Export Audio WAV using soundfile
    full_audio = np.concatenate(combined_audio_frames)
    os.makedirs(os.path.dirname(output_audio_path), exist_ok=True)
    import soundfile as sf
    sf.write(output_audio_path, full_audio, sample_rate)

    return output_audio_path, timeline, current_time


def draw_centered_wrapped_text(draw, text, font, box, fill_color, line_spacing=1.2):
    """Utility to center multiline wrapped text inside a bounding box [x1, y1, x2, y2]."""
    x1, y1, x2, y2 = box
    max_w = x2 - x1
    max_h = y2 - y1

    words = text.split()
    lines = []
    curr_line = []

    for w in words:
        test_line = " ".join(curr_line + [w])
        if font.getlength(test_line) > max_w and curr_line:
            lines.append(" ".join(curr_line))
            curr_line = [w]
        else:
            curr_line.append(w)
    if curr_line:
        lines.append(" ".join(curr_line))

    line_h = int(font.size * line_spacing)
    tot_h = len(lines) * line_h
    start_y = y1 + (max_h - tot_h) // 2

    for i, line_str in enumerate(lines):
        line_w = font.getlength(line_str)
        cur_x = x1 + (max_w - line_w) // 2
        cur_y = start_y + i * line_h
        draw.text((cur_x, cur_y), line_str, fill=fill_color, font=font)


def render_short_quiz_frame(bg_solid, bg_card, slide_data, current_time, fonts):
    """
    Render 1080x1920 Full HD frame for Short Quiz video.
    """
    active_state = slide_data.get("active_state", "INTRO")
    center_x = 540

    if active_state in ["INTRO", "OUTRO"]:
        canvas = bg_solid.copy()
        draw = ImageDraw.Draw(canvas, "RGBA")

        # Header Title Overlay
        title_txt = "ENGLISH QUIZ CHALLENGE!" if active_state == "INTRO" else "QUIZ COMPLETE!"
        tw = fonts["title"].getlength(title_txt)
        draw.text((int(center_x - tw / 2), 320), title_txt, fill=(255, 215, 0, 255), font=fonts["title"])

        # Main Hook / CTA Text Container
        txt = slide_data.get("text", "")
        draw_centered_wrapped_text(
            draw,
            text=txt,
            font=fonts["hook"],
            box=[120, 520, 960, 1400],
            fill_color=(255, 255, 255, 255),
            line_spacing=1.35
        )

        return canvas

    # Question States (QUESTION_READING, QUESTION_TICKING, QUESTION_REVEAL)
    canvas = bg_card.copy()
    draw = ImageDraw.Draw(canvas, "RGBA")

    q_num = slide_data.get("q_num", 1)
    q_txt = slide_data.get("question", "")
    opt_a = slide_data.get("option_a", "")
    opt_b = slide_data.get("option_b", "")
    opt_c = slide_data.get("option_c", "")
    opt_d = slide_data.get("option_d", "")
    c_opt = str(slide_data.get("correct_option", "A")).upper().strip()

    # 1. Question Number in Top Circle Badge (Center X = 540, Center Y = 245)
    q_num_str = str(q_num)
    nw = fonts["q_num"].getlength(q_num_str)
    draw.text((int(center_x - nw / 2), 222), q_num_str, fill=(255, 255, 255, 255), font=fonts["q_num"])

    # 2. Question Text in Upper Purple Box [120, 260, 960, 760]
    draw_centered_wrapped_text(
        draw,
        text=q_txt,
        font=fonts["q_text"],
        box=[120, 260, 960, 760],
        fill_color=(46, 16, 101, 255),
        line_spacing=1.3
    )

    # 3. 4 Option Boxes Bounding Specifications (1080x1920)
    option_boxes = {
        "A": {"rect": [75, 836, 1002, 966], "text_x": 220, "text_y": 878, "text": opt_a},
        "B": {"rect": [75, 990, 1002, 1120], "text_x": 220, "text_y": 1032, "text": opt_b},
        "C": {"rect": [75, 1143, 1002, 1273], "text_x": 220, "text_y": 1185, "text": opt_c},
        "D": {"rect": [75, 1297, 1002, 1427], "text_x": 220, "text_y": 1339, "text": opt_d}
    }

    # Draw regular text for all options
    for opt_letter, opt_info in option_boxes.items():
        draw.text(
            (opt_info["text_x"], opt_info["text_y"]),
            opt_info["text"],
            fill=(30, 41, 59, 255),
            font=fonts["opt_text"]
        )

    # 4. State: QUESTION_TICKING (3-Second Clock Countdown Timer Animation)
    if active_state == "QUESTION_TICKING":
        start_t = slide_data.get("start_time", current_time)
        end_t = slide_data.get("end_time", current_time + 3.0)
        dur = max(0.1, end_t - start_t)
        rem_sec = max(1, math.ceil(end_t - current_time))

        timer_txt = f"⏳ 00:0{rem_sec}"
        tw = fonts["timer"].getlength(timer_txt)

        # Draw glowing timer badge above options (Y=775)
        draw.rounded_rectangle([center_x - (tw/2) - 20, 775, center_x + (tw/2) + 20, 830], radius=16, fill=(245, 158, 11, 245))
        draw.text((int(center_x - tw / 2), 776), timer_txt, fill=(255, 255, 255, 255), font=fonts["timer"])

    # 5. State: QUESTION_REVEAL (Highlight Correct Option Box)
    if active_state == "QUESTION_REVEAL":
        corr_info = option_boxes.get(c_opt, option_boxes["A"])
        r = corr_info["rect"]
        cy = (r[1] + r[3]) // 2

        # Outer Emerald Green Glowing Border (6px width)
        draw.rounded_rectangle([r[0]-3, r[1]-3, r[2]+3, r[3]+3], radius=32, fill=(16, 185, 129, 240))
        # Inner Emerald Soft Tint
        draw.rounded_rectangle([r[0], r[1], r[2], r[3]], radius=28, fill=(236, 253, 245, 255))

        # Circle icon highlight letter: Perfect crisp 88x88px circle at X=138
        draw.ellipse([94, cy - 44, 182, cy + 44], fill=(16, 185, 129, 255))
        lw = fonts["opt_text"].getlength(c_opt)
        draw.text((int(138 - lw / 2), cy - 28), c_opt, fill=(255, 255, 255, 255), font=fonts["opt_text"])

        # Correct Option Text in Bright Emerald Bold
        draw.text(
            (corr_info["text_x"], corr_info["text_y"]),
            corr_info["text"],
            fill=(4, 120, 87, 255),
            font=fonts["opt_text"]
        )

    return canvas


def render_short_quiz_video(
    script_data,
    voice="en-US-JennyNeural",
    rate="-5%",
    output_video_path="output/short_quiz_output.mp4",
    progress_callback=None
):
    """
    Render 1080x1920 9:16 Short Question Video with FFmpeg pipe stream.
    """
    os.makedirs("output", exist_ok=True)
    audio_path = "output/short_quiz_audio.wav"

    print("Building Short Quiz audio timeline...")
    audio_path, timeline, total_duration = build_short_quiz_audio_and_timeline(
        script_data,
        voice=voice,
        rate=rate,
        output_audio_path=audio_path,
        progress_callback=progress_callback
    )

    print(f"Short Quiz Audio Ready! Duration: {total_duration:.2f}s")
    bg_solid, bg_card = load_quiz_backgrounds()
    fonts = get_quiz_fonts()

    fps = 24
    total_frames = int(total_duration * fps)

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    temp_raw_video = output_video_path + ".raw.mp4"

    cmd = [
        ffmpeg_exe,
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", "1080x1920",
        "-pix_fmt", "rgb24",
        "-r", str(fps),
        "-i", "-",
        "-i", audio_path,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        temp_raw_video
    ]

    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    print(f"Rendering Short Quiz Video ({total_frames} frames)...")

    prev_slide = None
    prev_frame_img = None

    for frame_idx in range(total_frames):
        current_time = frame_idx / fps

        # Find active slide (remains on current slide during silence gaps, preventing OUTRO flashing)
        active_slide = timeline[0]
        for slide in timeline:
            if current_time >= slide["start_time"]:
                active_slide = slide
            else:
                break

        frame_img = render_short_quiz_frame(bg_solid, bg_card, active_slide, current_time, fonts)

        # Smooth 0.3s Cross-Fade Transition when transitioning between question numbers
        if (prev_slide and 
            prev_slide.get("active_state") != "INTRO" and 
            active_slide.get("active_state") == "QUESTION_READING" and
            prev_slide.get("q_num") != active_slide.get("q_num")):
            trans_start = active_slide["start_time"]
            trans_dur = 0.3
            if current_time - trans_start < trans_dur and prev_frame_img is not None:
                alpha = (current_time - trans_start) / trans_dur
                frame_img = Image.blend(prev_frame_img, frame_img, alpha)

        prev_slide = active_slide
        prev_frame_img = frame_img.copy()

        frame_rgb = frame_img.convert("RGB")
        process.stdin.write(frame_rgb.tobytes())

        if progress_callback and frame_idx % 24 == 0:
            prog = 0.2 + 0.8 * (frame_idx / total_frames)
            progress_callback(f"Rendering Short Quiz Video ({frame_idx}/{total_frames})...", prog)

    process.stdin.close()
    process.wait()

    if os.path.exists(temp_raw_video):
        if os.path.exists(output_video_path):
            os.remove(output_video_path)
        os.rename(temp_raw_video, output_video_path)

    print(f"Short Quiz Video exported successfully: {output_video_path}")
    return output_video_path
