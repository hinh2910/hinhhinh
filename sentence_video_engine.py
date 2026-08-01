import os
import sys
import time
import math
import subprocess
import re
import numpy as np
import av
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

from video_engine import compute_real_audio_waveform, draw_soundwave_graphic

def get_sentence_fonts():
    """Load bold, high-definition Segoe UI fonts matching video_engine.py L352-L370."""
    font_path_bold = "C:/Windows/Fonts/segoeuib.ttf"
    try:
        font_num = ImageFont.truetype(font_path_bold, 46)
        font_main = ImageFont.truetype(font_path_bold, 68)             # Prominent 68pt bold for mobile
        font_main_small = ImageFont.truetype(font_path_bold, 56)       # Clean 56pt bold for longer sentences
        font_exp = ImageFont.truetype(font_path_bold, 46)              # Crisp 46pt bold
        font_dlg_hdr = ImageFont.truetype(font_path_bold, 38)
        font_dlg_body = ImageFont.truetype(font_path_bold, 46)         # Prominent 46pt bold
        font_dlg_body_small = ImageFont.truetype(font_path_bold, 38)   # Clean 38pt bold for longer dialogue
        font_status = ImageFont.truetype(font_path_bold, 48)
    except Exception as e:
        print(f"Warning loading Segoe UI fonts ({e}), fallback to default...")
        font_num = ImageFont.load_default()
        font_main = font_num
        font_main_small = font_num
        font_exp = font_num
        font_dlg_hdr = font_num
        font_dlg_body = font_num
        font_dlg_body_small = font_num
        font_status = font_num

    return {
        "num": font_num,
        "main": font_main,
        "main_small": font_main_small,
        "exp": font_exp,
        "dlg_hdr": font_dlg_hdr,
        "dlg_body": font_dlg_body,
        "dlg_body_small": font_dlg_body_small,
        "status": font_status
    }



def is_word_in_target(word_str, target_word):
    """
    Check if word_str matches target_word (single word or multi-word phrase).
    Avoids false positives from substring matching (e.g., 'in' in 'going').
    """
    if not word_str or not target_word:
        return False
    w_clean = re.sub(r'[^\w]', '', word_str.lower())
    if not w_clean:
        return False
    t_clean = re.sub(r'[^\w\s]', '', target_word.lower())
    t_tokens = [re.sub(r'[^\w]', '', t) for t in t_clean.split() if re.sub(r'[^\w]', '', t)]
    if not t_tokens:
        return False
    for tok in t_tokens:
        tok_stem = tok[:4] if len(tok) >= 4 else tok
        if w_clean == tok or (len(tok_stem) >= 4 and w_clean.startswith(tok_stem)):
            return True
    return False

def get_active_word_index(words, active_time):
    """
    Find active word index from Whisper timestamps with 0.15s silence bridging.
    """
    if not words:
        return -1
    for idx, w in enumerate(words):
        if w['start'] <= active_time <= w['end']:
            return idx
        elif w['end'] < active_time:
            next_start = words[idx+1]['start'] if idx < len(words) - 1 else w['end'] + 0.15
            if active_time < next_start and (active_time - w['end'] < 0.15):
                return idx
    return -1

