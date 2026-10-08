# Findings & Decisions

## Research Findings

- Watch 0.3.2 has Gemini/local engines and built-in Groq/OpenAI/WhisperX/none speech fallback; no GLM-ASR backend. For this request use watch with `--engine local --no-whisper` and run GLM-ASR separately only if audio transcription is needed.
- User chose balanced visual sampling (~100 frames), initially WhisperX for missing captions, then explicitly superseded this with Zhipu GLM-ASR.
- Official GLM-ASR-2512 endpoint: `POST https://open.bigmodel.cn/api/paas/v4/audio/transcriptions`, multipart file/model/stream, Bearer API key. Each file must be WAV/MP3, <=25 MB and <=30 seconds. Response includes `text`. Sources: https://docs.bigmodel.cn/cn/guide/models/sound-and-video/glm-asr-2512 and https://docs.bigmodel.cn/api-reference/%E6%A8%A1%E5%9E%8B-api/%E8%AF%AD%E9%9F%B3%E8%BD%AC%E6%96%87%E6%9C%AC
- No Zhipu API key was detected in process environment or existing parent project `.env`; user was asked to add `ZHIPUAI_API_KEY` there, without sharing the value in chat. Watch's private config was unreadable in sandbox but approved read-only check showed no Gemini or Groq/OpenAI key; it does not check Zhipu.
- Python 3.12.13 at `C:\Users\86195\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe` works. Watch setup currently lacks ffmpeg, ffprobe and yt-dlp and reports first_run=true, engine=local, detail=balanced.
- On Windows, watch's `setup.py --engine local` only prints `winget` installation hints for missing binaries; it does not install them automatically. Need install ffmpeg/yt-dlp through an available package manager, then rerun setup with `--backend none --detail balanced` to prohibit unintended ASR fallback.
- Installed yt-dlp 2026.8.19 into workspace-local `tmp/watch-env`, without altering the application dependencies. No winget/choco/scoop exists. The publisher's FFmpeg essentials ZIP is 109 MB and downloaded too slowly; its 7z archive is 34 MB and has SHA-256 `4705843ccaaf54257c16ad90f3e952ece33c17df964ecf7bfdbb0f49c7171077`. The incomplete ZIP is left untouched in `tmp/watch-deps-20261002`.
- GitHub mirror `GyanD/codexffmpeg` delivered the same 7z quickly. Local SHA-256 matched the publisher's checksum exactly. Windows bsdtar can read the archive; all 49 entries stay under one expected directory and were extracted into `tmp/watch-deps-20261002`. ffmpeg, ffprobe and yt-dlp executables now exist in workspace-local temporary paths.
- `watch.py --engine local --no-whisper --detail balanced` successfully downloaded Bilibili BV1br421E7D6. Title: `【dy/邹老师】四六级翻译 养老 真题（5.5） 时长感人的一篇，快来感受一下真题的压迫感！！`; duration 58:44 (3523.9s), media 320×640, 100 frames selected from 158 candidates. No captions; watch fallback deliberately disabled, so no speech transcript yet. Work dir: `tmp/watch-runs/watch-vpq3hloh`; local video at its `download/run-h73qgcf3/video.mp4`.
- At 30 seconds maximum per GLM-ASR call, full 3523.9s track needs at least 118 requests (possibly more if overlap). This is a paid cloud upload to Zhipu, not local transcription. User must configure key before calls.
- User configured `ZHIPUAI_API_KEY` in the parent `.env`; presence was verified without printing the value. FFmpeg produced 122 MP3 segments of ~29 seconds each. No segment has been transcribed: first API request returned HTTP 429 with business code `1113`, and subsequent diagnostic request gave the same code. Official error table defines `1113` as account in arrears / recharge required, distinct from rate limit (`1302`): https://docs.bigmodel.cn/cn/api/api-code . Stop API calls pending user direction or new usable account balance.
- First four sampled frames show the original elderly-care passage and the teacher beginning to write `In recent years` under the source. This verifies the video is the same topic as the user's earlier notes, but the voice explanation remains unverified.
- Frames 0007-0018 show the teacher marking Chinese source phrases before writing, annotating `keep V-ing` and `be + V-ing`, then drafting `In recent years, the elderly population in China keeps growing. The Chinese government is taking a variety of measures...`. Visual evidence supports a workflow of source marking, grammar/tense choice, then English sentence construction.
- Frames 0020-0031 show the source phrase `推进养老服务体系建设，使老年人晚年生活健康幸福` underlined/annotated and the English continuation `to spur the construction of old-age care service system and make the elderly ... happy and healthy life`. This visually confirms word-order restructuring and converting the Chinese comma into an English purpose/parallel construction; precise spoken rationale is unavailable.
- Frames 0033-0044 show the next sentence being marked then drafted in passive voice: `Various old-age service institutions are built all over the country...`. This supports teacher's method of finding an English subject and using passive for the Chinese impersonal `全国兴建了...` construction.
- Frames 0045-0069 show source annotations over `颁布标准、加强监管` and the English `the government has issued a train of standards, strengthening the supervision of these institutions`. Visual sequence supports joining a second action via an `-ing` phrase. The phrase `a train of standards` appears in the teacher's draft, but naturalness needs separate evaluation rather than automatic adoption.
- GLM-ASR completed all 122 chunks, 20,391 Chinese-character-equivalent text characters from 00:00 to 58:44; no empty chunk. Teacher explicitly teaches at ~05:19 purpose relation, ~08:13 noun-of-noun restructuring, ~14:01 long sentence segmentation, ~15:57 passive voice for absent subject, ~25:37 nonfinite -ing/-ed, ~32:23 plain-Chinese paraphrase, ~33:21 subject-verb adjacency, ~37:42 selective omission, ~55:06 等 / other plural, ~56:04 ensure-that and purpose. Sales pitch interrupts ~29:00-31:25 and ~39:38-46:53; not substantive translation teaching.
- Frames 0071-0082 remain on the annotated first page while the teacher points back to the printed passage and drafted standards/supervision sentence. They do not show a new translated sentence.
- Frames 0083-0088 add `Many cities have set up community canteens, offering ... meals` to the first page. Frames 0090-0095 switch to a tablet displaying student testimonials/results during the sales segment, consistent with the GLM transcript; do not treat that segment as translation method evidence.
- Frames 0096-0107 briefly show the completed first-page draft (`... affordable meals for their convenience`), a printed course promotion sheet, then the teacher placing a blank lined page to continue the last sentences. The promotional sheet is not instruction for this task.
- Frames 0109-0120 show the second page beginning `Elderly people with mobility difficulties can also enjoy...`; the teacher first writes `of` after `people`, then annotates/replaces it with `with`, matching the transcript's more natural `people with mobility difficulties` recommendation. This is a concrete self-correction in the lesson.
- Frames 0122-0133 keep the same unfinished second-page sentence on screen while the teacher gestures/talks. GLM transcript places these in the long sales/cross-subject discussion; no further English written text appears in these sampled frames.
- Frames 0134-0145 resume the answer: `Elderly people with mobility difficulties can also enjoy food delivery service. Meanwhile, China is also actively exploring home care...`. The teacher's note near `also` and `actively` corresponds to the transcript explanation at ~53:39 that adverb placement/form matters.
- Frames 0147-0158 show the second-page ending developing through `... home care, community care and other old-age support modes, in order to ensure that all the elderly...`; the final frame stops before the full last predicate, but the GLM transcript covers it through 58:44. All 100 selected `watch` frames have now been viewed.
- Important teacher overstatements/corrections: at ~01:56, his present-perfect explanation says `have + kept`, but singular `population` takes `has`; `In recent years, China's elderly population has continued to grow` is safer. At ~26:35, he says two verbs can only be separated by a comma and cannot use `and`; this is false—`issued ... and strengthened ...` is grammatical. At ~21:16, he treats Chinese `了` without a specific past date as a general present-perfect signal; context still determines tense. At ~08:13, `of` for long nouns is a heuristic, not universal. At ~23:00, his `a train of standards` is less natural than `a series of standards` or `a set of standards`. At ~37:42/~50:16, selective omission is useful only when meaning is recoverable; `meal delivery to their homes` keeps `上门` explicit if precision matters. Score guarantees and “100%必考” claims are marketing, not verified rules.

## Requirements
-

## Research Findings
-

## Technical Decisions
| Decision | Rationale |
|----------|-----------|

## Issues Encountered
| Issue | Resolution |
|-------|------------|

## Resources
-
