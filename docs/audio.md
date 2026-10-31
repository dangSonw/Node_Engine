# Sounds and independent playback voices

The editor's **Scene > Sounds…** dialog imports WAV, Ogg, MP3 and FLAC files into
`assets/audio`, and supports naming/removing library entries. Choose the imported
asset through a **Play Sound** node's Inspector. Library and graph changes share
Undo/Redo and project save/reopen. Preview validates encoded audio; unsupported or
corrupt files report an error while preserving the previous running scene.

Each playback has a scene-wide **Voice** name, such as `music` or `pickup`.
Playing the same voice again replaces/restarts it. Different voices can share one
sound asset and have independent position, volume, loop and pause state.
The node's Loop setting repeats the whole sound; embedded file loop points are
ignored so they cannot silently override one-shot playback or its duration.

## Nodes

Category 17 contains fourteen shared native definitions, IDs **17001–17014**.

| Node | Behavior |
|---|---|
| Play Sound | Start/restart a named voice with Sound, Loop and Volume |
| Stop Sound | Stop a known voice; its name remains available for queries/reuse |
| Pause / Resume Sound | Freeze/continue a voice's playback position |
| Is Sound Playing / Paused | Query state; an unknown valid name returns false |
| Set / Get Sound Volume | Per-voice linear gain between 0 and 1 |
| Get Sound Position | Current position in source seconds |
| Get Sound Duration | Registered asset duration in seconds |
| Sound Exists | Test the scene sound library for an asset ID |
| Stop All Sounds | Stop every voice, retaining named slots |
| Set / Get Master Volume | Linear gain applied to the complete mix, from 0 to 1 |

Control/getter nodes requiring a voice report an error for an unknown name.
Voice names require nonblank text with at most 128 UTF-8 bytes and no control
characters. Volume changes reject nonfinite/out-of-range values. Invalid Play
parameters are rejected before replacing the previous voice. Pausing/stopping
an already paused/stopped voice follows SDL_mixer's idempotent behavior.

## Native playback and reproducibility

All four executables use the same SDL_mixer code. The mixer produces 48 kHz
stereo float PCM at the end of each simulation step, after graph/event/timer
delivery. Fractional sample time carries into subsequent steps. Named voices
retain source positions and SDL_mixer handles resampling. Master gain is applied
to the mix, then final output is clamped to [-1, 1].

Interactive Preview and graphical games feed this PCM into an SDL audio device
stream. Editor Pause pauses both simulation and the output device; Resume
continues them. Stop/reload replaces the audio scene. A failed replacement keeps
the existing audio context and device. Queued output above 250 ms is cleared
after a device stall to bound latency; discarded device backlog does not rewind
the simulation. Audio is updated with the simulation, so a main-thread stall can
cause a gap. A device-free/headless run or graphical `--frames` replay generates
the same PCM without opening speakers.

`--audio-output path.wav` records IEEE float stereo WAV output. It is available
on both headless and graphical executables. `--project-root` resolves asset
paths for manual root builds; editor Build Game copies assets into the build
directory. For example:

```powershell
.\build\node_preview.exe --ir examples/audio_demo/generated/game.ir.json `
  --project-root examples/audio_demo --frames 42 `
  --input-replay examples/audio_demo/input-replay.json --audio-output audio.wav
```

The native snapshot preserves the asset definitions in `scene.audio_assets`
and exposes voice state/master volume under `audio`. Loading a scene starts
with no playing voices; this is not a running-game save/resume implementation.
Audio voices are scene-wide and have no entity activity or prefab ownership yet.

## Demo and evidence

Open `examples/audio_demo/project.json`. The generated music tone loops softly.
Space plays a short effect; P pauses music, R resumes, S stops every sound,
V lowers music volume, M mutes the master and L restarts/unmutes music.
Each action also changes the top-left sprite frame. The demo tones are generated
locally by `tools/create_audio_demo.py` and contain no third-party recordings.

`tests/test_audio.py` covers asset validation, actual editor authoring and all
fourteen native node functions. `tests/test_audio_runtime.py` measures PCM values,
voice replacement, sample timing, file rejection, native MP3 decoding and WAV
loop metadata with both one-shot and looping playback.
`tools/verify_audio_workflow.py` checks the actual editor/device path, failed
reload recovery, asynchronous Build Game and relocation. It compares state/WAV
bytes across headless and graphical Preview/export, with GPU comparisons for the
graphical pair. See [validation-report.md](validation-report.md) for results.

## Current boundaries

At most 1024 assets and 256 named voices per scene. Reuse voice names; stopped
slots are retained until scene reset. Files must resolve inside project assets,
with at most 64 MiB per encoded file and 256 MiB total. Accepted files must expose
a positive duration up to one hour, up to eight channels and 384 kHz. Encoded
files are cached in memory and decoded by SDL_mixer on demand. File loading is
synchronous. Captures are limited to 1 GiB; a single audio timestep is limited
to 60 seconds. Missing playback devices fail explicitly for interactive audio
projects; scenes without sound assets do not require an audio device.

WAV and MP3 are directly verified on Windows/WASAPI. Ogg and FLAC use the pinned
decoder but still need format-specific fixtures. These checks prove PCM and
device delivery; they do not certify acoustic output quality across hardware.
Pitch, fading/crossfade, buses, spatial audio/listeners, completion event nodes,
streaming, runtime file loading and device-change recovery remain pending.

## Runtime checkpoint groundwork

The internal version-2 `AudioCheckpoint` / `RestoreAudioCheckpoint` APIs rebuild
the mixer using an ordered journal of playback controls and exact mixing request
sizes. Repeated identical requests are run-length encoded. Elapsed sample totals
alone were insufficient: a combined-game test found different 44.1 kHz resampler
positions and future PCM when replay requests were split differently. Version 1
is rejected; this private format has no migration guarantee.

The state probe now passes 81 checks, including six fresh-process checkpoints,
389 continuation frames, 22.05/44.1/48/96 kHz WAV and MP3, and exact continuation
PCM. The combined-game probe passes 46 checks and seven matching capture pairs,
including capture continuation across a live context replacement. Invalid
records preserve the old mixer. See [persistence.md](persistence.md).

Recording is bounded to 65,536 journal entries, one hour of mixed output and
1,080,000 mixing calls; serialized history is limited to 16 MiB. Exceeding a
recording limit disables audio checkpoints until scene reset while playback
continues. Incoming records are checked before expensive replay. These are
defensive ceilings, not an acceptable restore-latency guarantee. Restore cost
still grows with history and active voice count; seekable converted assets or
another bounded-latency strategy are needed for unrestricted public game saves.

`TransferAudioOutput` hands the existing device and capture file to the prepared
candidate after staging succeeds, discarding queued pre-load output. The combined
probe passes with both the dummy driver and the machine's WASAPI output, checking
ownership, pause state and capture append. This verifies device delivery, not
acoustic quality. Host/editor/export integration remains unimplemented.
