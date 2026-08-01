import os
import sys
import time
import math
import subprocess
import re
import numpy as np
import av
import imageio_ffmpeg
import scipy.io.wavfile as wav
from PIL import Image, ImageDraw, ImageFont

def compute_real_audio_waveform(wav_path, num_bars=45, fps=24, smooth_factor=0.82, gamma=1.4, min_h=3, max_h=120):
    """
    Compute smooth log-frequency FFT audio visualizer matching user preferences.
    FFT Size: 2048, Bars: 45, Max Height: 120px, Smooth: 0.82.
    """
    if not wav_path or not os.path.exists(wav_path):
        return {}

    try:
        sr, audio = wav.read(wav_path)
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        elif audio.dtype == np.int32:
            audio = audio.astype(np.float32) / 2147483648.0

        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)

        total_samples = len(audio)
        samples_per_frame = int(sr / fps)
        total_frames = int(total_samples / samples_per_frame) + 1

        n_fft = 2048
        freq_bins = np.logspace(np.log10(2), np.log10(n_fft // 2 - 10), num_bars + 1, dtype=int)

        frame_waveforms = {}
        prev_bars = np.zeros(num_bars, dtype=np.float32)

        for f in range(total_frames):
            center_sample = f * samples_per_frame
            s_start = max(0, center_sample - n_fft // 2)
            s_end = min(total_samples, s_start + n_fft)
            
            chunk = audio[s_start:s_end]
            if len(chunk) < n_fft:
                chunk = np.pad(chunk, (0, n_fft - len(chunk)))

            windowed = chunk * np.hanning(len(chunk))
            fft_mag = np.abs(np.fft.rfft(windowed))

            raw_bars = np.zeros(num_bars, dtype=np.float32)
            for i in range(num_bars):
                b_start = freq_bins[i]
                b_end = max(b_start + 1, freq_bins[i+1])
                raw_bars[i] = np.mean(fft_mag[b_start:b_end])

            max_val = np.max(raw_bars) if np.max(raw_bars) > 1e-5 else 1.0
            norm_bars = np.clip(raw_bars / max_val, 0.0, 1.0)
            gamma_bars = np.power(norm_bars, gamma)

            smoothed_bars = prev_bars * smooth_factor + gamma_bars * (1.0 - smooth_factor)
            prev_bars = smoothed_bars

            heights = [int(min_h + b * (max_h - min_h)) for b in smoothed_bars]
            frame_waveforms[f] = heights

        return frame_waveforms
    except Exception as e:
        print(f"Warning: Error computing FFT soundwave: {e}")
        return {}

def draw_soundwave_graphic(draw, real_bar_heights=None, center_x=1440, center_y=615, num_bars=45, bar_color=None):
    """
    Draw dynamic white or forest green capsule Soundwave visualizer.
    """
    bar_width = 6
    gap = 4
    total_w = num_bars * bar_width + (num_bars - 1) * gap
    start_x = int(center_x - (total_w / 2))
    
    if not real_bar_heights or len(real_bar_heights) < num_bars:
        real_bar_heights = [3] * num_bars

    for i in range(num_bars):
        h = real_bar_heights[i] if i < len(real_bar_heights) else 3
        x = int(start_x + i * (bar_width + gap))

        # Mirror symmetric above and below center line
        y1 = center_y - (h // 2)
        y2 = center_y + (h // 2)

        alpha = 230 if h > 5 else 130
        if bar_color:
            color = (bar_color[0], bar_color[1], bar_color[2], alpha)
        else:
            color = (255, 255, 255, alpha)

        if h <= bar_width:
            r = bar_width // 2
            draw.ellipse([x, center_y - r, x + bar_width, center_y + r], fill=color)
        else:
            draw.rounded_rectangle([x, y1, x + bar_width, y2], radius=bar_width // 2, fill=color)

def load_video_frames_to_ram(video_path, target_size=(1920, 1080)):
    """
    Load all frames of a background video into memory as PIL RGB images
    and resize to Full HD 1920x1080 resolution.
    """
    if video_path == "white" or not os.path.exists(video_path):
        return [Image.new("RGB", target_size, (255, 255, 255))]
    container = av.open(video_path)
    frames = []
    for frame in container.decode(video=0):
        img = frame.to_image().convert("RGB")
        if img.size != target_size:
            img = img.resize(target_size, Image.Resampling.LANCZOS)
        frames.append(img)
    container.close()
    return frames

def is_vocab_in_text(v_word, text):
    """Smart matching helper to detect key vocabulary phrases even with verb tense variations (e.g. hold back vs holding back)."""
    if not v_word or not text:
        return False
    v_clean = re.sub(r'[^\w\s]', '', v_word.lower())
    t_clean = re.sub(r'[^\w\s]', '', text.lower())
    
    v_tokens = v_clean.split()
    if not v_tokens:
        return False
        
    t_tokens = t_clean.split()
    matched_count = 0
    for tok in v_tokens:
        tok_stem = tok[:4] if len(tok) >= 4 else tok
        if any(tt.startswith(tok_stem) or tok_stem in tt for tt in t_tokens):
            matched_count += 1
            
    return matched_count >= len(v_tokens) - (1 if len(v_tokens) > 2 else 0)

def render_frame_overlay(base_img, text, words, active_time, progress_ratio, font_large, font_small, section_type="intro_story", key_vocab_list=None, target_word="", meaning="", quiz_data=None, real_bar_heights=None):
    """
    Draw subtitle text with active word red highlighting, goal progress bar, 
    Chapter Badges, and Key Word Popups onto base_img for Full HD 1080p (1920x1080).
    """
    img = base_img.copy()
    draw = ImageDraw.Draw(img, "RGBA")

    # 1. Render Chapter Badge in Top-Right Overlay (Shifted right, centered, larger 44px bold font)
    badge_text = "Part 1: Introduction"
    if section_type in ["intro_quiz", "quiz"]:
        badge_text = "Part 2: Question"
    elif section_type == "shadowing_practice":
        badge_text = "Part 3: Shadowing Practice"
    elif section_type == "review":
        badge_text = "Part 4: Conclusion"
    elif section_type == "podcast_conversation":
        badge_text = "Podcast Conversation"
    elif section_type == "ielts_listening":
        badge_text = "IELTS Listening Practice"

    try:
        font_badge = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 34)
    except:
        font_badge = font_large

    # Center align badge text and background pill badge at (X=1440, Y=180)
    badge_center_x = 1440
    badge_center_y = 180

    bbox = font_badge.getbbox(badge_text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    padding_x = 26
    padding_y = 12

    bg_rect = [
        badge_center_x - (text_w / 2) - padding_x,
        badge_center_y - (text_h / 2) - padding_y,
        badge_center_x + (text_w / 2) + padding_x,
        badge_center_y + (text_h / 2) + padding_y
    ]
    draw.rounded_rectangle(bg_rect, radius=18, fill=(70, 94, 76, 240))

    # Draw Badge Text with anchor='mm' for 100% PERFECT VERTICAL & HORIZONTAL CENTERING
    draw.text((badge_center_x, badge_center_y - 2), badge_text, fill=(255, 255, 255, 255), font=font_badge, anchor="mm")

    x_start, y_start = 1020, 270

    # -------------------------------------------------------------
    # DEDICATED FULLSCREEN QUIZ FRAME (Switches Frame to Card Image)
    # -------------------------------------------------------------
    if quiz_data:
        card_path = r"C:\Users\hinht\Downloads\shadowingEnglish\image\Screenshot 2026-07-31 170819.png"
        if os.path.exists(card_path):
            try:
                card_img = Image.open(card_path).convert("RGB")
                img = card_img.resize((1920, 1080), Image.Resampling.LANCZOS)
            except Exception as e:
                print(f"Warning: Could not load card background image: {e}")

        draw = ImageDraw.Draw(img, "RGBA")

        # Chapter Badge Top Right on Fullscreen Card (Centered at x=1480, 44px bold font)
        card_badge_w = font_badge.getlength("Part 2: Question")
        card_badge_x = int(1480 - (card_badge_w / 2))
        draw.text((card_badge_x, 85), "Part 2: Question", fill=(24, 76, 140, 255), font=font_badge)

        q_num = quiz_data.get("q_num", 1)
        q_str = quiz_data.get("question", "")
        oa = quiz_data.get("option_a", "")
        ob = quiz_data.get("option_b", "")
        oc = quiz_data.get("option_c", "")
        od = quiz_data.get("option_d", "")
        c_opt = quiz_data.get("correct_option", "A")
        c_text = quiz_data.get("correct_text", "")
        exp = quiz_data.get("explanation", "")
        reveal_t = quiz_data.get("reveal_start", 999999.0)
        is_c = quiz_data.get("is_challenge", False)
        q_words = quiz_data.get("words", [])

        # Find currently active spoken word object directly from timestamp (with 0.15s silence bridging)
        active_w_obj = None
        if q_words:
            for i, w in enumerate(q_words):
                if w['start'] <= active_time <= w['end']:
                    active_w_obj = w
                    break
                elif i < len(q_words) - 1:
                    # Bridge tiny silences between consecutive words so word highlighting flows 100% smooth without flickering!
                    if w['end'] < active_time < q_words[i+1]['start'] and (active_time - w['end'] < 0.15):
                        active_w_obj = w
                        break

        active_part = active_w_obj.get('part', '') if active_w_obj else ''
        active_word_clean = re.sub(r'[^\w]', '', active_w_obj.get('word', '').lower()) if active_w_obj else ''

        try:
            font_q = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 38)
            font_opt = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 36)
            font_ans = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 36)
            font_exp = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 30)
        except:
            font_q = font_large
            font_opt = font_small
            font_ans = font_small
            font_exp = font_small

        import textwrap
        start_x = 480
        # START BELOW GIANT BAKED-IN QUESTION HEADER IMAGE (Shifted down slightly to Y = 425)
        y_curr = 425

        opt_times = quiz_data.get("opt_times", {})

        # 1. Render Question Text as "Q1: ..."
        q_clean = q_str
        if q_clean.lower().startswith(f"question {q_num}"):
            q_clean = re.sub(r"^question\s*\d+[\:\.\s]*", "", q_clean, flags=re.IGNORECASE).strip()

        full_q_header = f"Q{q_num}: {q_clean}"
        q_lines = textwrap.wrap(full_q_header, width=46)

        for q_l in q_lines:
            curr_x = start_x
            for word in q_l.split():
                clean_w = re.sub(r'[^\w]', '', word.lower())
                is_w_active = (active_part == 'question') and (clean_w == active_word_clean)
                w_color = (255, 30, 0) if is_w_active else (25, 25, 25)
                draw.text((curr_x, y_curr), word + " ", fill=w_color, font=font_q)
                curr_x += font_q.getlength(word + " ")
            y_curr += 44

        y_curr += 16 # Gap before options

        # 2. Render 4 Options A, B, C, D with Continuous Line + Word-Level Extra Red Highlighting
        opts = [("A", oa), ("B", ob), ("C", oc), ("D", od)]
        for letter, opt_val in opts:
            target_part = f"option_{letter}"
            is_line_active = False
            if letter in opt_times:
                s_t, e_t = opt_times[letter]
                if s_t <= active_time <= e_t:
                    is_line_active = True
            if not is_line_active:
                is_line_active = (active_part == target_part)

            # Draw Option Label: "A ) "
            label = f"{letter} ) "
            label_color = (255, 30, 0) if is_line_active else (215, 130, 20)
            draw.text((start_x, y_curr), label, fill=label_color, font=font_opt)
            lbl_w = font_opt.getlength(label)

            # Draw Option Text words (Word highlight ONLY when Host Annie speaks this specific option!)
            curr_x = start_x + lbl_w
            for word in opt_val.split():
                clean_w = re.sub(r'[^\w]', '', word.lower())
                is_w_active = (active_part == target_part) and (clean_w == active_word_clean)
                word_color = (255, 30, 0) if is_w_active else ((225, 90, 20) if is_line_active else (60, 60, 60))
                draw.text((curr_x, y_curr), word + " ", fill=word_color, font=font_opt)
                curr_x += font_opt.getlength(word + " ")

            y_curr += 48

        y_curr += 14 # Gap before answer reveal

        # 3. Render Answer Reveal Line & Explanation Text (after 3s clock ticking pause)
        if active_time >= reveal_t:
            if not is_c:
                clean_ans = c_text[:42] + ("..." if len(c_text) > 42 else "")
                ans_str = f"Correct answer : {c_opt} ) {clean_ans}"
                draw.text((start_x, y_curr), ans_str, fill=(30, 126, 52), font=font_ans)
                y_curr += 42

                if exp:
                    exp_header = f"Explanation: {exp}"
                    exp_lines = textwrap.wrap(exp_header, width=54)
                    for e_l in exp_lines[:2]:
                        curr_x = start_x
                        for word in e_l.split():
                            clean_w = re.sub(r'[^\w]', '', word.lower())
                            is_w_active = (active_part == 'reveal') and (clean_w == active_word_clean)
                            word_color = (255, 30, 0) if is_w_active else (50, 50, 50)
                            draw.text((curr_x, y_curr), word + " ", fill=word_color, font=font_exp)
                            curr_x += font_exp.getlength(word + " ")
                        y_curr += 36
            else:
                ans_str = "Comment your answer A, B, C, or D below!"
                draw.text((start_x, y_curr), ans_str, fill=(217, 56, 30), font=font_ans)

        return img

    # Determine active word index (if any)
    active_word_idx = -1
    if words:
        for idx, w in enumerate(words):
            if w['start'] <= active_time <= w['end']:
                active_word_idx = idx
                break

    words_list = text.split()

    # 1080p Coordinates (1920x1080)
    x_start, y_start = 1070, 260
    max_w = 740

    # Determine dynamic font size based on word count & section type (Larger & more prominent subtitles)
    try:
        current_font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 64)
    except:
        current_font = font_large
    line_height = 86

    if len(words_list) > 10:
        try:
            current_font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 56)
        except:
            current_font = font_large
        line_height = 76

    is_quiz_text = (section_type in ["intro_story", "intro_quiz"]) and any(k in text.lower() for k in ["option", "choice", "a:", "b:", "c:", "d:"])
    
    if is_quiz_text:
        try:
            current_font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 42)
        except:
            current_font = font_small
        line_height = 56

    lines = []
    curr_line = []
    curr_w = 0

    for i, w in enumerate(words_list):
        w_len = current_font.getlength(w + " ")
        
        # Force a NEW LINE whenever a new Option (Option A, Option B, Option C, Option D) starts!
        is_option_start = False
        if w.upper() == "OPTION" and i > 0 and curr_line:
            # Check if this is Option B, Option C, Option D starting a new option
            is_option_start = True

        if (curr_w + w_len > max_w or is_option_start) and curr_line:
            lines.append(curr_line)
            curr_line = [(w, i)]
            curr_w = w_len
        else:
            curr_line.append((w, i))
            curr_w += w_len
    if curr_line:
        lines.append(curr_line)

    center_x = 1440
    y = y_start
    for line in lines:
        line_w = sum(current_font.getlength(w + " ") for w, _ in line) - current_font.getlength(" ")
        x = int(center_x - (line_w / 2))
        for word, idx in line:
            color = (225, 30, 0) if idx == active_word_idx else (20, 20, 20)
            
            # Highlight Option A, B, C, D headers in Gold/Orange
            if word.upper() in ["OPTION", "A:", "B:", "C:", "D:", "QUESTION"]:
                color = (215, 130, 20)

            # Draw subtle text shadow for crisp contrast
            draw.text((x + 2, y + 2), word, fill=(245, 240, 235, 200), font=current_font)
            # Main text
            draw.text((x, y), word, fill=color, font=current_font)
            
            x += int(current_font.getlength(word + " "))
        y += line_height

    # Render Green Correct Answer Popup Banner (e.g. CORRECT ANSWER : B ) Break the ice) when answer is revealed
    if section_type == "intro_story" and "correct answer" in text.lower():
        ans_str = text.strip()
        ans_text = "CORRECT ANSWER :"
        m = re.search(r"Option\s*([A-D])(?:\:|\s*)(.*)", ans_str, flags=re.IGNORECASE)
        if m:
            opt_letter = m.group(1).upper()
            opt_content = m.group(2).strip("!.")
            ans_text = f"CORRECT ANSWER : {opt_letter} ) {opt_content}"
        else:
            clean_r = re.sub(r"(?i)the\s*correct\s*answer\s*is\s*", "", ans_str).strip("!.")
            ans_text = f"CORRECT ANSWER : {clean_r}"

        box_y = 580
        draw.rounded_rectangle([x_start, box_y, x_start + 735, box_y + 70], radius=12, fill=(235, 247, 238), outline=(40, 167, 69), width=2)
        draw.text((x_start + 20, box_y + 16), ans_text, fill=(30, 126, 52), font=font_small)

    # Draw dynamic white or forest green capsule Soundwave visualizer driven by REAL audio data (Centered at X=1440, Y=615)
    sw_color = (70, 94, 76) if section_type in ["podcast_conversation", "ielts_listening"] else None
    draw_soundwave_graphic(draw, real_bar_heights=real_bar_heights, center_x=1440, center_y=615, num_bars=45, bar_color=sw_color)

    # Render Tip text centered at X=1440, with larger 34px font for prominent visibility
    curr_target = target_word.strip() if target_word else ""
    curr_meaning = meaning.strip() if meaning else ""

    if section_type == "shadowing_practice" and not curr_target and key_vocab_list:
        for item in key_vocab_list:
            v_word = item.get("word", "").strip()
            v_meaning = item.get("meaning", "").strip()
            if v_word and is_vocab_in_text(v_word, text):
                curr_target = v_word
                curr_meaning = v_meaning
                break

    if section_type == "shadowing_practice" and curr_target:
        try:
            font_tip = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 34)
        except:
            font_tip = font_small

        y_tip = 675
        w_title = f'Tip: the word "{curr_target}" means'
        w_title_len = font_tip.getlength(w_title)
        x_title = int(1440 - (w_title_len / 2))
        
        draw.text((x_title + 1, y_tip + 1), w_title, fill=(240, 240, 240, 160), font=font_tip)
        draw.text((x_title, y_tip), w_title, fill=(215, 130, 20, 255), font=font_tip)
        
        w_mean = f"{curr_meaning}"
        words_m = w_mean.split()
        m_lines = []
        c_line = ""
        for w in words_m:
            test_l = (c_line + " " + w).strip()
            if font_tip.getlength(test_l) <= 735:
                c_line = test_l
            else:
                m_lines.append(c_line)
                c_line = w
        if c_line:
            m_lines.append(c_line)
            
        y_m = y_tip + 38
        for m_line in m_lines[:2]:
            m_len = font_tip.getlength(m_line)
            x_m = int(1440 - (m_len / 2))
            draw.text((x_m + 1, y_m + 1), m_line, fill=(240, 240, 240, 160), font=font_tip)
            draw.text((x_m, y_m), m_line, fill=(35, 35, 35, 255), font=font_tip)
            y_m += 30

    # Goal Progress Bar 1080p (Shifted right to X=1470, Y=805)
    bar_w, bar_h = 705, 26
    bar_x = int(1470 - (bar_w / 2))
    bar_y = 805
    
    # Outer Bar Track (soft cream fill)
    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=13, fill=(239, 232, 220, 255))
    
    # Progress Fill (Forest Green #4A6B53)
    fill_w = int(bar_w * max(0.0, min(1.0, progress_ratio)))
    if fill_w > 0:
        draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], radius=13, fill=(70, 94, 76, 255))

    # Clean text 'Your Goal' or '100% COMPLETED' Banner placed ABOVE top-right of progress bar
    try:
        font_goal = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 30)
    except:
        font_goal = font_small

    goal_label = "100% COMPLETED" if (progress_ratio >= 0.98 or section_type == "review") else "Your Goal"
    draw.text((bar_x + bar_w - 145, bar_y - 42), goal_label, fill=(70, 94, 76), font=font_goal)

    return img

