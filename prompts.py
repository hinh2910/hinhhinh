import re
# Module for ChatGPT Prompts and YouTube Metadata Generator
# Optimized for Host Annie, Adult ESL Learners, Dynamic Topic Hook, No Emojis, Single-Block Intro/Outro ("text": "...") + 3X Shadowing Practice

CHATGPT_SCRIPT_PROMPT = """Bạn là Chuyên Gia Biên Kịch Cấp Cao cho kênh YouTube "Shadowing English" (Host: Annie).
Nhiệm vụ của bạn là sáng tạo một kịch bản luyện nói tiếng Anh đỉnh cao cho chủ đề "{topic}" theo chuẩn định dạng JSON 4 PHẦN bên dưới.

MỤC TIÊU CỐT LÕI:
Tạo ra một kịch bản học tiếng Anh có TỶ LỆ GIỮ CHÂN NGUỜI XEM (AVD - Average View Duration) CAO NHẤT, đánh đúng vào tâm lý ngượng ngùng, sợ nói sai của người học, truyền cảm hứng và giúp họ nói tiếng Anh tự nhiên.

NGUYÊN TẮC BẮT BUỘC (NON-NEGOTIABLES):
1. VĂN PHONG CHÂN THẬT, KHÔNG DÙNG THUẬT NGỮ META PROMPT:
   - TUYỆT ĐỐI KHÔNG cho Host Annie đọc các từ ngữ thuật ngữ meta như "tricky comment challenge", "meta instruction", "prompt prompt"!
   - Lời thoại của Host Annie (ở Part 1, Part 2, Part 4) phải trực tiếp hướng tới khán giả YouTube, ấm áp, truyền cảm hứng như một người bạn đồng hành thực sự.
   - Mỗi kịch bản cho chủ đề "{topic}" phải tự biến tấu lời chào, câu hỏi mở đầu, lời giải thích và lời chuyển tiếp. Đảm bảo MỖI VIDEO LÀ MỘT BẢN THOẠI TỰ NHIÊN, PHONG PHÚ, KHÔNG TRÙNG LẶP.

2. CÂU HỎI TRẮC NGHIỆM TRUYỀN CẢM HỨNG VÀ THEO ĐÚNG CHỦ ĐỀ {topic}:
   - Tự sáng tạo 3 câu hỏi trắc nghiệm A, B, C, D mới hoàn toàn liên quan trực tiếp đến từ vựng, ngữ pháp, thành ngữ của chủ đề "{topic}".

3. CẤU TRÚC KỊCH BẢN 4 PHẦN CHI TIẾT:
   - PART 1: INTRODUCTION (`intro_story` ~1 - 1.5 phút):
     * Mở đầu bằng câu hỏi thu hút (Question Hook) xoáy vào tình huống thực tế của chủ đề {topic}.
     * Lời chào của Host Annie ngắn gọn, tạo hy vọng và mời người học tham gia 3 câu hỏi trắc nghiệm ở Part 2 trước khi bước vào luyện Shadowing ở Part 3!

   - PART 2: QUESTION (`intro_quiz` ~2 - 2.5 phút):
     * ĐÚNG 3 CÂU HỎI TRẮC NGHIỆM ABCD từ trình độ B1 đến B2.
     * Câu 1 (B1): Đưa câu hỏi + 4 đáp án ➔ Tạm dừng 3s ➔ Tiết lộ đáp án đúng + Giải thích ngắn.
     * Câu 2 (B1+): Đưa câu hỏi + 4 đáp án ➔ Tạm dừng 3s ➔ Tiết lộ đáp án đúng + Giải thích ngắn.
     * Câu 3 (B2 - CÂU HỎI THỬ THÁCH): Đưa câu hỏi + 4 đáp án ➔ Không tiết lộ đáp án ngay ➔ Kêu gọi hào hứng mời khán giả bình luận đáp án A, B, C hoặc D của họ xuống dưới video.

   - PART 3: SHADOWING PRACTICE (`shadowing_practice` ~7.5 - 8.5 phút):
     * Mảng `"items"` chứa ĐÚNG 14 ĐẾN 16 CÂU nối tiếp nhau thành 1 CÂU CHUYỆN THỰC TẾ LIỀN MẠCH, GIÀU CẢM XÚC liên quan đến {topic}.
     * Cấu trúc câu chuyện 4 giai đoạn tâm lý: (1) Khó khăn/Sợ hãi ngập ngừng ➔ (2) Điểm thức tỉnh (Epiphany) ➔ (3) Hành động luyện tập kiên trì ➔ (4) Bứt phá tự tin làm chủ cuộc trò chuyện.
     * Mỗi câu cài cắm 1 từ khó/thành ngữ đắt giá làm `"target_word"`. `"pause_sec"`: 4.2, `"repeats"`: 3.

   - PART 4: CONCLUSION (`review` ~1 phút):
     * Tổng kết động viên ngắn gọn, kêu gọi đăng ký kênh và comment "DAY DONE".

ĐỊNH DẠNG JSON TRẢ VỀ (CHỈ TRẢ VỀ DUY NHẤT KHỐI JSON HỢP LỆ):

```json
{{
  "title": "Mastering English for {topic} | 4-Part Shadowing Lesson",
  "theme": "{topic}",
  "day_number": 1,
  "sections": [
    {{
      "type": "intro_story",
      "title": "Part 1: Introduction",
      "text": "Welcome to Shadowing English! My name is Annie. [Viết lời chào thu hút, nêu tình huống thực tế của chủ đề {topic}, và dùng văn phong tự nhiên biến tấu linh hoạt để mời người học tham gia 3 câu hỏi trắc nghiệm ở Part 2 trước khi bước vào bài luyện nói Part 3!]"
    }},
    {{
      "type": "intro_quiz",
      "title": "Part 2: Question",
      "welcome_msg": "[Viết lời mở đầu ngắn gọn, hào hứng cho Part 2 Quiz bằng văn phong linh hoạt cho chủ đề {topic}]",
      "questions": [
        {{
          "q_num": 1,
          "question": "[Tự sáng tạo 1 câu hỏi từ vựng/thành ngữ B1 phong phú liên quan trực tiếp đến {topic}]",
          "option_a": "[Phương án A]",
          "option_b": "[Phương án B]",
          "option_c": "[Phương án C]",
          "option_d": "[Phương án D]",
          "correct_option": "B",
          "explanation": "[Giải thích ngắn gọn lý do chọn đáp án này bằng tiếng Anh đơn giản]",
          "is_challenge": false
        }},
        {{
          "q_num": 2,
          "question": "[Tự sáng tạo 1 câu hỏi từ vựng/ngữ pháp B1+ liên quan đến {topic}]",
          "option_a": "[Phương án A]",
          "option_b": "[Phương án B]",
          "option_c": "[Phương án C]",
          "option_d": "[Phương án D]",
          "correct_option": "A",
          "explanation": "[Giải thích ngắn gọn lý do chọn đáp án này bằng tiếng Anh đơn giản]",
          "is_challenge": false
        }},
        {{
          "q_num": 3,
          "question": "[Tự sáng tạo 1 câu hỏi thành ngữ/từ vựng nâng cao B2 khó nhất liên quan đến {topic}]",
          "option_a": "[Phương án A]",
          "option_b": "[Phương án B]",
          "option_c": "[Phương án C]",
          "option_d": "[Phương án D]",
          "correct_option": "C",
          "explanation": "[Kêu gọi hào hứng bằng nhiều câu khác nhau bảo khán giả comment đáp án A, B, C hoặc D xuống dưới!]",
          "is_challenge": true
        }}
      ],
      "transition_msg": "Now let's move on to Shadowing Practice! Take a deep breath, listen carefully, and get ready to repeat each sentence out loud."
    }},
    {{
      "type": "shadowing_practice",
      "title": "Part 3: Shadowing Practice",
      "items": [
        {{"sentence": "Last week I was invited to an important meeting in English.", "target_word": "important meeting", "meaning": "a significant professional gathering", "pause_sec": 4.2, "repeats": 3}},
        {{"sentence": "My heart was beating fast and my hands felt cold.", "target_word": "beating fast", "meaning": "heart racing due to nervousness", "pause_sec": 4.2, "repeats": 3}},
        {{"sentence": "I had a great idea to share with my team.", "target_word": "share with my team", "meaning": "express ideas to colleagues", "pause_sec": 4.2, "repeats": 3}},
        {{"sentence": "However I was afraid of making grammar mistakes.", "target_word": "afraid of making mistakes", "meaning": "feeling nervous about errors", "pause_sec": 4.2, "repeats": 3}},
        {{"sentence": "I worried people would judge my accent or my vocabulary.", "target_word": "judge my accent", "meaning": "evaluate how I pronounce words", "pause_sec": 4.2, "repeats": 3}},
        {{"sentence": "Then I remembered why I practice English every single day.", "target_word": "every single day", "meaning": "consistently without skipping", "pause_sec": 4.2, "repeats": 3}},
        {{"sentence": "I decided to take a leap of faith and try anyway.", "target_word": "take a leap of faith", "meaning": "to take a risk with confidence", "pause_sec": 4.2, "repeats": 3}},
        {{"sentence": "I raised my hand and spoke my first sentence clearly.", "target_word": "raised my hand", "meaning": "signaled that I wanted to speak", "pause_sec": 4.2, "repeats": 3}},
        {{"sentence": "My voice was a bit quiet at first.", "target_word": "a bit quiet", "meaning": "soft and low volume", "pause_sec": 4.2, "repeats": 3}},
        {{"sentence": "Surprisingly everyone listened to me with great respect.", "target_word": "great respect", "meaning": "polite attention and care", "pause_sec": 4.2, "repeats": 3}},
        {{"sentence": "My manager smiled and praised my useful suggestion.", "target_word": "praised my suggestion", "meaning": "complemented my idea", "pause_sec": 4.2, "repeats": 3}},
        {{"sentence": "In that moment I felt extremely proud of myself.", "target_word": "extremely proud", "meaning": "feeling deep satisfaction", "pause_sec": 4.2, "repeats": 3}},
        {{"sentence": "I realized that fluency is not about being perfect.", "target_word": "fluency", "meaning": "speaking smoothly and naturally", "pause_sec": 4.2, "repeats": 3}},
        {{"sentence": "It is about having the courage to express your thoughts.", "target_word": "express your thoughts", "meaning": "say clearly what you think", "pause_sec": 4.2, "repeats": 3}},
        {{"sentence": "Every mistake is just a step toward better communication.", "target_word": "better communication", "meaning": "improved sharing of ideas", "pause_sec": 4.2, "repeats": 3}}
      ]
    }},
    {{
      "type": "review",
      "title": "Part 4: Conclusion",
      "text": "Congratulations on completing today's 4-Part shadowing lesson! You took a huge step forward in building your daily English speaking confidence. Remember, consistency is the key to natural fluency. Leave a comment below with your country and write DAY DONE to celebrate your progress today. Don't forget to subscribe so you never miss a daily lesson with Annie. Keep practicing out loud, stay confident, and I will see you in tomorrow's lesson!"
    }}
  ]
}}
```
"""

