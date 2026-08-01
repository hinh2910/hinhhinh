import os
import sys
import time
import subprocess
import numpy as np
import av
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

def load_top_media_frames(media_path, target_size=(1080, 520)):
    """
    Load frames from an image file or video clip file, resized/cropped to target_size (fill mode).
    Top area occupies ~1/4 of total height (1080x520).
    """
    frames = []
    if not media_path or not os.path.exists(media_path):
        return frames

    tw, th = target_size
    target_ratio = tw / th

    def fill_crop(img):
        w, h = img.size
        img_ratio = w / h
        if img_ratio > target_ratio:
            new_w = int(h * target_ratio)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))
        else:
            new_h = int(w / target_ratio)
            top = (h - new_h) // 2
            img = img.crop((0, top, w, top + new_h))
        return img.resize(target_size, Image.Resampling.LANCZOS)

    # Check if image file
    ext = os.path.splitext(media_path)[1].lower()
    if ext in ['.jpg', '.jpeg', '.png', '.webp', '.bmp']:
        try:
            img = Image.open(media_path).convert("RGB")
            frames.append(fill_crop(img))
            return frames
        except Exception as e:
            print(f"Warning loading top image {media_path}: {e}")

    # Video clip file loading
    try:
        container = av.open(media_path)
        for frame in container.decode(video=0):
            img = frame.to_image().convert("RGB")
            frames.append(fill_crop(img))
        container.close()
    except Exception as e:
        print(f"Warning loading video clip {media_path}: {e}")

    return frames


def get_paper_background(target_size=(1080, 1400)):
    """
    Search for shortbackground.jpg in image/, short/, assets/, or root directory.
    If not found, create a clean parchment/paper textured background.
    """
    search_paths = [
        "short/shortbackground.jpg",
        "image/shortbackground.jpg",
        "image/background.jpg",
        "assets/shortbackground.jpg",
        "shortbackground.jpg"
    ]
    for p in search_paths:
        if os.path.exists(p):
            try:
                img = Image.open(p).convert("RGB")
                return img.resize(target_size, Image.Resampling.LANCZOS)
            except Exception as e:
                print(f"Warning loading background image {p}: {e}")

    # Fallback solid textured paper image
    bg = Image.new("RGB", target_size, (244, 241, 234))
    draw = ImageDraw.Draw(bg)
    draw.rectangle([20, 20, target_size[0]-20, target_size[1]-20], outline=(220, 215, 200), width=2)
    return bg

