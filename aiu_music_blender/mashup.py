# This module is THE_AI_MASHUP_MACHINE: it hides HOW TWO SONGS BECOME ONE behind
# a simple interface of two inputs, one rendered file, and one honest report.

# Import the operating system path tools.
import os
# Import the temporary-folder tools for intermediate audio files.
import tempfile
# Import the subprocess tools for the rubberband and demucs programs.
import subprocess
# Import the importable-module checker for optional Demucs.
import importlib.util
# Import the numerical array library.
import numpy
# Import the audio file reader and writer.
import soundfile
# Import the analysis pipeline and its sample rate.
from .analysis import analyze_song, SAMPLE_RATE, load_samples, PITCH_NAMES

# Define the largest tempo stretch considered comfortable (about eight percent).
COMFORTABLE_STRETCH = 0.08
# Define the largest key shift, in semitones, the engine will apply.
MAX_KEY_SHIFT = 2
# Define the gain of the vocal part in a stem mash-up.
VOCAL_GAIN = 0.95
# Define the gain of the instrumental part in a stem mash-up (lowered to duck under the vocal).
INSTRUMENTAL_GAIN = 0.65
# Define the gain of each song in a plain (no-stems) blend.
PLAIN_BLEND_GAIN = 0.55


# Define a helper that reports whether the Demucs stem separator is installed.
def demucs_available():
    # Report whether the demucs module can be found.
    return importlib.util.find_spec("demucs") is not None


# Define a helper that folds song B's tempo by halves and doubles to sit nearest song A's tempo.
def folded_tempo(tempo_a, tempo_b):
    # Try the tempo as-is, doubled, and halved.
    candidates = [tempo_b, tempo_b * 2.0, tempo_b / 2.0]
    # Return the candidate closest to song A's tempo.
    return min(candidates, key=lambda candidate: abs(candidate - tempo_a))


# Define a helper that measures the shortest distance between two keys, in semitones.
def key_shift_semitones(key_a, key_b):
    # Find the pitch class number of song A's tonic.
    tonic_a = PITCH_NAMES.index(key_a["tonic"])
    # Find the pitch class number of song B's tonic.
    tonic_b = PITCH_NAMES.index(key_b["tonic"])
    # Compute the raw difference from A to B.
    difference = (tonic_b - tonic_a) % 12
    # Fold the difference to the shortest direction around the circle.
    return difference - 12 if difference > 6 else difference


# Define the compatibility scorer: high when the stretch is small and the keys are neighbors.
def score_compatibility(record_a, record_b):
    # Fold song B's tempo to the octave nearest song A's tempo.
    tempo_b = folded_tempo(record_a["tempo"], record_b["tempo"])
    # Compute the fractional tempo stretch needed to meet in the middle.
    stretch = abs(record_a["tempo"] - tempo_b) / record_a["tempo"]
    # Compute the key shift needed to align the songs.
    shift = key_shift_semitones(record_a["key"], record_b["key"])
    # Score the tempo part: one when identical, falling toward zero as stretch grows.
    tempo_score = max(0.0, 1.0 - stretch / (2.0 * COMFORTABLE_STRETCH))
    # Score the key part: one when identical, falling with each semitone of shift.
    key_score = max(0.0, 1.0 - abs(shift) / 6.0)
    # Combine the parts into one score between zero and one.
    return {"score": round(0.6 * tempo_score + 0.4 * key_score, 3),
            "stretch": round(stretch, 4), "key_shift": shift}


# Define a helper that runs the rubberband program to stretch and shift a wav file.
def rubberband(input_wav, output_wav, time_ratio, semitones):
    # Build the rubberband command with the time ratio and pitch shift.
    command = ["rubberband", "-q", "--time", str(time_ratio), "--pitch", str(semitones),
               input_wav, output_wav]
    # Run the command, stopping on failure.
    subprocess.run(command, check=True, capture_output=True)


# Define a helper that separates a song into vocals and instrumental with Demucs.
def separate_stems(audio_path, work_folder):
    # Run Demucs in two-stem mode (vocals versus everything else) into the work folder.
    subprocess.run(["python3", "-m", "demucs", "--two-stems", "vocals",
                    "-o", work_folder, audio_path], check=True, capture_output=True)
    # Name the song's stem folder the way Demucs names it.
    song_name = os.path.splitext(os.path.basename(audio_path))[0]
    # Build the folder where Demucs put this song's stems.
    stem_folder = os.path.join(work_folder, "htdemucs", song_name)
    # Return the vocals path and the instrumental (no_vocals) path.
    return (os.path.join(stem_folder, "vocals.wav"),
            os.path.join(stem_folder, "no_vocals.wav"))