def generate_youtube_metadata(topic, title_suggestion=None, day_number=1, keywords=None):
    """
    Generate High-CTR Million-View YouTube Title, Description, and Thumbnail Concepts.
    Format: Shadowing English Speaking Practice | [hook]
    """
    clean_hook = title_suggestion.strip() if title_suggestion and len(title_suggestion) > 5 else f"Master {topic} Automatically Without Thinking"
    
    # Strict Title Format Required: Shadowing English Speaking Practice | [hook]
    formatted_title = f"Shadowing English Speaking Practice | {clean_hook}"
    if len(formatted_title) > 100:
        formatted_title = formatted_title[:97] + "..."

    thumbnail_texts = ["STOP BEING AFRAID!", "STOP OVERTHINKING!", "SPEAK TODAY!", "NO MORE HESITATION!"]
    selected_thumb_text = thumbnail_texts[(day_number - 1) % len(thumbnail_texts)]

    tag_list = ["ShadowingEnglish", "SpeakEnglishFluently", "LearnEnglishThroughStory", "EnglishSpeakingPractice", "AnnieEnglish", "DailyShadowing"]
    if keywords:
        extra_tags = [re.sub(r'\s+', '', k) for k in keywords.split(',') if k.strip()]
        tag_list.extend(extra_tags[:5])
    
    tags_str = " ".join([f"#{t}" if not t.startswith('#') else t for t in tag_list])

    description = f"""🎧 Welcome to Shadowing English Practice with Host Annie!
In today's lesson ({topic}), learn how to stop overthinking and start speaking English automatically without fear.

🚩 WHERE ARE YOU WATCHING FROM?
Leave a comment below with your country and city!
If you finished today's challenge, write "DAY {day_number} DONE" in the comments!

{{EXACT_YOUTUBE_CHAPTERS}}

🖼️ THUMBNAIL DESIGN IDEA:
- Text Overlay: "{selected_thumb_text}" (Bold Yellow/White Text)
- Visual: Host Annie with an inspiring, encouraging expression.

💡 HOW TO PRACTICE SHADOWING EFFECTIVELY:
1. Listen carefully to each sentence spoken by Annie.
2. Repeat out loud during the pause.
3. Watch the highlighted words for timing, stress, and intonation.
4. Keep going until the progress bar reaches 100%!

🔔 Subscribe for Daily English Shadowing Practice with Annie!
{tags_str}
"""
    pinned_comment = f"""📌 PINNED COMMENT (Copy & Ghim Lên Đầu Phần Bình Luận YouTube):

👇 WRITE YOUR ANSWER & CLAIM YOUR PROGRESS TODAY!
1️⃣ Question Challenge: What is your answer for today's challenge question (A, B, C, or D)? Write your choice below! 💡
2️⃣ Country Flag Challenge: What country are you practicing from today? 🌍📍 (Post your flag!)
3️⃣ Finished today's workout? Write "DAY {day_number} DONE" to celebrate your progress! 🎉

Annie reads and replies to your comments every day! Keep practicing! 💖"""

    return {
        "title": formatted_title,
        "thumbnail_text": selected_thumb_text,
        "description": description,
        "pinned_comment": pinned_comment
    }