def render_short_frame(top_frame, paper_bg, title, text, words, current_time, font_title, font_body, target_word="", meaning=""):
    """
    Combine top video frame (1080x520, ~1/4 height) and paper background (1080x1400, ~3/4 height) into 1080x1920 Short video frame.
    Draws title, story text with active line light highlight box, CTA bait, and Golden Tip text.
    """
    # Create full canvas (1080 x 1920)
    canvas = Image.new("RGB", (1080, 1920), (255, 255, 255))
    
    # Paste top video clip frame (0..520 Y)
    canvas.paste(top_frame, (0, 0))
    
    # Paste bottom paper background texture (520..1920 Y)
    canvas.paste(paper_bg, (0, 520))
    
    draw = ImageDraw.Draw(canvas, "RGBA")

    # 1. Render Title
    title_text = title.strip()
    if title_text:
        max_title_w = 940
        title_lines = []
        words_title = title_text.split()
        curr_l = ""
        for w in words_title:
            test_l = (curr_l + " " + w).strip()
            if font_title.getlength(test_l) <= max_title_w:
                curr_l = test_l
            else:
                title_lines.append(curr_l)
                curr_l = w
        if curr_l:
            title_lines.append(curr_l)

        y_title = 575
        for line in title_lines:
            w_len = font_title.getlength(line)
            x_title = (1080 - w_len) / 2
            draw.text((x_title, y_title), line, fill=(20, 20, 20, 255), font=font_title)
            y_title += 62

    # 2. Find active word & line indices (Line highlight stays ON continuously even during pauses)
    active_line_word_idx = 0  # Default to 0 (Line 1 active from beginning)
    current_word_idx = -1     # Exact word currently spoken
    if words:
        for idx, w_info in enumerate(words):
            if current_time >= w_info['start']:
                active_line_word_idx = idx
            if w_info['start'] <= current_time <= w_info['end']:
                current_word_idx = idx

    # 3. Format and Wrap Story Text on Paper Background
    words_list = text.split()
    x_start = 70
    y_start = 710
    max_w = 940
    line_h = 88

    lines = []
    curr_line = []
    curr_w = 0

    for i, w in enumerate(words_list):
        w_len = font_body.getlength(w + " ")
        if curr_w + w_len > max_w and curr_line:
            lines.append(curr_line)
            curr_line = [(w, i)]
            curr_w = w_len
        else:
            curr_line.append((w, i))
            curr_w += w_len
    if curr_line:
        lines.append(curr_line)

    # 4. Render Text with Entire Active Line Light Highlight Box & Bold Active Text
    line_bg_color = (187, 222, 251, 210)     # Soft light blue box behind entire active line
    word_active_box = (144, 202, 249, 255)   # Slightly deeper highlight for exact active word
    
    active_text_color = (0, 0, 0, 255)        # Pure bold black text on active line
    normal_text_color = (110, 110, 110, 255)  # Softer grey text for inactive lines

    y = y_start
    for line in lines:
        is_active_line = any(idx == active_line_word_idx for word, idx in line)
        
        # Calculate full line width
        line_w = sum(font_body.getlength(w + " ") for w, _ in line)
        
        if is_active_line:
            box_left = x_start - 12
            box_top = y - 4
            box_right = x_start + line_w + 4
            box_bottom = y + line_h - 18
            draw.rounded_rectangle([box_left, box_top, box_right, box_bottom], radius=12, fill=line_bg_color)

        x = x_start
        for word, idx in line:
            w_width = font_body.getlength(word)
            
            if is_active_line:
                if idx == current_word_idx:
                    w_left = x - 5
                    w_top = y - 4
                    w_right = x + w_width + 5
                    w_bottom = y + line_h - 18
                    draw.rounded_rectangle([w_left, w_top, w_right, w_bottom], radius=8, fill=word_active_box)

                draw.text((x + 1, y), word, fill=active_text_color, font=font_body)
                draw.text((x, y + 1), word, fill=active_text_color, font=font_body)
                draw.text((x, y), word, fill=active_text_color, font=font_body)
            else:
                draw.text((x, y), word, fill=normal_text_color, font=font_body)
                
            x += font_body.getlength(word + " ")
        y += line_h

    # 5. Render Call-to-Action (Bait for Like & Subscribe - Red-Orange text, NO broken icon)
    y_cta = min(y + 35, 1420)
    cta_text = "LIKE & SUBSCRIBE for Daily Practice!"
    cta_w = font_body.getlength(cta_text)
    x_cta = (1080 - cta_w) / 2
    
    draw.text((x_cta + 2, y_cta + 2), cta_text, fill=(230, 230, 230, 140), font=font_body)
    draw.text((x_cta, y_cta), cta_text, fill=(230, 60, 30, 255), font=font_body)

    # 6. Render Per-Sentence/Story Tip BELOW the Call-to-Action (Bait Like & Sub)
    curr_target = target_word.strip() if target_word else ""
    curr_meaning = meaning.strip() if meaning else ""

    if curr_target:
        y_tip = y_cta + 125
        w_title = f'Tip: the word "{curr_target}" means'
        max_tip_w = 920

        # Dynamic word wrap for tip header line to prevent screen overflow/cutting off text
        words_t = w_title.split()
        t_lines = []
        c_t = ""
        for w in words_t:
            test_t = (c_t + " " + w).strip()
            if font_body.getlength(test_t) <= max_tip_w:
                c_t = test_t
            else:
                if c_t:
                    t_lines.append(c_t)
                c_t = w
        if c_t:
            t_lines.append(c_t)

        for line in t_lines:
            w_len1 = font_body.getlength(line)
            x_tip1 = (1080 - w_len1) / 2
            # Soft Golden Yellow/Amber (215, 130, 20)
            draw.text((x_tip1 + 2, y_tip + 2), line, fill=(240, 240, 240, 140), font=font_body)
            draw.text((x_tip1, y_tip), line, fill=(215, 130, 20, 255), font=font_body)
            y_tip += 50

        if curr_meaning:
            w_mean = f"{curr_meaning}"
            max_m_w = 920
            words_m = w_mean.split()
            m_lines = []
            c_line = ""
            for w in words_m:
                test_l = (c_line + " " + w).strip()
                if font_body.getlength(test_l) <= max_m_w:
                    c_line = test_l
                else:
                    if c_line:
                        m_lines.append(c_line)
                    c_line = w
            if c_line:
                m_lines.append(c_line)

            y_m = y_tip + 6
            for m_line in m_lines[:2]:
                w_len2 = font_body.getlength(m_line)
                x_tip2 = (1080 - w_len2) / 2
                draw.text((x_tip2 + 2, y_m + 2), m_line, fill=(240, 240, 240, 140), font=font_body)
                draw.text((x_tip2, y_m), m_line, fill=(50, 50, 50, 255), font=font_body)
                y_m += 48

    return canvas.convert("RGB")