def draw_text_with_word_indices(
    draw,
    text,
    words,
    font,
    x_pos,
    y_start,
    max_w,
    active_time,
    normal_color=(30, 41, 59, 255),        # Slate Navy (#1E293B) matching video_engine.py
    highlight_color=(225, 29, 72, 255),    # Crimson Red (#E11D48) matching video_engine.py
    target_word="",
    align_center=False,
    line_spacing_mult=1.38,
    max_lines=3,
    start_time=0.0,
    end_time=0.0
):
    """
    Word-index subtitle rendering with automatic 3-line multi-page pagination:
    - Keeps full 38pt font size BIG & CRISP (no shrinking).
    - Splits text into 3-line pages and flips automatically as audio reads through.
    - Highlights ONLY the exact word index `i == active_word_idx`.
    """
    if not text:
        return y_start

    t_mod = re.sub(r'[—–]', ' ', text)
    words_list = t_mod.split()
    if not words_list:
        return y_start

    active_word_idx = get_active_word_index(words, active_time)

    lines = []
    curr_line = []
    curr_w = 0

    for i, w in enumerate(words_list):
        w_len = font.getlength(w + " ")
        if curr_w + w_len > max_w and curr_line:
            lines.append(curr_line)
            curr_line = [(w, i)]
            curr_w = w_len
        else:
            curr_line.append((w, i))
            curr_w += w_len
    if curr_line:
        lines.append(curr_line)

    # Multi-page pagination: group lines into 3-line pages and switch pages smoothly as audio reads
    if max_lines and len(lines) > max_lines:
        pages = [lines[p : p + max_lines] for p in range(0, len(lines), max_lines)]
        
        current_page_idx = 0
        if active_word_idx >= 0:
            for p_idx, page in enumerate(pages):
                first_w_idx = page[0][0][1]
                if active_word_idx >= first_w_idx:
                    current_page_idx = p_idx
        else:
            # Fallback based on time ratio during silent gaps between words to prevent any flickering
            if end_time > start_time and active_time >= start_time:
                if active_time >= end_time:
                    current_page_idx = len(pages) - 1
                else:
                    ratio = (active_time - start_time) / (end_time - start_time)
                    current_page_idx = min(len(pages) - 1, int(ratio * len(pages)))

        lines_to_draw = pages[current_page_idx]
    else:
        lines_to_draw = lines

    curr_y = y_start
    line_h = int(font.size * line_spacing_mult)

    for line in lines_to_draw:
        line_w = sum(font.getlength(w + " ") for w, _ in line) - font.getlength(" ")
        curr_x = int(x_pos - (line_w / 2)) if align_center else x_pos

        for word_str, idx in line:
            # Exact index match for spoken red highlight
            if idx == active_word_idx:
                color = highlight_color
            elif target_word and is_word_in_target(word_str, target_word):
                color = (217, 119, 6, 255)  # Amber Orange (#D97706)
            else:
                color = normal_color

            # Main bold text
            draw.text((curr_x, curr_y), word_str, fill=color, font=font)
            curr_x += int(font.getlength(word_str + " "))

        curr_y += line_h

    return curr_y