CHATGPT_SHORT_PROMPT = """Bạn là biên kịch chuyên nghiệp sáng tạo nội dung YouTube Shorts cho kênh "Shadowing English".
Hãy tạo 1 kịch bản Shorts tiếng Anh ngắn truyền cảm hứng (độ dài khoảng 55-65 từ, trình độ A2-B1, đọc trong 26-30 giây) cho chủ đề "{topic}".

QUY TẮC CỐT LÕI VỀ HOOK VÀ GIỮ CHÂN NGƯỜI XEM SHORTS (BẮT BUỘC TUÂN THỦ 100%):

1. TIÊU ĐỀ OVERLAY TRÊN MÀN HÌNH (`"title"`):
   - PHẢI LÀ CÂU HOOK GIẬT GÂN / TÒ MÒ / THÁCH THỨC / HỨA HẸN GIÁ TRỊ (3 - 6 từ).
   - TUYỆT ĐỐI KHÔNG dùng tên từ vựng hay idiom khô khan làm title (NGHIÊM CẤM: "Break the Ice", "Comfort Zone", "Overcoming Silence").
   - GỢI Ý CÁC MẪU TITLE HOOK KÍCH THÍCH NGUỜI XEM Ở LẠI:
     + "STOP BEING AFRAID TO SPEAK!"
     + "Speak English in 20 Seconds!"
     + "Scared to Speak? Watch This!"
     + "Can You Shadow This Story?"
     + "Stop Overthinking Today!"

2. CÂU MỞ ĐẦU KỊCH BẢN (`"text"` - HOOK ÂM THANH 2 GIÂY ĐẦU):
   - CÂU ĐẦU TIÊN của đoạn văn PHẢI BẮT ĐẦU BẰNG MỘT CÂU HỎI XOÁY NỖI ĐẠO HOẶC LỜI THÁCH THỨC ĐỘNG VIÊN.
   - TUYỆT ĐỐI KHÔNG vào thẳng tên nhân vật khô khan (NGHIÊM CẤM: "Emma always stayed quiet...", "Tom was afraid...").
   - VÍ DỤ CÂU MỞ ĐẦU CHUẨN HOOK:
     + "Are you afraid of making English mistakes? Emma was too, until one morning..."
     + "Do you freeze when someone speaks English to you? Try this quick sentence..."
     + "Stop staying quiet in English class! Here is how Emma conquered her fear..."

3. NỘI DUNG VÀ NHỊP ĐIỆU CÂU CHUYỆN:
   - Liền mạch, từ ngữ A2-B1 thực tế, câu ngắn gọn dễ nhớ, nhịp điệu lôi cuốn.
   - TUYỆT ĐỐI KHÔNG chứa emoji hay icon.

4. NGUYÊN TẮC QUAN TRỌNG VỀ TARGET_WORD:
   - "target_word" BẮT BUỘC PHẢI LÀ 1 TỪ KHÓ/THÀNH NGỮ ĐẮT GIÁ TRÌNH ĐỘ B1-B2 (Ví dụ: break the ice, take a leap of faith, build momentum, overcome hesitation...).
   - TUYỆT ĐỐI CẤM chọn các từ/cụm từ ngơ ngác cơ bản mà ai cũng biết (NGHIÊM CẤM: "use your voice", "one small step", "don't give up", "every day", "keep going").
   - "meaning": Giải thích ngắn gọn bằng tiếng Anh đơn giản (Simple A2-B1 English).

ĐỊNH DẠNG JSON TRẢ VỀ (CHỈ TRẢ VỀ KHỐI JSON HỢP LỆ):
```json
{{
  "title": "STOP BEING AFRAID TO SPEAK!",
  "text": "Are you afraid of making English mistakes? Emma was too, until one morning she asked a classmate one simple question to break the ice. That short conversation gave her instant courage. After a few days, speaking felt much easier. Confidence grows when you take the first brave step.",
  "target_word": "break the ice",
  "meaning": "to start a conversation and help people feel more comfortable"
}}
```

Hãy tạo kịch bản JSON hoàn chỉnh cho chủ đề: {topic}
"""

