document.addEventListener('DOMContentLoaded', () => {

  // Current Video Mode State: 'long', 'podcast', 'ielts', 'short'
  let currentVideoMode = 'long';

  // Mode Selector Elements
  const btnModeLong = document.getElementById('btn-mode-long');
  const btnModeSentence = document.getElementById('btn-mode-sentence');
  const btnModePodcast = document.getElementById('btn-mode-podcast');
  const btnModeIelts = document.getElementById('btn-mode-ielts');
  const btnModeShort = document.getElementById('btn-mode-short');
  const shortClipsBox = document.getElementById('short-video-clips-box');
  const shadowingVoiceContainer = document.getElementById('shadowing-voice-container');
  const lblIntroVoice = document.getElementById('lbl-intro-voice');

  const step1Title = document.getElementById('step1-header-title');
  const step1Desc = document.getElementById('step1-header-desc');
  const step2Title = document.getElementById('step2-header-title');
  const step2Desc = document.getElementById('step2-header-desc');

  function setVideoMode(mode) {
    currentVideoMode = mode;
    if (btnModeLong) btnModeLong.classList.toggle('active', mode === 'long');
    if (btnModeSentence) btnModeSentence.classList.toggle('active', mode === 'sentence');
    if (btnModePodcast) btnModePodcast.classList.toggle('active', mode === 'podcast');
    if (btnModeIelts) btnModeIelts.classList.toggle('active', mode === 'ielts');
    if (btnModeShort) btnModeShort.classList.toggle('active', mode === 'short');

    const rateSelect = document.getElementById('rate-select');
    if (rateSelect) rateSelect.value = '-5%';

    const mainVideoPlayer = document.getElementById('main-video-player');

    if (mode === 'short') {
      if (shortClipsBox) shortClipsBox.style.display = 'block';
      if (shadowingVoiceContainer) shadowingVoiceContainer.style.display = 'none';
      if (lblIntroVoice) lblIntroVoice.innerText = '🎙️ Chọn Giọng Đọc Video Short:';
      if (step1Title) step1Title.innerText = '📝 Bước 1: Lấy Prompt Câu Chuyện Ngẫu Nhiên Short (< 30s)';
      if (step1Desc) step1Desc.innerText = 'Nhập chủ đề và copy prompt để ChatGPT viết 1 câu chuyện ngẫu nhiên ngắn tiếng Anh truyền cảm hứng (< 30 giây).';
      if (step2Title) step2Title.innerText = '📥 Bước 2: Dán Kịch Bản Short & Chọn Giọng + Import 1 Ảnh Nền';
      if (step2Desc) step2Desc.innerText = 'Dán kịch bản Short từ ChatGPT, chọn 1 hình ảnh nền cho phần trên video và giọng đọc.';
      if (mainVideoPlayer) mainVideoPlayer.classList.add('vertical-short');
    } else if (mode === 'sentence') {
      if (shortClipsBox) shortClipsBox.style.display = 'none';
      if (shadowingVoiceContainer) shadowingVoiceContainer.style.display = 'block';
      if (lblIntroVoice) lblIntroVoice.innerText = '🎙️ Giọng Host Dẫn Chuyện (Intro/Outro):';
      if (step1Title) step1Title.innerText = '📝 Bước 1: Lấy Prompt ChatGPT 20 Essential Sentences (Hỏi - Đáp)';
      if (step1Desc) step1Desc.innerText = 'Prompt tạo kịch bản 20 câu giao tiếp thực tế kèm ví dụ Hộp thoại Hỏi & Đáp chuẩn A2/B1.';
      if (step2Title) step2Title.innerText = '📥 Bước 2: Dán Kịch Bản 20 Câu & Chọn Giọng Host + Speaker A/B';
      if (step2Desc) step2Desc.innerText = 'Dán kịch bản 20 câu từ ChatGPT, hệ thống sẽ tự động ghép giọng Hỏi & Đáp + khoảng Pause nhại lại.';
      if (mainVideoPlayer) mainVideoPlayer.classList.remove('vertical-short');
    } else if (mode === 'podcast') {
      if (shortClipsBox) shortClipsBox.style.display = 'none';
      if (shadowingVoiceContainer) shadowingVoiceContainer.style.display = 'block';
      if (lblIntroVoice) lblIntroVoice.innerText = '🎙️ Chọn Giọng Nữ (Host Jenny):';
      if (step1Title) step1Title.innerText = '📝 Bước 1: Lấy Prompt ChatGPT Podcast (>= 15 Phút)';
      if (step1Desc) step1Desc.innerText = 'Prompt tạo kịch bản cuộc trò chuyện 2 giọng Nam & Nữ đối thoại tự nhiên chuẩn B1-B2.';
      if (step2Title) step2Title.innerText = '📥 Bước 2: Dán Kịch Bản Podcast & Chọn Giọng Nam/Nữ';
      if (step2Desc) step2Desc.innerText = 'Dán kịch bản đối thoại Podcast từ ChatGPT, hệ thống sẽ tự động ghép giọng Nam & Nữ.';
      if (mainVideoPlayer) mainVideoPlayer.classList.remove('vertical-short');
    } else if (mode === 'ielts') {
      if (shortClipsBox) shortClipsBox.style.display = 'none';
      if (shadowingVoiceContainer) shadowingVoiceContainer.style.display = 'block';
      if (lblIntroVoice) lblIntroVoice.innerText = '🎙️ Chọn Giọng Đọc IELTS Listening:';
      if (step1Title) step1Title.innerText = '📝 Bước 1: Lấy Prompt ChatGPT IELTS Listening (>= 20 Phút)';
      if (step1Desc) step1Desc.innerText = 'Prompt tạo kịch bản bài nghe IELTS Listening chuẩn Anh - Anh Band 7.0+.';
      if (step2Title) step2Title.innerText = '📥 Bước 2: Dán Kịch Bản IELTS Listening & Chọn Giọng';
      if (step2Desc) step2Desc.innerText = 'Dán kịch bản IELTS Listening từ ChatGPT, hệ thống sẽ tự động tạo bài nghe chuẩn âm thanh.';
      if (mainVideoPlayer) mainVideoPlayer.classList.remove('vertical-short');
    } else {
      if (shortClipsBox) shortClipsBox.style.display = 'none';
      if (shadowingVoiceContainer) shadowingVoiceContainer.style.display = 'block';
      if (lblIntroVoice) lblIntroVoice.innerText = '🎙️ Giọng đọc Phần Intro (Dẫn Chuyện):';
      if (step1Title) step1Title.innerText = '📝 Bước 1: Lấy Prompt Chuẩn Kịch Bản (>= 12 Phút)';
      if (step1Desc) step1Desc.innerText = 'Nhập chủ đề bài học và copy prompt để ChatGPT viết kịch bản từ vựng giao tiếp đơn giản A2/B1.';
      if (step2Title) step2Title.innerText = '📥 Bước 2: Dán Kịch Bản & Chọn Giọng Đọc';
      if (step2Desc) step2Desc.innerText = 'Mặc định sử dụng Giọng Libby cho lời dẫn Intro và Giọng Sonia cho đoạn Shadowing.';
      if (mainVideoPlayer) mainVideoPlayer.classList.remove('vertical-short');
    }

    loadPrompt();
  }

  if (btnModeLong) btnModeLong.addEventListener('click', () => setVideoMode('long'));
  if (btnModeSentence) btnModeSentence.addEventListener('click', () => setVideoMode('sentence'));
  if (btnModePodcast) btnModePodcast.addEventListener('click', () => setVideoMode('podcast'));
  if (btnModeIelts) btnModeIelts.addEventListener('click', () => setVideoMode('ielts'));
  if (btnModeShort) btnModeShort.addEventListener('click', () => setVideoMode('short'));


  // Step Navigation
  const stepBtns = document.querySelectorAll('.step-btn');
  const stepContents = document.querySelectorAll('.step-content');

  function switchStep(stepNum) {
    stepBtns.forEach(btn => {
      btn.classList.toggle('active', btn.dataset.step == stepNum);
    });
    stepContents.forEach(content => {
      content.classList.toggle('active', content.id == `step-${stepNum}`);
    });
    if (stepNum == 4) {
      loadOutputsList();
    }
  }

  stepBtns.forEach(btn => {
    btn.addEventListener('click', () => switchStep(btn.dataset.step));
  });

  // Step 1: Fetch ChatGPT Prompt
  const topicInput = document.getElementById('prompt-topic');
  const promptTextarea = document.getElementById('prompt-text');
  const btnCopyPrompt = document.getElementById('btn-copy-prompt');
  const btnGotoStep2 = document.getElementById('btn-goto-step2');

  async function loadPrompt() {
    try {
      const res = await fetch('/api/generate_prompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: topicInput.value,
          video_type: currentVideoMode
        })
      });
      const data = await res.json();
      promptTextarea.value = data.prompt;
    } catch (err) {
      console.error("Error fetching prompt:", err);
    }
  }

  loadPrompt();
  topicInput.addEventListener('input', loadPrompt);

  btnCopyPrompt.addEventListener('click', () => {
    navigator.clipboard.writeText(promptTextarea.value);
    btnCopyPrompt.innerText = "✅ Đã Copy Prompt!";
    setTimeout(() => {
      btnCopyPrompt.innerText = "📋 Copy Prompt Vừa Tạo";
    }, 2000);
  });

  btnGotoStep2.addEventListener('click', () => switchStep(2));

  // Step 2: Voice Selectors & Preview Players
  const introVoiceSelect = document.getElementById('intro-voice-select');
  const shadowingVoiceSelect = document.getElementById('shadowing-voice-select');
  const rateSelect = document.getElementById('rate-select');
  const introVoicePlayer = document.getElementById('intro-voice-player');
  const shadowingVoicePlayer = document.getElementById('shadowing-voice-player');
  const btnStartRender = document.getElementById('btn-start-render');
  const scriptJsonArea = document.getElementById('script-json');

  function updateVoicePreviews() {
    if (introVoiceSelect && introVoicePlayer) {
      introVoicePlayer.src = `/static/voice_samples/${introVoiceSelect.value}.mp3`;
    }
    if (shadowingVoiceSelect && shadowingVoicePlayer) {
      shadowingVoicePlayer.src = `/static/voice_samples/${shadowingVoiceSelect.value}.mp3`;
    }
  }

  updateVoicePreviews();
  introVoiceSelect.addEventListener('change', updateVoicePreviews);
  shadowingVoiceSelect.addEventListener('change', updateVoicePreviews);

  let currentJobId = null;
  let pollInterval = null;

  btnStartRender.addEventListener('click', async () => {
    const scriptVal = scriptJsonArea.value.trim();
    if (!scriptVal) {
      alert("Vui lòng dán nội dung kịch bản JSON từ ChatGPT vào!");
      return;
    }

    btnStartRender.disabled = true;
    btnStartRender.innerText = "⏳ Đang Khởi Tạo Process Render...";

    try {
      let res, data;
      if (currentVideoMode === 'short') {
        const formData = new FormData();
        formData.append('script', scriptVal);
        formData.append('voice', introVoiceSelect.value);
        formData.append('rate', rateSelect.value);

        const imgFile = document.getElementById('short-image-file');
        if (imgFile && imgFile.files[0]) {
          formData.append('image', imgFile.files[0]);
        }

        res = await fetch('/api/render_short', {
          method: 'POST',
          body: formData
        });
      } else if (currentVideoMode === 'sentence') {
        res = await fetch('/api/render_sentence', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            script: scriptVal,
            host_voice: introVoiceSelect ? introVoiceSelect.value : 'en-US-JennyNeural',
            speaker_a_voice: 'en-US-AvaNeural',
            speaker_b_voice: shadowingVoiceSelect ? shadowingVoiceSelect.value : 'en-GB-SoniaNeural',
            rate: rateSelect ? rateSelect.value : '-5%'
          })
        });
      } else {
        res = await fetch('/api/render', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            script: scriptVal,
            intro_voice: introVoiceSelect.value,
            shadowing_voice: shadowingVoiceSelect.value,
            rate: rateSelect.value
          })
        });
      }


      data = await res.json();
      if (!res.ok) {
        alert(data.error || "Lỗi khởi tạo render!");
        btnStartRender.disabled = false;
        btnStartRender.innerText = "🚀 Bắt Đầu Render Video Tự Động";
        return;
      }

      currentJobId = data.job_id;
      switchStep(3);
      startPollingStatus(currentJobId);

    } catch (err) {
      alert("Lỗi kết nối máy chủ: " + err.message);
    } finally {
      btnStartRender.disabled = false;
      btnStartRender.innerText = "🚀 Bắt Đầu Render Video Tự Động";
    }
  });

  // Step 3: Polling Status & Preview
  const statusText = document.getElementById('status-text');
  const progressPercent = document.getElementById('progress-percent');
  const progressFill = document.getElementById('progress-fill');
  const videoPreviewBox = document.getElementById('video-preview-box');
  const mainVideoPlayer = document.getElementById('main-video-player');
  const btnDownloadVideo = document.getElementById('btn-download-video');
  const btnGotoStep4 = document.getElementById('btn-goto-step4');

  function startPollingStatus(jobId) {
    videoPreviewBox.style.display = "none";

    if (pollInterval) clearInterval(pollInterval);

    pollInterval = setInterval(async () => {
      try {
        const res = await fetch(`/api/job_status/${jobId}`);
        const job = await res.json();

        statusText.innerText = job.status_msg || "Đang xử lý...";
        progressPercent.innerText = `${job.progress}%`;
        progressFill.style.width = `${job.progress}%`;

        if (job.status === "COMPLETED") {
          clearInterval(pollInterval);
          progressFill.style.width = "100%";

          const videoUrl = `/outputs/${job.video_filename}`;
          mainVideoPlayer.src = videoUrl;
          btnDownloadVideo.href = `/api/download/${job.video_filename}`;

          if (currentVideoMode === 'short' || job.video_filename.startsWith('short_')) {
            mainVideoPlayer.classList.add('vertical-short');
          } else {
            mainVideoPlayer.classList.remove('vertical-short');
          }

          let btnSrt = document.getElementById('btn-download-srt');
          if (!btnSrt && job.srt_filename) {
            btnSrt = document.createElement('a');
            btnSrt.id = 'btn-download-srt';
            btnSrt.className = 'btn btn-secondary';
            btnSrt.style.marginLeft = '10px';
            btnSrt.innerText = '📝 Tải Phụ Đề (.SRT) Cho YouTube';
            btnDownloadVideo.parentNode.insertBefore(btnSrt, btnDownloadVideo.nextSibling);
          }
          if (btnSrt && job.srt_filename) {
            btnSrt.href = `/api/download/${job.srt_filename}`;
          }

          videoPreviewBox.style.display = "block";

          if (job.youtube_metadata) {
            if (document.getElementById('yt-title')) document.getElementById('yt-title').value = job.youtube_metadata.title || '';
            if (document.getElementById('yt-desc')) document.getElementById('yt-desc').value = job.youtube_metadata.description || '';
            if (document.getElementById('yt-pinned')) document.getElementById('yt-pinned').value = job.youtube_metadata.pinned_comment || '';
          }

        } else if (job.status === "FAILED") {
          clearInterval(pollInterval);
          alert("Lỗi Render: " + job.status_msg);
        }

      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 1500);
  }

  btnGotoStep4.addEventListener('click', () => switchStep(4));

  // Step 4: Outputs Library & Copy Metadata
  const btnCopyTitle = document.getElementById('btn-copy-title');
  const btnCopyDesc = document.getElementById('btn-copy-desc');
  const btnCopyPinned = document.getElementById('btn-copy-pinned');
  const ytTitleInput = document.getElementById('yt-title');
  const ytDescArea = document.getElementById('yt-desc');
  const ytPinnedArea = document.getElementById('yt-pinned');
  const outputsContainer = document.getElementById('outputs-list-container');

  if (btnCopyTitle) {
    btnCopyTitle.addEventListener('click', () => {
      navigator.clipboard.writeText(ytTitleInput.value);
      btnCopyTitle.innerText = "✅ Copied!";
      setTimeout(() => { btnCopyTitle.innerText = "Copy Title"; }, 2000);
    });
  }

  if (btnCopyDesc) {
    btnCopyDesc.addEventListener('click', () => {
      navigator.clipboard.writeText(ytDescArea.value);
      btnCopyDesc.innerText = "✅ Copied!";
      setTimeout(() => { btnCopyDesc.innerText = "Copy Description"; }, 2000);
    });
  }

  if (btnCopyPinned) {
    btnCopyPinned.addEventListener('click', () => {
      navigator.clipboard.writeText(ytPinnedArea.value);
      btnCopyPinned.innerText = "✅ Copied!";
      setTimeout(() => { btnCopyPinned.innerText = "📋 Copy Pinned Comment"; }, 2000);
    });
  }

  async function loadOutputsList() {
    try {
      const res = await fetch('/api/outputs');
      const data = await res.json();
      if (data.success && data.files) {
        if (data.files.length === 0) {
          outputsContainer.innerHTML = `<p style="color: var(--text-muted);">Chưa có video nào trong thư mục output/.</p>`;
          return;
        }
        outputsContainer.innerHTML = data.files.map(f => `
          <div class="output-item">
            <div>
              <strong>${f.filename.startsWith('short_') ? '📱' : '🎥'} ${f.filename}</strong>
              <div style="font-size: 12px; color: var(--text-muted);">Dung lượng: ${(f.size / (1024*1024)).toFixed(1)} MB</div>
            </div>
            <div style="display: flex; gap: 8px;">
              <a href="/outputs/${f.filename}" target="_blank" class="btn btn-secondary btn-sm">▶️ Xem Video</a>
              <a href="/api/download/${f.filename}" class="btn btn-primary btn-sm">📥 Tải MP4</a>
              ${f.srt_filename ? `<a href="/api/download/${f.srt_filename}" class="btn btn-secondary btn-sm">📝 Tải SRT Subtitle</a>` : ''}
            </div>
          </div>
        `).join('');
      }
    } catch (err) {
      console.error("Error loading outputs:", err);
    }
  }

});