def render_short_video(media_paths=None, audio_path=None, title="", text="", words=[], total_duration=0, output_video_path="", progress_callback=None, video_clips_paths=None, target_word="", meaning=""):
    """
    Render 1080x1920 Vertical Short Video.
    - Top 1/4 (1080x520): Displays imported image or video clip.
    - Bottom 3/4 (1080x1400): Paper background + Title + Active word highlighted story text.
    - Video length strictly matches audio duration.
    """
    if media_paths is None:
        media_paths = video_clips_paths if video_clips_paths is not None else []

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    if progress_callback:
        progress_callback("Loading Top Image/Media for Shorts...", 0.3)

    target_top_size = (1080, 520)
    all_clip_frames = []

    # Handle string (single image/video path) or list of paths
    if isinstance(media_paths, str):
        media_paths = [media_paths]

    # Load frames from provided media paths (image or video)
    for m_path in media_paths:
        if m_path and os.path.exists(m_path):
            m_frames = load_top_media_frames(m_path, target_size=target_top_size)
            if m_frames:
                all_clip_frames.extend(m_frames)

    # Fallback to default background image or video/bgtalk.mp4 if no media uploaded
    if not all_clip_frames:
        default_v = "video/bgtalk.mp4"
        if os.path.exists(default_v):
            all_clip_frames = load_top_media_frames(default_v, target_size=target_top_size)
        else:
            fallback_img = Image.new("RGB", target_top_size, (50, 60, 80))
            all_clip_frames = [fallback_img]

    n_top_frames = len(all_clip_frames)

    # Load paper background texture (1080x1400)
    paper_bg = get_paper_background(target_size=(1080, 1400))

    # Font setup
    font_path_bold = "C:/Windows/Fonts/segoeuib.ttf"
    try:
        font_title = ImageFont.truetype(font_path_bold, 68)
        font_body = ImageFont.truetype(font_path_bold, 56)
    except:
        try:
            font_title = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 68)
            font_body = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 56)
        except:
            font_title = ImageFont.load_default()
            font_body = ImageFont.load_default()

    fps = 24
    total_frames = int(total_duration * fps)

    w, h = 1080, 1920
    encoder = "libx264"
    preset_args = ["-preset", "ultrafast", "-crf", "22"]

    cmd = [
        ffmpeg_exe, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{w}x{h}",
        "-pix_fmt", "rgb24",
        "-r", str(fps),
        "-i", "-",           # Stdin raw frames
        "-i", audio_path,    # Audio track
        "-c:v", encoder,
        *preset_args,
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",         # Trim video to audio length!
        "-pix_fmt", "yuv420p",
        output_video_path
    ]

    pipe = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    for f_idx in range(total_frames):
        current_time = f_idx / fps

        top_frame = all_clip_frames[f_idx % n_top_frames]

        rendered_canvas = render_short_frame(
            top_frame=top_frame,
            paper_bg=paper_bg,
            title=title,
            text=text,
            words=words,
            current_time=current_time,
            font_title=font_title,
            font_body=font_body,
            target_word=target_word,
            meaning=meaning
        )

        raw_bytes = rendered_canvas.tobytes()
        pipe.stdin.write(raw_bytes)

        if f_idx % 24 == 0:
            pct = 0.4 + (f_idx / max(1, total_frames)) * 0.55
            if progress_callback:
                progress_callback(f"Rendering 9:16 Short Frames ({f_idx}/{total_frames})...", round(pct, 2))

    pipe.stdin.close()
    pipe.wait()
    print("9:16 Vertical Short Video rendering completed successfully!")