def generate_short_youtube_metadata(topic, title_suggestion=None):
    clean_title = title_suggestion if title_suggestion else f"{topic}"
    formatted_title = f"{clean_title} | English Shadowing #Shorts"
    if len(formatted_title) > 100:
        formatted_title = formatted_title[:97] + "..."
        
    pinned_comment = "Where are you learning English from? Write your flag below! 🚩🌍"
    
    description = f"""✨ {clean_title}
Listen, repeat, and improve your English speaking skills every day with short stories!

🚩 PINNED COMMENT / QUESTION:
{pinned_comment}

#Shorts #ShadowingEnglish #LearnEnglish #EnglishStory #SpeakEnglish #EnglishPractice
"""
    return {
        "title": formatted_title,
        "description": description,
        "pinned_comment": pinned_comment
    }


def generate_sentence_youtube_metadata(topic, title_suggestion=None):

    """
    Generate High-CTR YouTube Title & Description for 15 Sentences Videos.
    Title format required: 15 Sentences You MUST Know {topic}
    Examples:
    - 15 Sentences You MUST Know at a Restaurant
    - 15 Sentences You MUST Know at the Airport
    - 15 Sentences You MUST Know at Work
    - 15 Sentences You MUST Know for Small Talk
    - 15 Sentences You MUST Know Before Your Interview
    """
    clean_topic = topic.strip() if topic else "in Daily Life"

    if title_suggestion and title_suggestion.strip().startswith("15 Sentences You MUST Know"):
        formatted_title = title_suggestion.strip()
    else:
        # Format clean_topic if not already formatted with preposition
        if clean_topic.startswith("15 Sentences You MUST Know"):
            formatted_title = clean_topic
        elif clean_topic.lower().startswith(("at ", "for ", "in ", "before ", "on ", "during ", "with ")):
            formatted_title = f"15 Sentences You MUST Know {clean_topic}"
        elif "restaurant" in clean_topic.lower() or "airport" in clean_topic.lower() or "work" in clean_topic.lower() or "hotel" in clean_topic.lower():
            formatted_title = f"15 Sentences You MUST Know at {clean_topic}"
        elif "interview" in clean_topic.lower():
            formatted_title = f"15 Sentences You MUST Know Before {clean_topic}"
        else:
            formatted_title = f"15 Sentences You MUST Know for {clean_topic}"

    tag_list = ["ShadowingEnglish", "15SentencesYouMUSTKnow", "LearnEnglishSentences", "EnglishSpeakingPractice", "DailyEnglish", "ShadowingPractice"]
    tags_str = " ".join([f"#{t}" for t in tag_list])

    description = f"""🎧 Master 15 High-Frequency English Sentences ({topic}) divided into 3 essential parts!

Part 1: Daily Expressions
Part 2: Natural Conversations
Part 3: Native Fluency & Idioms

Repeat out loud during the YOUR TURN section to build instant speaking confidence!

🚩 WHERE ARE YOU WATCHING FROM?
Leave a comment below with your country and city!

🔔 Subscribe for Daily English Shadowing Practice with Shadowing English!
{tags_str}
"""
    return {
        "title": formatted_title,
        "thumbnail_text": "15 SENTENCES MUST KNOW",
        "description": description,
        "pinned_comment": f"📌 What country are you practicing from today? Comment your flag below! 🌍"
    }