# Define a helper that loads a wav as mono samples at the engine sample rate.
def load_mono(path):
    # Load the file with the analysis loader, which resamples and folds to mono.
    samples, _ = load_samples(path)
    # Return the samples.
    return samples


# Define a helper that trims a song's samples to start at its first beat.
def trim_to_first_beat(samples, record, time_ratio):
    # Find the first beat time, scaled by any time stretch already applied.
    first_beat_time = record["beats"][0] * time_ratio if record["beats"] else 0.0
    # Convert the first beat time to a sample position.
    first_beat_sample = int(first_beat_time * SAMPLE_RATE)
    # Return the samples from the first beat onward.
    return samples[first_beat_sample:]


# Define the main entry: render a mash-up of two songs and return an honest report.
def render_mashup(path_a, path_b, output_path, use_stems=False,
                  vocals_a=None, vocals_b=None):
    # Each song's vocals can be kept or dropped independently:
    #   vocals_a True,  vocals_b True .... APPEND: SONG-2 (with vocals) joins onto the end of
    #                                      SONG-1 (with vocals), tempo- and key-conformed, making
    #                                      one big long song for the blender's beat graph;
    #   vocals_a True,  vocals_b False ... SONG-1's vocal over SONG-2's instrumental (classic);
    #   vocals_a False, vocals_b True .... SONG-2's vocal over SONG-1's instrumental;
    #   vocals_a False, vocals_b False ... APPEND, INSTRUMENTAL ONLY: the same one big long
    #                                      song, but built from the two instrumental stems,
    #                                      so the entire track carries no vocals at all.
    # Translate the older stems flag when the explicit choices were not given.
    if vocals_a is None:
        # Song A keeps its vocals in both older modes.
        vocals_a = True
    # Translate the second choice the same way.
    if vocals_b is None:
        # In older stems mode song B lost its vocals; in the plain mode it kept them.
        vocals_b = not use_stems
    # Analyze both songs.
    record_a = analyze_song(path_a)
    # Analyze the second song.
    record_b = analyze_song(path_b)
    # Score the pairing so the report can say why it worked or fought.
    compatibility = score_compatibility(record_a, record_b)
    # Fold song B's tempo to the octave nearest song A's tempo.
    tempo_b = folded_tempo(record_a["tempo"], record_b["tempo"])
    # Choose the common target tempo between the two, splitting the stretch.
    target_tempo = float(numpy.sqrt(record_a["tempo"] * tempo_b))
    # Compute each song's time ratio (output duration multiplier) to reach the target.
    ratio_a = record_a["tempo"] / target_tempo
    # Compute song B's time ratio.
    ratio_b = tempo_b / target_tempo
    # Compute the key shift, and apply it to song A only when it is small enough.
    shift = compatibility["key_shift"]
    # Decide the semitones to shift song A (zero when the keys are too far to force).
    semitones_a = shift if abs(shift) <= MAX_KEY_SHIFT else 0
    # Do all intermediate work in a temporary folder that cleans itself up.
    with tempfile.TemporaryDirectory() as work_folder:
        # Prepare the two source parts according to the per-song vocal choices.
        part_a_path, part_b_path, gain_a, gain_b = prepare_parts(
            path_a, path_b, work_folder, vocals_a, vocals_b)
        # Build the stretched-and-shifted version of part A.
        conformed_a = os.path.join(work_folder, "conformed_a.wav")
        # Stretch and shift part A with rubberband.
        rubberband(part_a_path, conformed_a, ratio_a, semitones_a)
        # Build the stretched version of part B.
        conformed_b = os.path.join(work_folder, "conformed_b.wav")
        # Stretch part B with rubberband, with no pitch shift.
        rubberband(part_b_path, conformed_b, ratio_b, 0)
        # When the two choices agree (both vocals, or both instrumental-only), append
        # song B onto the end of song A as one long song; otherwise overlay the parts.
        if vocals_a == vocals_b:
            # Join the two conformed parts end to end.
            mix = append_parts(conformed_a, conformed_b)
        # A single vocal overlays the other song's instrumental.
        else:
            # Load, align, and mix the two conformed parts.
            mix = mix_parts(conformed_a, conformed_b, record_a, record_b,
                            ratio_a, ratio_b, gain_a, gain_b)
    # Write the mix to the output audio file.
    soundfile.write(output_path, mix, SAMPLE_RATE)
    # Return the honest report of what was done.
    return {"compatibility": compatibility, "target_tempo": round(target_tempo, 2),
            "stretch_a": round(ratio_a, 4), "stretch_b": round(ratio_b, 4),
            "key_shift_applied": semitones_a, "stems": not (vocals_a and vocals_b),
            "mode": "append" if (vocals_a == vocals_b) else "mix",
            "vocals_a": vocals_a, "vocals_b": vocals_b, "output": output_path}


