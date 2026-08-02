import os
import sys
import json
import uuid
import re
import time
import asyncio
import threading
import av
from flask import Flask, render_template, request, jsonify, send_from_directory

# Local module imports
from audio_engine import build_lesson_audio_and_timeline, build_short_audio_and_timeline, build_sentence_audio_and_timeline, generate_tts_sync, generate_srt_file
from video_engine import render_lesson_video, concat_intro_and_lesson
from short_video_engine import render_short_video
from short_quiz_video_engine import render_short_quiz_video
from sentence_video_engine import render_sentence_video
from prompts import CHATGPT_SCRIPT_PROMPT, CHATGPT_SHORT_PROMPT, CHATGPT_SENTENCE_PROMPT, CHATGPT_SHORT_QUIZ_PROMPT, generate_youtube_metadata, generate_short_youtube_metadata, generate_sentence_youtube_metadata


app = Flask(__name__)

# Dictionary storing background render jobs status
render_jobs = {}

def get_video_duration(video_path):
    """Get video duration in seconds using PyAV."""
    try:
        container = av.open(video_path)
        dur = float(container.duration) / 1000000.0
        container.close()
        return dur
    except:
        return 0.0

def robust_repair_chatgpt_json(raw_text_input):
    """
    3-Layer Bulletproof JSON Repair Engine:
    Layer 1: Standard JSON Load (with markdown fence cleanup)
    Layer 2: Regex Syntax Repair (fix missing commas, control characters, auto-closing braces)
    Layer 3: Regex Extraction Fallback (extract "text": "..." for intro/outro and "items": [...] for shadowing)
    """
    raw_str = raw_text_input.strip()

    if "```" in raw_str:
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_str, flags=re.IGNORECASE)
        if fence_match:
            raw_str = fence_match.group(1).strip()

    try:
        data = json.loads(raw_str)
        if isinstance(data, dict) and "sections" in data:
            return data
    except Exception:
        pass

    cleaned = raw_str
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', cleaned)
    cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
    cleaned = re.sub(r'}\s*\n?\s*{', '},\n{', cleaned)
    cleaned = re.sub(r'(:\s*(?:"[^"]*"|\d+|\d+\.\d+|true|false|null))\s*\n\s*"', r'\1,\n"', cleaned)

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    open_braces = cleaned.count('{') - cleaned.count('}')
    open_brackets = cleaned.count('[') - cleaned.count(']')
    auto_closed = cleaned + (']' * max(0, open_brackets)) + ('}' * max(0, open_braces))

    try:
        return json.loads(auto_closed)
    except Exception:
        pass

    print("Running Layer 3 Regex Extractor Fallback...")
    sections = []
    
    intro_text_match = re.search(r'"type"\s*:\s*"intro_story".*?"text"\s*:\s*"([^"]*)"', raw_str, flags=re.DOTALL)
    if intro_text_match:
        sections.append({
            "type": "intro_story",
            "title": "Part 1: Welcome & Topic Hook",
            "text": intro_text_match.group(1).strip()
        })

    shadow_block = re.search(r'"type"\s*:\s*"shadowing_practice".*?"items"\s*:\s*\[(.*?)\]', raw_str, flags=re.DOTALL)
    if shadow_block:
        items_text = shadow_block.group(1)
        matches = re.findall(r'\{\s*"sentence"\s*:\s*"(.*?)"(?:\s*,\s*"pause_sec"\s*:\s*([\d\.]+))?(?:\s*,\s*"repeats"\s*:\s*(\d+))?\s*\}', items_text, flags=re.DOTALL)
        shadow_items = []
        for sent, p_sec, reps in matches:
            s_clean = sent.replace('\n', ' ').strip()
            if s_clean:
                shadow_items.append({"sentence": s_clean, "pause_sec": 4.2, "repeats": 3})
        if shadow_items:
            sections.append({
                "type": "shadowing_practice",
                "title": "Part 2: 3x Shadowing Practice",
                "items": shadow_items
            })

    review_text_match = re.search(r'"type"\s*:\s*"review".*?"text"\s*:\s*"([^"]*)"', raw_str, flags=re.DOTALL)
    if review_text_match:
        sections.append({
            "type": "review",
            "title": "Part 3: Outro",
            "text": review_text_match.group(1).strip()
        })

    if not sections:
        all_sents = re.findall(r'"(?:sentence|text)"\s*:\s*"([^"]*)"', raw_str)
        if not all_sents:
            raise ValueError("Không thể trích xuất được văn bản hợp lệ từ kịch bản!")

        sections = [
            {"type": "intro_story", "title": "Part 1: Intro", "text": " ".join(all_sents[:3])},
            {"type": "shadowing_practice", "title": "Part 2: Practice", "items": [{"sentence": s, "pause_sec": 4.2, "repeats": 3} for s in all_sents[3:-1]]},
            {"type": "review", "title": "Part 3: Outro", "text": all_sents[-1] if len(all_sents) > 3 else "Great job today!"}
        ]

    return {
        "title": "Day 1 of 10-Day English Speaking Challenge",
        "theme": "English Practice",
        "day_number": 1,
        "sections": sections
    }

