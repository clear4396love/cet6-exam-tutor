# Task Plan: B 站翻译课视频观看与 GLM-ASR 转写

## Goal
使用 watch 提取用户给定 B 站视频的本地画面与音频，以现成字幕或用户指定的智谱 GLM-ASR 获取带时间线的讲解证据，解释老师如何完成翻译题。

## Next Step
全部证据已核对；交付老师的方法、必要纠错和一版更稳妥的示范译文。

## Current Phase
Phase 5

## Phases

### Phase 1: Requirements & Discovery
- [x] Understand user intent
- [x] Identify constraints
- [x] Document in findings.md
- **Status:** complete

### Phase 2: Planning & Structure
- [x] Define local video / GLM-ASR split approach
- [x] Keep artifacts in watch disposable work dir; no product feature
- **Status:** complete

### Phase 3: Implementation
- [x] Install/verify base watch binaries
- [x] Extract video transcript/frames without other cloud ASR
- [x] If captions insufficient and key ready, segment audio into <=30 s chunks and call GLM-ASR
- [x] Analyze teacher's translation method with timestamps
- **Status:** complete

### Phase 4: Testing & Verification
- [x] Verify provenance of every claimed method
- [x] Read all report frames if generated
- [x] Record incomplete evidence accurately
- **Status:** complete

### Phase 5: Delivery
- [x] Review outputs
- [x] Deliver to user
- **Status:** complete

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Honor previous local viewing preference; do not use Gemini | User chose local processing earlier in this chat. |
| Replace WhisperX with GLM-ASR only for speech transcription | User explicitly changed ASR provider mid-setup. |
| No silent Groq/OpenAI fallback | User specified GLM-ASR. |

## Errors Encountered
| Error | Resolution |
|-------|------------|
| uv Python install returned missing minor-version link, despite extracting Python 3.12.13 | Direct python.exe works and will run setup/watch. |
| watch setup config unreadable in sandbox | Approved read-only escalation returned status. |
| winget/choco/scoop absent on host | Use a workspace-local yt-dlp venv plus an FFmpeg archive linked by ffmpeg.org. |
| FFmpeg essentials ZIP download progressed only ~1.7 MB after ~2 minutes | Stopped it; try the publisher's smaller 7z archive with libarchive tar extraction. |
| Access to escalated watch work directory denied inside sandbox | Use approved read-only escalation to inspect files, then image viewing tool for frames. |
| GLM-ASR first test could not open `chunk_000.mp3` because FFmpeg CSV lists relative names | Resolve CSV filenames against the chunk output directory, then retry. |
| GLM-ASR first request returned HTTP 429 after four retry attempts | Inspect the API error code/message safely without logging the key before deciding next action. |
| Parallel frame image reads briefly failed with a sandbox ACL helper error at frame 0122 | Exact file ACL was valid; retrying one image at a time succeeded. |