def render_sentence_frame(
    bg_image,
    slide_data,
    current_time,
    total_duration,
    fonts,
    real_bar_heights=None
):
    """
    Render 1920x1080 Full HD video frame for Type 3: Sentence Video.
    Background: image/ce3aca79-22d2-46aa-8259-85f8b5c2af7b (1).png
    Host avatar is fixed on the right side (X > 1150).
    Working canvas area: Left side X in [180, 1120], Center X = 650.
    """
    canvas = bg_image.copy()
    draw = ImageDraw.Draw(canvas, "RGBA")

    if not slide_data:
        return canvas

    active_state = slide_data.get("active_state", "INTRO")
    num = slide_data.get("sentence_num", 0)
    main_sent = slide_data.get("main_sentence", "")
    target_word = slide_data.get("target_word", "")
    explanation = slide_data.get("explanation", "")
    q_text = slide_data.get("dialogue_question", "")
    a_text = slide_data.get("dialogue_answer", "")
    is_pause = slide_data.get("is_pause", False)
    words = slide_data.get("words", [])

    center_x = 650

    # 1. INTRO / OUTRO STAGE
    if active_state in ["INTRO", "OUTRO"]:
        title_text = "SHADOW ENGLISH" if active_state == "INTRO" else "GREAT JOB TODAY!"
        t_w = fonts["main"].getlength(title_text)
        draw.text((int(center_x - t_w / 2), 170), title_text, fill=(30, 41, 59, 255), font=fonts["main"])

        start_t = slide_data.get("start_time", 0.0)
        end_t = slide_data.get("end_time", 1.0)

        # Draw with full 46pt BOLD FONT without pagination limit so full intro monologue is displayed without page jumps
        draw_text_with_word_indices(
            draw,
            text=explanation,
            words=words,
            font=fonts["exp"],           # ALWAYS BIG 46pt BOLD FONT!
            x_pos=center_x,
            y_start=280,
            max_w=850,
            active_time=current_time,
            normal_color=(51, 65, 85, 255),
            align_center=True,
            max_lines=None,
            start_time=start_t,
            end_time=end_t
        )

        draw_soundwave_graphic(draw, real_bar_heights, center_x=center_x, center_y=900, num_bars=35, bar_color=(217, 119, 6))
        return canvas



    # 1b. CHAPTER PART BADGE (Top-Right Overlay at X=1440, Y=70)
    part_name = slide_data.get("part_name", "")
    if part_name and part_name not in ["Intro", "Outro"]:
        badge_center_x, badge_center_y = 1440, 70
        bbox = fonts["num"].getbbox(part_name)
        t_w = bbox[2] - bbox[0]
        t_h = bbox[3] - bbox[1]
        p_x, p_y = 24, 10
        bg_rect = [
            badge_center_x - (t_w / 2) - p_x,
            badge_center_y - (t_h / 2) - p_y,
            badge_center_x + (t_w / 2) + p_x,
            badge_center_y + (t_h / 2) + p_y
        ]
        draw.rounded_rectangle(bg_rect, radius=16, fill=(217, 119, 6, 235))
        draw.text((badge_center_x, badge_center_y - 2), part_name, fill=(255, 255, 255, 255), font=fonts["num"], anchor="mm")

    # 2. SENTENCE NUMBER BADGE (Circled ①, ②, ③... at X=650, Y=70)
    if num > 0:
        c_x, c_y = center_x, 70
        circle_r = 30
        draw.ellipse([c_x - circle_r, c_y - circle_r, c_x + circle_r, c_y + circle_r], fill=(217, 119, 6, 255))
        num_str = str(num)
        nw = fonts["num"].getlength(num_str)
        draw.text((int(c_x - nw / 2), c_y - 25), num_str, fill=(255, 255, 255, 255), font=fonts["num"])


    # 3. MAIN TARGET SENTENCE (Centered at X=650, Y=140)
    main_end_y = 140
    if main_sent:
        main_font = fonts["main_small"] if len(main_sent.split()) > 8 else fonts["main"]
        main_end_y = draw_text_with_word_indices(
            draw,
            text=main_sent,
            words=words if active_state in ["MAIN_SENTENCE", "INTRO"] else [],
            font=main_font,
            x_pos=center_x,
            y_start=140,
            max_w=850,
            active_time=current_time,
            normal_color=(30, 41, 59, 255),
            target_word=target_word,
            align_center=True,
            max_lines=None
        )

    # 4. EXPLANATION / CONTEXT (Dynamically placed below main_sent: max(280, main_end_y + 12))
    if explanation:
        exp_y_start = max(280, main_end_y + 12)
        draw_text_with_word_indices(
            draw,
            text=explanation,
            words=words if active_state == "EXPLANATION" else [],
            font=fonts["exp"],
            x_pos=center_x,
            y_start=exp_y_start,
            max_w=840,
            active_time=current_time,
            normal_color=(71, 85, 105, 255),
            align_center=True,
            max_lines=None
        )


    # 5. SUBTLE DIVIDER LINE (Y=475)
    draw.line([220, 475, 1080, 475], fill=(217, 119, 6, 90), width=2)

    # 6. MINI DIALOGUE AREA (Question & Answer)
    left_x = 180
    right_x = 650
    dialogue_y = 495

    is_q_active = active_state in ["DEMO_Q", "PRACTICE_Q_SPEAKING", "PRACTICE_Q_PAUSE"]
    is_a_active = active_state in ["DEMO_A", "PRACTICE_A_SPEAKING", "PRACTICE_A_PAUSE"]

    # Question
    hdr_q_color = (217, 119, 6, 255) if is_q_active else (148, 163, 184, 255)
    draw.text((left_x, dialogue_y), "Question:", fill=hdr_q_color, font=fonts["dlg_hdr"])

    if q_text:
        q_font = fonts["dlg_body_small"] if len(q_text.split()) > 8 else fonts["dlg_body"]
        draw_text_with_word_indices(
            draw,
            text=q_text,
            words=words if is_q_active else [],
            font=q_font,
            x_pos=left_x,
            y_start=dialogue_y + 48,
            max_w=440,
            active_time=current_time,
            normal_color=(30, 41, 59, 255) if is_q_active else (148, 163, 184, 255),
            align_center=False,
            max_lines=None
        )

    # Answer
    hdr_a_color = (4, 120, 87, 255) if is_a_active else (148, 163, 184, 255)
    draw.text((right_x, dialogue_y), "Answer:", fill=hdr_a_color, font=fonts["dlg_hdr"])

    if a_text:
        a_font = fonts["dlg_body_small"] if len(a_text.split()) > 8 else fonts["dlg_body"]
        draw_text_with_word_indices(
            draw,
            text=a_text,
            words=words if is_a_active else [],
            font=a_font,
            x_pos=right_x,
            y_start=dialogue_y + 48,
            max_w=450,
            active_time=current_time,
            normal_color=(30, 41, 59, 255) if is_a_active else (148, 163, 184, 255),
            align_center=False,
            max_lines=None
        )



    # 7. PRACTICE REPETITION STATUS & SOUNDWAVE
    if is_pause:
        start_t = slide_data.get("start_time", current_time)
        end_t = slide_data.get("end_time", current_time + 1)
        dur = max(0.1, end_t - start_t)
        progress = max(0.0, min(1.0, (current_time - start_t) / dur))

        active_color = (217, 119, 6) if active_state == "PRACTICE_Q_PAUSE" else (4, 120, 87)

        # Status text without missing font emoji box
        status_str = "YOUR TURN! SPEAK NOW!"
        sw = fonts["status"].getlength(status_str)
        draw.text((int(center_x - sw / 2), 750), status_str, fill=(active_color[0], active_color[1], active_color[2], 255), font=fonts["status"])

        # Progress bar
        bar_x = 350
        bar_y = 805
        bar_w = 600
        draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + 12], radius=6, fill=(226, 232, 240, 255))
        if progress > 0:
            fill_w = int(bar_w * progress)
            draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + 12], radius=6, fill=(active_color[0], active_color[1], active_color[2], 255))

        # Dynamic Soundwave during pause (Shifted down to Y=900 to eliminate text overlap)
        draw_soundwave_graphic(draw, real_bar_heights, center_x=center_x, center_y=900, num_bars=35, bar_color=active_color)
    else:
        # Dynamic Soundwave during host/speaker talking (Shifted down to Y=900 to eliminate text overlap)
        talk_color = (217, 119, 6) if is_q_active else ((4, 120, 87) if is_a_active else (217, 119, 6))
        draw_soundwave_graphic(draw, real_bar_heights, center_x=center_x, center_y=900, num_bars=35, bar_color=talk_color)




    return canvas