def process_video_job(job_id, script_data, intro_voice="en-US-JennyNeural", shadowing_voice="en-GB-SoniaNeural", praise_voice="en-US-AvaNeural", rate="-10%"):
    """Background worker for generating audio, running whisper alignment, creating SRT, and rendering video."""
    try:
        def update_progress(msg, progress):
            render_jobs[job_id]["status"] = "PROCESSING"
            render_jobs[job_id]["status_msg"] = msg
            render_jobs[job_id]["progress"] = int(progress * 100)

        update_progress("Synthesizing Audio & Aligning Word Timestamps...", 0.05)

        sections = script_data.get("sections", [])
        if not sections:
            raise ValueError("Kịch bản không chứa thông tin sections hợp lệ!")

        os.makedirs("output", exist_ok=True)
        lesson_wav_path = os.path.join("output", f"lesson_{job_id}.wav")
        lesson_mp4_path = os.path.join("output", f"lesson_{job_id}.mp4")
        final_mp4_path = os.path.join("output", f"final_shadowing_{job_id}.mp4")
        final_srt_path = os.path.join("output", f"final_shadowing_{job_id}.srt")

        # 1. Build Audio and Word Timeline
        audio_path, timeline, total_dur = build_lesson_audio_and_timeline(
            sections,
            intro_voice=intro_voice,
            shadowing_voice=shadowing_voice,
            praise_voice=praise_voice,
            rate=rate,
            output_audio_path=lesson_wav_path,
            progress_callback=update_progress
        )

        # 2. Render Lesson Video Frames with Goal Bar & Subtitles
        bgtalk_path = "video/talk.mp4" if os.path.exists("video/talk.mp4") else "video/bgtalk.mp4"
        bgnotalk_path = "video/notalk.mp4" if os.path.exists("video/notalk.mp4") else "video/bgnotalk.mp4"
        intro_mp4_path = "video/intro.mp4"
        outro_mp4_path = "video/outtro.mp4" if os.path.exists("video/outtro.mp4") else ("video/outro.mp4" if os.path.exists("video/outro.mp4") else None)

        if not os.path.exists(bgtalk_path) or not os.path.exists(bgnotalk_path):
            raise FileNotFoundError("Không tìm thấy video nền 'talk.mp4' hoặc 'notalk.mp4' trong thư mục video/!")

        key_vocab_list = script_data.get("key_vocabulary", [])
        render_lesson_video(
            bgtalk_path=bgtalk_path,
            bgnotalk_path=bgnotalk_path,
            audio_path=audio_path,
            timeline=timeline,
            total_duration=total_dur,
            output_video_path=lesson_mp4_path,
            progress_callback=update_progress,
            key_vocab_list=key_vocab_list
        )

        # 3. Stitch Intro Channel Video + Lesson Video + Outro Video
        intro_offset = 0.0
        if os.path.exists(intro_mp4_path):
            intro_offset = get_video_duration(intro_mp4_path)

        concat_intro_and_lesson(
            intro_path=intro_mp4_path if os.path.exists(intro_mp4_path) else None,
            lesson_video_path=lesson_mp4_path,
            final_output_path=final_mp4_path,
            progress_callback=update_progress,
            outro_path=outro_mp4_path
        )
        video_filename = os.path.basename(final_mp4_path)

        # 4. Generate Timed SRT Subtitle File for YouTube Upload
        srt_filename = video_filename.replace(".mp4", ".srt")
        srt_full_path = os.path.join("output", srt_filename)
        generate_srt_file(timeline, srt_full_path, intro_offset_sec=intro_offset)

        # 5. Generate YouTube Title & Description with 100% Exact Chapters
        theme = script_data.get("theme", "English Practice")
        day_num = script_data.get("day_number", 1)
        yt_meta = generate_youtube_metadata(theme, day_number=day_num)

        # Read 100% Exact Timestamps from output/youtube_chapters.txt (GUARANTEED ACCURATE YOUTUBE FORMAT)
        exact_chapters_str = ""
        chapters_file_path = os.path.join("output", "youtube_chapters.txt")
        if os.path.exists(chapters_file_path):
            try:
                with open(chapters_file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    lines = [l.strip() for l in content.splitlines() if l.strip() and not l.startswith("=")]
                    if lines:
                        exact_chapters_str = "✨ LESSON TIMESTAMPS & CHAPTERS:\n" + "\n".join(lines)
            except Exception as e:
                print(f"Error reading chapters file: {e}")

        if not exact_chapters_str:
            exact_chapters_str = "✨ LESSON TIMESTAMPS & CHAPTERS:\n(Timestamps will automatically generate when video renders)"

        clean_desc = yt_meta["description"]
        clean_desc = clean_desc.replace("{{EXACT_YOUTUBE_CHAPTERS}}", exact_chapters_str)
        clean_desc = clean_desc.replace("{EXACT_YOUTUBE_CHAPTERS}", exact_chapters_str)
        yt_meta["description"] = clean_desc

        render_jobs[job_id]["status"] = "COMPLETED"
        render_jobs[job_id]["status_msg"] = "Xuất Video & Phụ Đề SRT Hoàn Tất!"
        render_jobs[job_id]["progress"] = 100
        render_jobs[job_id]["video_filename"] = video_filename
        render_jobs[job_id]["srt_filename"] = srt_filename
        render_jobs[job_id]["video_url"] = f"/outputs/{video_filename}"
        render_jobs[job_id]["srt_url"] = f"/api/download/{srt_filename}"
        render_jobs[job_id]["youtube_metadata"] = {
            "title": yt_meta["title"],
            "description": yt_meta["description"],
            "pinned_comment": yt_meta.get("pinned_comment", "")
        }

        print(f"Job {job_id} COMPLETED SUCCESSFULLY: {video_filename} | Subtitle: {srt_filename}")

    except Exception as e:
        print(f"Error in process_video_job ({job_id}): {e}")
        render_jobs[job_id]["status"] = "FAILED"
        render_jobs[job_id]["status_msg"] = str(e)
        render_jobs[job_id]["progress"] = 0

def parse_short_script(raw_text_input):
    raw_str = raw_text_input.strip()
    if "```" in raw_str:
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_str, flags=re.IGNORECASE)
        if fence_match:
            raw_str = fence_match.group(1).strip()
    try:
        data = json.loads(raw_str)
        if isinstance(data, dict) and "text" in data:
            return {
                "title": data.get("title", "English Short Story"),
                "text": data.get("text", ""),
                "target_word": data.get("target_word", ""),
                "meaning": data.get("meaning", "")
            }
    except Exception:
        pass
    
    lines = [l.strip() for l in raw_str.split("\n") if l.strip()]
    if lines:
        if len(lines) == 1:
            return {"title": "English Short Story", "text": lines[0], "target_word": "", "meaning": ""}
        else:
            return {"title": lines[0], "text": " ".join(lines[1:]), "target_word": "", "meaning": ""}
    return {"title": "English Short Story", "text": raw_str, "target_word": "", "meaning": ""}