def render_lesson_video(bgtalk_path, bgnotalk_path, audio_path, timeline, total_duration, output_video_path, progress_callback=None, key_vocab_list=None):
    """
    Render lesson video in Full HD 1080p (1920x1080) resolution
    with background looping, PIL text/goal bar overlays, and audio.
    """
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    print("Pre-loading background video frames into RAM in 1080p Full HD (1920x1080)...")
    bgtalk_frames = load_video_frames_to_ram(bgtalk_path, target_size=(1920, 1080))
    bgnotalk_frames = load_video_frames_to_ram(bgnotalk_path, target_size=(1920, 1080))

    n_talk = len(bgtalk_frames)
    n_notalk = len(bgnotalk_frames)

    font_path = "C:/Windows/Fonts/segoeuib.ttf"
    try:
        font_large = ImageFont.truetype(font_path, 54)
        font_small = ImageFont.truetype(font_path, 33)
    except:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    fps = 24
    total_frames = int(total_duration * fps)

    print("Extracting 45-bar dynamic FFT audio visualizer (max height 120px)...")
    real_waveforms = compute_real_audio_waveform(audio_path, num_bars=45, fps=fps, smooth_factor=0.82, gamma=1.4, max_h=120)

    w, h = 1920, 1080
    encoder = "libx264"
    preset_args = ["-preset", "ultrafast", "-crf", "22"]

    cmd = [
        ffmpeg_exe, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{w}x{h}",
        "-pix_fmt", "rgb24",
        "-r", str(fps),
        "-i", "-", # Stdin pipe
        "-i", audio_path, # Audio track
        "-c:v", encoder,
        *preset_args,
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-pix_fmt", "yuv420p",
        output_video_path
    ]

    pipe = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def get_timeline_at(t):
        for item in timeline:
            if item['start_time'] <= t <= item['end_time']:
                return item
        return None

    last_item = None

    for f_idx in range(total_frames):
        t = f_idx / fps
        progress_ratio = t / max(0.1, total_duration)

        item = get_timeline_at(t)
        if item is None and last_item is not None:
            item = last_item
        elif item is not None:
            last_item = item

        is_talking = item.get('is_talking', False) if item else False
        text = item.get('text', '') if item else ''
        words = item.get('words', []) if item else []

        sec_type = item.get('section_type', 'intro_story') if item else 'intro_story'

        # Frame selection logic: Solid white background for Podcast & IELTS modes (or when specified as white)
        if sec_type in ["podcast_conversation", "ielts_listening"] or bgtalk_path == "white":
            base_frame = Image.new("RGB", (1920, 1080), (255, 255, 255))
        elif is_talking:
            base_frame = bgnotalk_frames[f_idx % n_notalk]
        else:
            base_frame = bgtalk_frames[f_idx % n_talk]
        t_word = item.get('target_word', '') if item else ''
        t_meaning = item.get('meaning', '') if item else ''
        q_data = item.get('quiz_data') if item else None

        real_bar_heights = real_waveforms.get(f_idx, None)
        rendered_img = render_frame_overlay(base_frame, text, words, t, progress_ratio, font_large, font_small, section_type=sec_type, key_vocab_list=key_vocab_list, target_word=t_word, meaning=t_meaning, quiz_data=q_data, real_bar_heights=real_bar_heights)
        
        raw_bytes = rendered_img.tobytes()
        pipe.stdin.write(raw_bytes)

        if f_idx % 48 == 0:
            pct = 0.4 + (f_idx / max(1, total_frames)) * 0.5
            if progress_callback:
                progress_callback(f"Rendering 1080p Video Frames ({f_idx}/{total_frames} frames)...", round(pct, 2))

    pipe.stdin.close()
    pipe.wait()
    print("1080p Video frame rendering completed.")