def render_sentence_video(
    bg_image_path="image/ce3aca79-22d2-46aa-8259-85f8b5c2af7b (1).png",
    audio_path="output_sentence.wav",
    timeline=[],
    total_duration=10.0,
    output_video_path="output_sentence.mp4",
    progress_callback=None
):
    """
    Render Type 3: 20 Essential Sentences video on requested background image.
    Uses +faststart remux pass for 100% Windows Media Player & web browser compatibility.
    """
    if not bg_image_path or not os.path.exists(bg_image_path):
        bg_image_path = "image/ce3aca79-22d2-46aa-8259-85f8b5c2af7b (1).png"

    print(f"Loading background image: {bg_image_path}...")
    bg_img = Image.open(bg_image_path).convert("RGB")
    if bg_img.size != (1920, 1080):
        bg_img = bg_img.resize((1920, 1080), Image.Resampling.LANCZOS)

    fonts = get_sentence_fonts()
    fps = 24
    total_frames = int(total_duration * fps)

    print("Extracting 35-bar dynamic FFT audio visualizer...")
    real_waveforms = compute_real_audio_waveform(audio_path, num_bars=35, fps=fps, smooth_factor=0.82, gamma=1.4, max_h=100)

    raw_mp4_path = output_video_path + ".raw.mp4"

    ffmpeg_cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", "1920x1080",
        "-pix_fmt", "rgb24",
        "-r", str(fps),
        "-i", "-", # Stdin pipe
        "-i", audio_path, # Audio track
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-pix_fmt", "yuv420p",
        raw_mp4_path
    ]

    pipe = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    def get_slide_at(t):
        if not timeline:
            raise ValueError("Timeline is empty! Cannot render video without a timeline.")
        if t < timeline[0]["start_time"] or t > timeline[-1]["end_time"] + 0.5:
            raise ValueError(f"Time {t:.2f}s is out of valid timeline range [{timeline[0]['start_time']:.2f}s, {timeline[-1]['end_time']:.2f}s]!")
        active_slide = timeline[0]
        for slide in timeline:
            if slide["start_time"] <= t:
                active_slide = slide
            else:
                break
        return active_slide

    for f in range(total_frames):
        current_time = f / fps

        active_slide = get_slide_at(current_time)
        real_bars = real_waveforms.get(f, None)

        frame_img = render_sentence_frame(
            bg_img,
            active_slide,
            current_time,
            total_duration,
            fonts,
            real_bar_heights=real_bars
        )

        pipe.stdin.write(frame_img.tobytes())

        if progress_callback and f % 96 == 0:
            prog = 0.05 + (f / max(1, total_frames)) * 0.9
            progress_callback(f"Rendering Sentence Video Frames ({f}/{total_frames})...", round(prog, 2))

    pipe.stdin.close()
    pipe.wait()

    # Fast second-pass remux to add +faststart header for 100% Windows Media Player & web browser compatibility
    if os.path.exists(raw_mp4_path):
        remux_cmd = [
            imageio_ffmpeg.get_ffmpeg_exe(), "-y",
            "-i", raw_mp4_path,
            "-c", "copy",
            "-movflags", "+faststart",
            output_video_path
        ]
        subprocess.run(remux_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            if os.path.exists(raw_mp4_path):
                os.remove(raw_mp4_path)
        except Exception:
            pass

    if progress_callback:
        progress_callback("Sentence Video Render Complete!", 1.0)

    print(f"Sentence Video exported successfully: {output_video_path}")
    return output_video_path