def process_short_video_job(job_id, title, text, voice="en-GB-LibbyNeural", rate="-10%", clip_paths=[], target_word="", meaning=""):
    try:
        def update_progress(msg, progress):
            render_jobs[job_id]["status"] = "PROCESSING"
            render_jobs[job_id]["status_msg"] = msg
            render_jobs[job_id]["progress"] = int(progress * 100)

        update_progress("Synthesizing Short Audio & Extracting Timestamps...", 0.05)

        os.makedirs("output", exist_ok=True)
        short_wav_path = os.path.join("output", f"short_audio_{job_id}.wav")
        short_mp4_path = os.path.join("output", f"short_{job_id}.mp4")
        short_srt_path = os.path.join("output", f"short_{job_id}.srt")

        audio_path, clean_text, words, total_dur = build_short_audio_and_timeline(
            text=text,
            voice=voice,
            rate=rate,
            output_audio_path=short_wav_path,
            progress_callback=update_progress
        )

        render_short_video(
            media_paths=clip_paths,
            audio_path=audio_path,
            title=title,
            text=clean_text,
            words=words,
            total_duration=total_dur,
            output_video_path=short_mp4_path,
            progress_callback=update_progress,
            target_word=target_word,
            meaning=meaning
        )

        talking_slide = [{
            "start_time": 0.0,
            "end_time": total_dur,
            "text": clean_text,
            "is_talking": True
        }]
        srt_filename = os.path.basename(short_srt_path)
        generate_srt_file(talking_slide, short_srt_path, intro_offset_sec=0.0)

        video_filename = os.path.basename(short_mp4_path)
        yt_meta = generate_short_youtube_metadata(title, title_suggestion=title)

        render_jobs[job_id]["status"] = "COMPLETED"
        render_jobs[job_id]["status_msg"] = "Xuất Video Short (9:16) & Subtitle SRT Hoàn Tất!"
        render_jobs[job_id]["progress"] = 100
        render_jobs[job_id]["video_filename"] = video_filename
        render_jobs[job_id]["srt_filename"] = srt_filename
        render_jobs[job_id]["video_url"] = f"/outputs/{video_filename}"
        render_jobs[job_id]["srt_url"] = f"/api/download/{srt_filename}"
        render_jobs[job_id]["youtube_metadata"] = {
            "title": yt_meta["title"],
            "description": yt_meta["description"],
            "pinned_comment": yt_meta.get("pinned_comment", "")
        }

        print(f"Short Job {job_id} COMPLETED SUCCESSFULLY: {video_filename}")

    except Exception as e:
        print(f"Error in process_short_video_job ({job_id}): {e}")
        render_jobs[job_id]["status"] = "FAILED"
        render_jobs[job_id]["status_msg"] = str(e)
        render_jobs[job_id]["progress"] = 0