# Define the helper that prepares the two parts to be mixed, per the vocal choices,
# returning each part's path and its mixing gain.
def prepare_parts(path_a, path_b, work_folder, vocals_a, vocals_b):
    # When both songs keep their vocals, blend the two full songs (no separation needed).
    if vocals_a and vocals_b:
        # Prepare both whole songs.
        return (whole_song_wav(path_a, work_folder, "a"),
                whole_song_wav(path_b, work_folder, "b"),
                PLAIN_BLEND_GAIN, PLAIN_BLEND_GAIN)
    # Every other choice needs the stem separator; verify it is installed.
    if not demucs_available():
        # Raise the error the faces will show the user.
        raise RuntimeError("Vocal selection needs Demucs, which is not installed; "
                           "install with: pip3 install demucs")
    # Prepare part A: its vocal stem when chosen, otherwise its instrumental.
    part_a = song_part(path_a, work_folder, vocals_a)
    # Prepare part B the same way.
    part_b = song_part(path_b, work_folder, vocals_b)
    # A lone vocal rides on top; an instrumental sits ducked beneath a vocal.
    gain_a = VOCAL_GAIN if vocals_a else INSTRUMENTAL_GAIN
    # Choose part B's gain the same way, but two instrumentals blend evenly.
    gain_b = VOCAL_GAIN if vocals_b else (
        PLAIN_BLEND_GAIN if not vocals_a else INSTRUMENTAL_GAIN)
    # Two instrumentals also even out part A's gain.
    gain_a = PLAIN_BLEND_GAIN if (not vocals_a and not vocals_b) else gain_a
    # Return both parts with their gains.
    return part_a, part_b, gain_a, gain_b


# Define a helper that writes one whole song as a wav for rubberband.
def whole_song_wav(path, work_folder, tag):
    # Build the wav path for this song.
    whole = os.path.join(work_folder, "whole_" + tag + ".wav")
    # Write the song's samples as a wav.
    soundfile.write(whole, load_mono(path), SAMPLE_RATE)
    # Return the wav path.
    return whole


# Define a helper that returns one song's vocal stem or instrumental stem.
def song_part(path, work_folder, want_vocals):
    # Separate the song into its vocal and instrumental stems.
    vocals, instrumental = separate_stems(path, work_folder)
    # Return the stem this song was asked for.
    return vocals if want_vocals else instrumental


# Define the length of the seam crossfade, in seconds, when songs are appended.
APPEND_CROSSFADE_SECONDS = 0.5


# Define the helper that appends part B onto the end of part A with a smooth seam.
def append_parts(conformed_a, conformed_b):
    # Load the conformed part A.
    samples_a = load_mono(conformed_a)
    # Load the conformed part B.
    samples_b = load_mono(conformed_b)
    # Compute the seam crossfade length in samples.
    fade = int(APPEND_CROSSFADE_SECONDS * SAMPLE_RATE)
    # Fall back to a plain join if either song is too short to crossfade.
    if len(samples_a) <= fade or len(samples_b) <= fade:
        # Join the songs end to end with no seam blending.
        return numpy.concatenate([samples_a, samples_b])
    # Build the equal-power fade-out curve for the end of song A.
    fade_out = numpy.cos(numpy.linspace(0, numpy.pi / 2, fade)) ** 2
    # Build the matching fade-in curve for the start of song B.
    fade_in = 1.0 - fade_out
    # Blend song A's tail with song B's head into one seam.
    seam = samples_a[-fade:] * fade_out + samples_b[:fade] * fade_in
    # Join song A's body, the seam, and song B's remainder into one big long song.
    return numpy.concatenate([samples_a[:-fade], seam, samples_b[fade:]])


# Define the helper that aligns the two conformed parts at their first beats and mixes them.
def mix_parts(conformed_a, conformed_b, record_a, record_b, ratio_a, ratio_b, gain_a, gain_b):
    # Load the conformed part A.
    samples_a = load_mono(conformed_a)
    # Load the conformed part B.
    samples_b = load_mono(conformed_b)
    # Trim part A to start at its first beat (downbeat alignment).
    samples_a = trim_to_first_beat(samples_a, record_a, ratio_a)
    # Trim part B to start at its first beat.
    samples_b = trim_to_first_beat(samples_b, record_b, ratio_b)
    # Use the shorter part's length for the mix.
    length = min(len(samples_a), len(samples_b))
    # Mix the aligned parts at the chosen gains.
    mix = samples_a[:length] * gain_a + samples_b[:length] * gain_b
    # Keep the mix inside the legal sample range.
    peak = numpy.max(numpy.abs(mix)) + 1e-9
    # Normalize only if the mix would clip.
    return mix / peak if peak > 1.0 else mix
