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
def render_mashup(path_a, path_b, output_path, use_stems=False):
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
        # Prepare the two source parts (whole songs, or stems when requested).
        part_a_path, part_b_path = prepare_parts(path_a, path_b, work_folder, use_stems)
        # Build the stretched-and-shifted version of part A.
        conformed_a = os.path.join(work_folder, "conformed_a.wav")
        # Stretch and shift part A with rubberband.
        rubberband(part_a_path, conformed_a, ratio_a, semitones_a)
        # Build the stretched version of part B.
        conformed_b = os.path.join(work_folder, "conformed_b.wav")
        # Stretch part B with rubberband, with no pitch shift.
        rubberband(part_b_path, conformed_b, ratio_b, 0)
        # Load, align, and mix the two conformed parts.
        mix = mix_parts(conformed_a, conformed_b, record_a, record_b, ratio_a, ratio_b, use_stems)
    # Write the mix to the output audio file.
    soundfile.write(output_path, mix, SAMPLE_RATE)
    # Return the honest report of what was done.
    return {"compatibility": compatibility, "target_tempo": round(target_tempo, 2),
            "stretch_a": round(ratio_a, 4), "stretch_b": round(ratio_b, 4),
            "key_shift_applied": semitones_a, "stems": use_stems, "output": output_path}


# Define the helper that prepares the two parts to be mixed (stems or whole songs).
def prepare_parts(path_a, path_b, work_folder, use_stems):
    # When stems are requested, verify the separator is installed.
    if use_stems:
        # Stop with a clear message if Demucs is missing.
        if not demucs_available():
            # Raise the error the faces will show the user.
            raise RuntimeError("Stem mash-up requested but Demucs is not installed; "
                               "install with: pip3 install demucs")
        # Separate song A and keep its vocals.
        vocals_a, _ = separate_stems(path_a, work_folder)
        # Separate song B and keep its instrumental.
        _, instrumental_b = separate_stems(path_b, work_folder)
        # Return the vocal part of A and the instrumental part of B.
        return vocals_a, instrumental_b
    # Without stems, convert both whole songs to wav files for rubberband.
    whole_a = os.path.join(work_folder, "whole_a.wav")
    # Write song A's samples as a wav.
    soundfile.write(whole_a, load_mono(path_a), SAMPLE_RATE)
    # Build the wav path for song B.
    whole_b = os.path.join(work_folder, "whole_b.wav")
    # Write song B's samples as a wav.
    soundfile.write(whole_b, load_mono(path_b), SAMPLE_RATE)
    # Return the two whole-song parts.
    return whole_a, whole_b


# Define the helper that aligns the two conformed parts at their first beats and mixes them.
def mix_parts(conformed_a, conformed_b, record_a, record_b, ratio_a, ratio_b, use_stems):
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
    # Choose the gains: ducked stems, or an even blend of whole songs.
    gain_a = VOCAL_GAIN if use_stems else PLAIN_BLEND_GAIN
    # Choose the gain for part B.
    gain_b = INSTRUMENTAL_GAIN if use_stems else PLAIN_BLEND_GAIN
    # Mix the aligned parts at the chosen gains.
    mix = samples_a[:length] * gain_a + samples_b[:length] * gain_b
    # Keep the mix inside the legal sample range.
    peak = numpy.max(numpy.abs(mix)) + 1e-9
    # Normalize only if the mix would clip.
    return mix / peak if peak > 1.0 else mix