def parse_short_quiz_script(raw_text_input):
    raw_str = raw_text_input.strip()
    if "```" in raw_str:
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_str, flags=re.IGNORECASE)
        if fence_match:
            raw_str = fence_match.group(1).strip()
    try:
        data = json.loads(raw_str)
        if isinstance(data, dict) and "questions" in data:
            return data
    except Exception:
        pass

    try:
        cleaned = raw_str
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', cleaned)
        cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
        return json.loads(cleaned)
    except Exception:
        pass

    raise ValueError("Không thể trích xuất kịch bản Short Quiz 'questions' hợp lệ từ JSON!")

def process_short_quiz_video_job(job_id, script_data, voice="en-US-JennyNeural", rate="-5%"):
    try:
        def update_progress(msg, progress):
            render_jobs[job_id]["status"] = "PROCESSING"
            render_jobs[job_id]["status_msg"] = msg
            render_jobs[job_id]["progress"] = int(progress * 100)

        update_progress("Đang tổng hợp âm thanh & timeline Quiz Short...", 0.05)

        safe_title = re.sub(r'[^\w\-]', '_', script_data.get("title", "short_quiz"))[:30]
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        video_filename = f"ShortQuiz_{safe_title}_{timestamp_str}.mp4"

        output_mp4_path = os.path.join("output", video_filename)

        render_short_quiz_video(
            script_data,
            voice=voice,
            rate=rate,
            output_video_path=output_mp4_path,
            progress_callback=update_progress
        )

        yt_meta = generate_short_youtube_metadata(script_data.get("title", "English Quiz Challenge"), title_suggestion=script_data.get("title"))

        render_jobs[job_id]["status"] = "COMPLETED"
        render_jobs[job_id]["status_msg"] = "Xuất Video Short Question (9:16) Hoàn Tất!"
        render_jobs[job_id]["progress"] = 100
        render_jobs[job_id]["video_filename"] = video_filename
        render_jobs[job_id]["srt_filename"] = None
        render_jobs[job_id]["video_url"] = f"/outputs/{video_filename}"
        render_jobs[job_id]["srt_url"] = None
        render_jobs[job_id]["youtube_metadata"] = {
            "title": yt_meta["title"],
            "description": yt_meta["description"],
            "pinned_comment": yt_meta.get("pinned_comment", "")
        }

        print(f"Short Quiz Job {job_id} COMPLETED SUCCESSFULLY: {video_filename}")

    except Exception as e:
        print(f"Error in process_short_quiz_video_job ({job_id}): {e}")
        render_jobs[job_id]["status"] = "FAILED"
        render_jobs[job_id]["status_msg"] = str(e)
        render_jobs[job_id]["progress"] = 0