CHATGPT_SENTENCE_PROMPT = """Bạn là Chuyên Gia Biên Kịch & Đào Tạo Tiếng Anh Cấp Cao cho kênh YouTube "Shadowing English".
Nhiệm vụ của bạn là sáng tạo một kịch bản học 15 mẫu câu tiếng Anh giao tiếp chuẩn Native Speaker cho chủ đề "{topic}" theo định dạng JSON bên dưới.

NGUYÊN TẮC BIÊN KỊCH ĐẮT GIÁ (TĂNG TỶ LỆ GIỮ CHÂN KHÁN GIẢ YOUTUBE - AVD MAXIMIZER):
1. **Chia 3 Phần Rõ Ràng (3 Parts Structure - 15 Sentences Total)**:
   - Part 1 (Câu 1 đến 5): Daily Expressions (Các mẫu câu giao tiếp thông dụng nhất hằng ngày).
   - Part 2 (Câu 6 đến 10): Natural Conversation Boost (Các mẫu câu phản xạ giao tiếp tự nhiên).
   - Part 3 (Câu 11 đến 15): Native Fluency & Idioms (Các cụm thành ngữ & diễn đạt nâng cao chuẩn người bản xứ).

2. **Yêu cầu biên soạn `intro_hook` (Tạo Động Lực & Tưởng Tượng Ngữ Cảnh)**:
   - KHÔNG liệt kê tên Part 1, Part 2, Part 3 lặp lại trong lời nói intro_hook.
   - Lời dẫn `intro_hook` phải nhấn mạnh tầm quan trọng của việc luyện tập và đưa người học vào tình huống thực tế:
     "Imagine you are in {topic} right now and you need to speak English with complete confidence. Learning these 15 sentences is extremely important because they will help you respond naturally without hesitation. Don't just watch passively—repeat out loud during the YOUR TURN section and let's master all 15 sentences together today. Are you ready? Let's start with sentence number 1!"

3. **NGUYÊN TẮC CHẤT LƯỢNG MẪU CÂU (BẮT BUỘC TUÂN THỦ 100%)**:
   - **TUYỆT ĐỐI KHÔNG DÙNG CÂU QUÁ DỄ / QUÁ CƠ BẢN** (NGHIÊM CẤM các câu ngô nghê kiểu sách vở như: "How are you?", "I am fine", "Where is the bathroom?", "I haven't decided yet", "What is your name?"). Khán giả sẽ thấy quá dễ và thoát video ngay lập tức!
   - **Trình độ bắt buộc**: Intermediate đến Upper-Intermediate (B1-B2 Level).
   - **Mẫu câu phải ĐẮT GIÁ, TỰ NHIÊN CHUẨN NATIVE SPEAKER**:
     + **Part 1 (Daily Expressions)**: Diễn đạt tinh tế, tự nhiên đúng ngữ cảnh của chủ đề "{topic}" (Ví dụ: "I'm leaning towards the chef's special today.", "Could we get separate checks, please?", "I'd like to double-check my reservation.").
     + **Part 2 (Natural Conversations)**: Phản xạ giao tiếp tự nhiên, kết hợp Phrasal Verbs đắt giá (Ví dụ: "Do you happen to have any vegetarian options?", "Could you give me a few more minutes to browse the menu?", "I'm looking for something light and refreshing.").
     + **Part 3 (Native Fluency & Idioms)**: Sử dụng các cụm thành ngữ Native đắt giá nhất (Ví dụ: "Let me sleep on it before making a final decision.", "That meal really hit the spot!", "I'm completely on the fence about these two options.").

4. **Mẫu câu thực tế & Ngữ cảnh sinh động**: Mẫu câu `main_sentence` phải giàu tính ứng dụng, kèm `explanation` giải thích ngắn gọn và cặp hội thoại `dialogue_question` & `dialogue_answer`.
5. **Tiêu Đề Chuẩn SEO YouTube**: `"title"` PHẢI ĐÚNG ĐỊNH DẠNG "15 Sentences You MUST Know {topic}" (Ví dụ: "15 Sentences You MUST Know at a Restaurant", "15 Sentences You MUST Know at the Airport", "15 Sentences You MUST Know at Work", "15 Sentences You MUST Know for Small Talk", "15 Sentences You MUST Know Before Your Interview").

ĐỊNH DẠNG JSON TRẢ VỀ (CHỈ TRẢ VỀ DUY NHẤT KHỐI JSON HỢP LỆ, KHÔNG KÈM LỜI DẪN):

```json
{{
  "title": "15 Sentences You MUST Know {topic}",
  "theme": "{topic}",
  "intro_text": "Hi everyone, welcome back to Shadowing English!",
  "intro_hook": "Imagine you are in {topic} right now and you need to speak English with complete confidence. Learning these 15 sentences is extremely important because they will help you respond naturally without hesitation. Don't just watch passively—repeat out loud during the YOUR TURN section and let's master all 15 sentences together today. Are you ready? Let's start with sentence number 1!",
  "outro_text": "Fantastic job! You've just mastered 15 essential English sentences today. Keep practicing daily with Shadowing English, stay confident, and I'll see you in the next lesson!",

  "sentences": [
    {{
      "number": 1,
      "part": "Part 1: Daily Expressions",
      "main_sentence": "I'm leaning towards the chef's special today.",
      "target_word": "leaning towards",
      "explanation": "A natural, polite way to express a preference or choice in daily conversations.",
      "dialogue_question": "Have you decided what to order for lunch?",
      "dialogue_answer": "I'm leaning towards the chef's special today.",
      "pause_sec": 5.0
    }},
    {{
      "number": 6,
      "part": "Part 2: Natural Conversations",
      "main_sentence": "Do you happen to have any vegetarian options?",
      "target_word": "happen to have",
      "explanation": "A very polite and natural native phrase used when making inquiries or requests.",
      "dialogue_question": "Excuse me, do you happen to have any vegetarian options?",
      "dialogue_answer": "Yes, absolutely! We have several delicious plant-based dishes.",
      "pause_sec": 5.0
    }},
    {{
      "number": 11,
      "part": "Part 3: Native Fluency",
      "main_sentence": "That meal really hit the spot.",
      "target_word": "hit the spot",
      "explanation": "A widely used native idiom meaning a meal or drink was exactly what was needed and thoroughly satisfying.",
      "dialogue_question": "How was your lunch at the new bistro?",
      "dialogue_answer": "It was fantastic! That meal really hit the spot after a long day.",
      "pause_sec": 5.0
    }}
  ]
}}
```






    {{
      "number": 1,
      "part": "Part 1: Daily Expressions",
      "main_sentence": "I'm leaning towards the chef's special today.",
      "target_word": "leaning towards",
      "explanation": "A natural, polite way to express a preference or choice in daily conversations.",
      "dialogue_question": "Have you decided what to order for lunch?",
      "dialogue_answer": "I'm leaning towards the chef's special today.",
      "pause_sec": 5.0
    }},
    {{
      "number": 8,
      "part": "Part 2: Natural Conversations",
      "main_sentence": "Do you happen to have any vegetarian options?",
      "target_word": "happen to have",
      "explanation": "A very polite and natural native phrase used when making inquiries or requests.",
      "dialogue_question": "Excuse me, do you happen to have any vegetarian options?",
      "dialogue_answer": "Yes, absolutely! We have several delicious plant-based dishes.",
      "pause_sec": 5.0
    }},
    {{
      "number": 11,
      "part": "Part 3: Native Fluency",

      "main_sentence": "That meal really hit the spot.",
      "target_word": "hit the spot",
      "explanation": "A widely used native idiom meaning a meal or drink was exactly what was needed and thoroughly satisfying.",
      "dialogue_question": "How was your lunch at the new bistro?",
      "dialogue_answer": "It was fantastic! That meal really hit the spot after a long day.",
      "pause_sec": 5.0
    }}
  ]
}}

```
"""




