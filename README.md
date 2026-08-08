<div align="center">

<img src="docs/images/banner_placeholder.png" alt="AIU Music Blender banner" width="600">

# AIU Music Blender

**The self-hosted infinite jukebox and mash-up machine.**

*Nothing to deprecate. Nothing to die.*

</div>

---

## What it is

AIU Music Blender resurrects and extends the beloved **Infinite Jukebox**: it analyzes a song **entirely on your own machine**, builds a graph of beats that sound alike, and plays the song **forever** by jumping between similar beats.

Then it goes further: **The_AI_Mashup_Machine** blends TWO songs (tempo-matched, key-matched, optionally stem-separated) into a mash-up — and the mash-up itself can play forever. Infinite mash-up radio.

Every hosted ancestor of this idea (Echo Nest, The Eternal Jukebox, eternalbox.dev, infiniby.com) died the same death: dependence on someone else's server or API. This project replaces the dead commercial analysis API with a **self-hosted machine-learning pipeline** (librosa: beats, MFCC timbre, chroma, key detection). No accounts. No API keys. No cloud. Unkillable.

## Three ways to run it

```bash
# 1. Command line
bin/ai-music-blender analyze  MySong.mp3
bin/ai-music-blender jukebox  MySong.mp3                 # play one song forever
bin/ai-music-blender jukebox  MySong.mp3 --seed 42       # a shareable, reproducible walk
bin/ai-music-blender mashup   SongA.mp3 SongB.mp3 -o blend.wav
bin/ai-music-blender jukebox  blend.wav                  # the mash-up plays forever

# 2. Localhost web page (the classic arc diagram, live)
bin/ai-music-blender web      # then open http://localhost:8765

# 3. Ubuntu desktop app (GTK)
bin/ai-music-blender gui
```

YouTube links work anywhere a file does (downloaded locally, analyzed locally).

## Install (Ubuntu)

```bash
sudo apt install ffmpeg rubberband-cli python3-gi gir1.2-gtk-3.0
pip3 install --user --break-system-packages -U yt-dlp   # pip, not apt: the apt version goes stale
pip3 install --user --break-system-packages librosa soundfile flask numpy
pip3 install --user --break-system-packages demucs   # optional: stem mash-ups
python3 -m unittest discover tests                    # verify: 8 tests, no network needed
```

## Documentation

- [CONSTITUTION.md](CONSTITUTION.md) — the rules of the repository
- [docs/User_Tutorial_v1.txt](docs/User_Tutorial_v1.txt) — for the newcomer user
- [docs/Developer_Tutorial_v1.txt](docs/Developer_Tutorial_v1.txt) — for the newcomer developer
- The DSPARCD Fileset — [Definition](docs/ai_music_blender_1_definition_v1.txt) · [Specification](docs/ai_music_blender_2_specification_v1.txt) · [Pseudocode](docs/ai_music_blender_3_pseudocode_v1.txt) · [Architecture](docs/ai_music_blender_4_architecture_v1.txt) · [Refinement](docs/ai_music_blender_5_refinement_v1.txt) · [Completion](docs/ai_music_blender_6_completion_v1.txt) · [Demonstration](docs/ai_music_blender_7_demonstration_v1.txt)
- [docs/AIU_Music_Blender_Vision_Document_v2.txt](docs/AIU_Music_Blender_Vision_Document_v2.txt) — the story and the plan

## Attribution

The jukebox core idea is vendored as a pristine reference snapshot from [EternalBox/EternalJukebox](https://github.com/EternalBox/EternalJukebox) (see `vendor/EternalJukebox`, license preserved) — the open-source rehosting of the original Infinite Jukebox by Paul Lamere at Echo Nest Labs. Thank you, and long may the walk continue.

## Legal

AIU Music Blender runs on your own audio files and your own local downloads, renders locally, and hosts and distributes nothing. Keep it that way.

---

<div align="center">

*The Jukebox is dead. Long live the AIU Music Blender.*

</div>