def parse_sentence_script(raw_text_input):
    raw_str = raw_text_input.strip()
    if "```" in raw_str:
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_str, flags=re.IGNORECASE)
        if fence_match:
            raw_str = fence_match.group(1).strip()
    try:
        data = json.loads(raw_str)
        if isinstance(data, dict) and "sentences" in data:
            return data
    except Exception:
        pass

    try:
        cleaned = raw_str
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', cleaned)
        cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
        return json.loads(cleaned)
    except Exception:
        pass

    raise ValueError("Không thể trích xuất kịch bản 'sentences' hợp lệ từ JSON!")

def process_sentence_video_job(job_id, script_data, host_voice="en-US-JennyNeural", speaker_a_voice="en-US-AvaNeural", speaker_b_voice="en-GB-SoniaNeural", rate="-8%"):
    try:
        def update_progress(msg, progress):
            render_jobs[job_id]["status"] = "PROCESSING"
            render_jobs[job_id]["status_msg"] = msg
            render_jobs[job_id]["progress"] = int(progress * 100)

        update_progress("Synthesizing Sentence Audio & Building Timeline...", 0.05)

        os.makedirs("output", exist_ok=True)
        sent_wav_path = os.path.join("output", f"sentence_audio_{job_id}.wav")
        sent_mp4_raw_path = os.path.join("output", f"sentence_raw_{job_id}.mp4")
        final_sent_mp4_path = os.path.join("output", f"sentence_{job_id}.mp4")
        final_sent_srt_path = os.path.join("output", f"sentence_{job_id}.srt")

        audio_path, timeline, total_dur = build_sentence_audio_and_timeline(
            script_data,
            host_voice=host_voice,
            speaker_a_voice=speaker_a_voice,
            speaker_b_voice=speaker_b_voice,
            rate=rate,
            output_audio_path=sent_wav_path,
            progress_callback=update_progress
        )

        bg_path = "image/ce3aca79-22d2-46aa-8259-85f8b5c2af7b (1).png"
        render_sentence_video(
            bg_image_path=bg_path,
            audio_path=audio_path,
            timeline=timeline,
            total_duration=total_dur,
            output_video_path=sent_mp4_raw_path,
            progress_callback=update_progress
        )

        # Stitch video/intro.mp4 + lesson video + video/outtro.mp4 (Matching Shadowing pipeline 100%)
        intro_mp4_path = os.path.join("video", "intro.mp4")
        outro_mp4_path = os.path.join("video", "outtro.mp4")

        intro_offset = 0.0
        if os.path.exists(intro_mp4_path):
            intro_offset = get_video_duration(intro_mp4_path)

        if os.path.exists(intro_mp4_path) or os.path.exists(outro_mp4_path):
            concat_intro_and_lesson(
                intro_path=intro_mp4_path if os.path.exists(intro_mp4_path) else None,
                lesson_video_path=sent_mp4_raw_path,
                final_output_path=final_sent_mp4_path,
                progress_callback=update_progress,
                outro_path=outro_mp4_path if os.path.exists(outro_mp4_path) else None
            )
        else:
            import shutil
            shutil.copy(sent_mp4_raw_path, final_sent_mp4_path)

        # Generate Timed SRT file with intro_offset
        srt_filename = os.path.basename(final_sent_srt_path)
        generate_srt_file(timeline, final_sent_srt_path, intro_offset_sec=intro_offset)

        video_filename = os.path.basename(final_sent_mp4_path)
        theme = script_data.get("theme", "Daily Life")
        yt_meta = generate_sentence_youtube_metadata(theme, title_suggestion=script_data.get("title"))


        # Read 100% Exact Timestamps from output/youtube_chapters.txt with intro_offset offset
        exact_chapters_str = ""
        chapters_file_path = os.path.join("output", "youtube_chapters.txt")
        if os.path.exists(chapters_file_path):
            try:
                with open(chapters_file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    lines = [l.strip() for l in content.splitlines() if l.strip() and not l.startswith("=")]
                    if lines:
                        adjusted_lines = []
                        for line in lines:
                            parts = line.split(" - ", 1)
                            if len(parts) == 2:
                                t_str, title_c = parts[0], parts[1]
                                t_parts = t_str.split(":")
                                if len(t_parts) == 2:
                                    t_sec = int(t_parts[0]) * 60 + int(t_parts[1]) + int(intro_offset)
                                    adj_t = f"{t_sec//60:02d}:{t_sec%60:02d}"
                                    adjusted_lines.append(f"{adj_t} - {title_c}")
                                else:
                                    adjusted_lines.append(line)
                            else:
                                adjusted_lines.append(line)
                        exact_chapters_str = "✨ LESSON TIMESTAMPS & CHAPTERS:\n" + "\n".join(adjusted_lines)
            except Exception as e:
                print(f"Error reading chapters file: {e}")

        clean_desc = yt_meta["description"]
        if exact_chapters_str:
            clean_desc = clean_desc + "\n\n" + exact_chapters_str

        render_jobs[job_id]["status"] = "COMPLETED"
        render_jobs[job_id]["status_msg"] = "Xuất Video 20 Essential Sentences & Subtitle SRT Hoàn Tất!"
        render_jobs[job_id]["progress"] = 100
        render_jobs[job_id]["video_filename"] = video_filename
        render_jobs[job_id]["srt_filename"] = srt_filename
        render_jobs[job_id]["video_url"] = f"/outputs/{video_filename}"
        render_jobs[job_id]["srt_url"] = f"/api/download/{srt_filename}"
        render_jobs[job_id]["youtube_metadata"] = {
            "title": yt_meta["title"],
            "description": clean_desc,
            "pinned_comment": yt_meta.get("pinned_comment", "")
        }

        print(f"Sentence Job {job_id} COMPLETED SUCCESSFULLY: {video_filename}")

    except Exception as e:
        print(f"Error in process_sentence_video_job ({job_id}): {e}")
        render_jobs[job_id]["status"] = "FAILED"
        render_jobs[job_id]["status_msg"] = str(e)
        render_jobs[job_id]["progress"] = 0


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/get_prompt", methods=["POST"])
@app.route("/api/generate_prompt", methods=["POST"])
def get_prompt():
    data = request.json or {}
    topic = data.get("topic", "Confidence & Daily Speaking")
    video_type = data.get("video_type", "long")
    
    if video_type == "short":
        formatted_prompt = CHATGPT_SHORT_PROMPT.format(topic=topic)
    elif video_type == "short_quiz":
        formatted_prompt = CHATGPT_SHORT_QUIZ_PROMPT.format(topic=topic)
    elif video_type == "sentence":
        formatted_prompt = CHATGPT_SENTENCE_PROMPT.format(topic=topic)
    elif video_type == "podcast":
        formatted_prompt = CHATGPT_PODCAST_PROMPT.format(topic=topic)
    elif video_type == "ielts":
        formatted_prompt = CHATGPT_IELTS_PROMPT.format(topic=topic)
    else:
        formatted_prompt = CHATGPT_SCRIPT_PROMPT.format(topic=topic)
    return jsonify({"prompt": formatted_prompt})


@app.route("/api/render", methods=["POST"])
def api_render():
    data = request.json or {}
    script_input = data.get("script", "")
    intro_voice = data.get("intro_voice", "en-US-JennyNeural")
    shadowing_voice = data.get("shadowing_voice", "en-GB-SoniaNeural")
    rate = data.get("rate", "-5%")

    if not script_input.strip():
        return jsonify({"error": "Vui lòng nhập kịch bản JSON!"}), 400

    try:
        parsed_script = robust_repair_chatgpt_json(script_input)
    except Exception as e:
        return jsonify({"error": f"Lỗi định dạng JSON kịch bản: {str(e)}"}), 400

    job_id = str(uuid.uuid4())[:8]
    render_jobs[job_id] = {
        "status": "PROCESSING",
        "status_msg": "Đang khởi tạo...",
        "progress": 0,
        "video_filename": None,
        "srt_filename": None,
        "video_url": None,
        "srt_url": None,
        "youtube_metadata": None
    }

    thread = threading.Thread(
        target=process_video_job,
        args=(job_id, parsed_script, intro_voice, shadowing_voice, rate),
        daemon=True
    )
    thread.start()

    return jsonify({"job_id": job_id})

@app.route("/api/render_short", methods=["POST"])
def api_render_short():
    clip_paths = []
    job_id = str(uuid.uuid4())[:8]
    upload_dir = os.path.join("scratch", f"uploads_{job_id}")
    os.makedirs(upload_dir, exist_ok=True)

    if request.is_json:
        data = request.json or {}
        script_input = data.get("script", "")
        voice = data.get("voice", "en-GB-LibbyNeural")
        rate = data.get("rate", "-10%")
    else:
        script_input = request.form.get("script", "")
        voice = request.form.get("voice", "en-GB-LibbyNeural")
        rate = request.form.get("rate", "-10%")

        for field in ["image", "image1", "video1", "video2", "video3"]:
            if field in request.files:
                file = request.files[field]
                if file and file.filename:
                    save_p = os.path.join(upload_dir, file.filename)
                    file.save(save_p)
                    clip_paths.append(save_p)

    if not script_input.strip():
        return jsonify({"error": "Vui lòng nhập kịch bản JSON cho Video Short!"}), 400

    parsed = parse_short_script(script_input)

    render_jobs[job_id] = {
        "status": "PROCESSING",
        "status_msg": "Đang khởi tạo Video Short...",
        "progress": 0,
        "video_filename": None,
        "srt_filename": None,
        "video_url": None,
        "srt_url": None,
        "youtube_metadata": None
    }

    thread = threading.Thread(
        target=process_short_video_job,
        args=(job_id, parsed["title"], parsed["text"], voice, rate, clip_paths, parsed.get("target_word", ""), parsed.get("meaning", "")),
        daemon=True
    )
    thread.start()

    return jsonify({"job_id": job_id})

@app.route("/api/render_short_quiz", methods=["POST"])
def api_render_short_quiz():
    data = request.json or {}
    script_input = data.get("script", "")
    voice = data.get("voice", "en-US-JennyNeural")
    rate = data.get("rate", "-5%")

    if not script_input.strip():
        return jsonify({"error": "Vui lòng nhập kịch bản JSON cho Video Short Quiz!"}), 400

    try:
        parsed_script = parse_short_quiz_script(script_input)
    except Exception as e:
        return jsonify({"error": f"Lỗi định dạng JSON kịch bản Short Quiz: {str(e)}"}), 400

    job_id = str(uuid.uuid4())[:8]
    render_jobs[job_id] = {
        "status": "PROCESSING",
        "status_msg": "Đang khởi tạo Video Short Question...",
        "progress": 0,
        "video_filename": None,
        "srt_filename": None,
        "video_url": None,
        "srt_url": None,
        "youtube_metadata": None
    }

    thread = threading.Thread(
        target=process_short_quiz_video_job,
        args=(job_id, parsed_script, voice, rate),
        daemon=True
    )
    thread.start()

    return jsonify({"job_id": job_id})

@app.route("/api/render_sentence", methods=["POST"])
def api_render_sentence():
    data = request.json or {}
    script_input = data.get("script", "")
    host_voice = data.get("host_voice", "en-US-JennyNeural")
    speaker_a_voice = data.get("speaker_a_voice", "en-US-AvaNeural")
    speaker_b_voice = data.get("speaker_b_voice", "en-GB-SoniaNeural")
    rate = data.get("rate")
    if not rate or not str(rate).strip():
        rate = "-13%"

    if not script_input.strip():
        return jsonify({"error": "Vui lòng nhập kịch bản JSON 15 câu!"}), 400


    try:
        parsed_script = parse_sentence_script(script_input)
    except Exception as e:
        return jsonify({"error": f"Lỗi định dạng JSON kịch bản câu: {str(e)}"}), 400

    job_id = str(uuid.uuid4())[:8]
    render_jobs[job_id] = {
        "status": "PROCESSING",
        "status_msg": "Đang khởi tạo Video 20 Essential Sentences...",
        "progress": 0,
        "video_filename": None,
        "srt_filename": None,
        "video_url": None,
        "srt_url": None,
        "youtube_metadata": None
    }

    thread = threading.Thread(
        target=process_sentence_video_job,
        args=(job_id, parsed_script, host_voice, speaker_a_voice, speaker_b_voice, rate),
        daemon=True
    )
    thread.start()

    return jsonify({"job_id": job_id})



@app.route("/api/status/<job_id>", methods=["GET"])
@app.route("/api/job_status/<job_id>", methods=["GET"])
def api_job_status(job_id):
    job = render_jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job ID không tồn tại!"}), 404
    return jsonify(job)

@app.route("/outputs/<path:filename>")
@app.route("/download/<path:filename>")
@app.route("/api/download/<path:filename>")
def download_file(filename):
    return send_from_directory("output", filename, as_attachment=True)

@app.route("/api/outputs", methods=["GET"])
def list_outputs():
    os.makedirs("output", exist_ok=True)
    files_info = []
    for fname in os.listdir("output"):
        if fname.endswith(".mp4"):
            fpath = os.path.join("output", fname)
            srt_name = fname.replace(".mp4", ".srt")
            files_info.append({
                "filename": fname,
                "srt_filename": srt_name if os.path.exists(os.path.join("output", srt_name)) else None,
                "size": os.path.getsize(fpath)
            })
    files_info.sort(key=lambda x: x["filename"], reverse=True)
    return jsonify({"success": True, "files": files_info})

if __name__ == "__main__":
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except:
            pass
    print("==========================================")
    print("  SHADOWING ENGLISH STUDIO")
    print("  Server running at: http://localhost:5000")
    print("  Default Intro Voice: Libby (en-GB-LibbyNeural)")
    print("  Default Shadowing Voice: Sonia (en-GB-SoniaNeural)")
    print("  Default Speed Rate: -10%")
    print("  YouTube Timed Subtitles (.SRT): ENABLED")
    print("==========================================\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