def concat_intro_and_lesson(intro_path, lesson_video_path, final_output_path, progress_callback=None, outro_path=None):
    """
    Concatenate intro.mp4, lesson_video_path, and optional outro_path (e.g. video/outtro.mp4) into final_output_path in 1920x1080 Full HD.
    """
    if progress_callback:
        progress_callback("Stitching Channel Intro, Lesson Video & Outro...", 0.95)

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    video_inputs = []
    if intro_path and os.path.exists(intro_path):
        video_inputs.append(intro_path)
    if lesson_video_path and os.path.exists(lesson_video_path):
        video_inputs.append(lesson_video_path)
    if outro_path and os.path.exists(outro_path):
        video_inputs.append(outro_path)

    if not video_inputs:
        raise ValueError("Không tìm thấy file video hợp lệ để ghép nối!")

    if len(video_inputs) == 1:
        import shutil
        shutil.copy(video_inputs[0], final_output_path)
        return

    cmd = [ffmpeg_exe, "-y"]
    for v_p in video_inputs:
        cmd.extend(["-i", v_p])

    filter_str = ""
    for idx in range(len(video_inputs)):
        filter_str += f"[{idx}:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2[v{idx}]; "

    concat_inputs = ""
    for idx in range(len(video_inputs)):
        concat_inputs += f"[v{idx}][{idx}:a]"

    filter_str += f"{concat_inputs}concat=n={len(video_inputs)}:v=1:a=1[v][a]"

    cmd.extend([
        "-filter_complex", filter_str,
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "192k",
        final_output_path
    ])

    subprocess.run(cmd, check=True)
    print(f"Concat {len(video_inputs)} 1080p video clips completed successfully!")
