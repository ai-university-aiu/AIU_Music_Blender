# This module hides HOW SIMILARITY IS MEASURED: it turns a song into an analysis
# record (tempo, key, beats, and a beat graph of jump edges), cached as JSON.

# Import the operating system path tools.
import os
# Import the JSON reader and writer.
import json
# Import the hashing tools for cache keys.
import hashlib
# Import the numerical array library.
import numpy
# Import the audio analysis library, the heart of the self-hosted pipeline.
import librosa
# Import the cache folder helper from our ingest module.
from .ingest import cache_directory

# Define the sample rate all analysis uses.
SAMPLE_RATE = 22050
# Define how many timbre coefficients (MFCCs) to compute per frame.
MFCC_COUNT = 13
# Define the weight of timbre distance in the similarity metric.
TIMBRE_WEIGHT = 0.7
# Define the weight of pitch (chroma) distance in the similarity metric.
CHROMA_WEIGHT = 0.3
# Define the penalty added when two beats sit at different positions in their bars.
BAR_POSITION_PENALTY = 0.6
# Define how many nearest neighbor beats on each side are excluded as trivial jumps.
NEIGHBOR_EXCLUSION = 3
# Define the most jump edges any one beat may keep.
MAX_EDGES_PER_BEAT = 6
# Define the percentile of all distances below which an edge is considered similar.
SIMILARITY_PERCENTILE = 10.0
# Define the weight of the one-beat-ahead context in the similarity distance.
CONTEXT_WEIGHT_ONE = 0.6
# Define the weight of the two-beats-ahead context in the similarity distance.
CONTEXT_WEIGHT_TWO = 0.3
# Define how strongly jumping on a singing beat is penalized, as a fraction of the median distance.
VOCAL_PENALTY_FRACTION = 0.8
# Define the bottom of the vocal frequency band, in Hertz.
VOCAL_LOW_HERTZ = 200.0
# Define the top of the vocal frequency band, in Hertz.
VOCAL_HIGH_HERTZ = 4000.0
# Define how many beats make one phrase (two 4-beat bars, the pop-music sentence unit).
PHRASE_BEATS = 8
# Define how strongly a vocal line bridging two phrases argues AGAINST cutting between them.
VOCAL_BRIDGE_WEIGHT = 1.0
# Define the most phrases one sentence may swallow before a boundary is forced.
MAX_PHRASES_PER_SENTENCE = 4
# Define the smallest vocal-bridge spread worth trusting: below this the track has no
# real singing (an instrumental), and standardizing would amplify noise into votes.
MIN_BRIDGE_SPREAD = 0.02
# Define the analysis record format version; a cache with an older version is re-analyzed.
ANALYSIS_VERSION = 4
# Define the Krumhansl major key profile (perceived strength of each pitch class in a major key).
MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
# Define the Krumhansl minor key profile.
MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
# Define the twelve pitch class names.
PITCH_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# Define the Camelot wheel number for each major key tonic, in pitch class order.
CAMELOT_MAJOR = ["8B", "3B", "10B", "5B", "12B", "7B", "2B", "9B", "4B", "11B", "6B", "1B"]
# Define the Camelot wheel number for each minor key tonic, in pitch class order.
CAMELOT_MINOR = ["5A", "12A", "7A", "2A", "9A", "4A", "11A", "6A", "1A", "8A", "3A", "10A"]


# Define a function that loads a song's samples at the analysis sample rate.
def load_samples(audio_path):
    # Load the audio as mono floating-point samples at our sample rate.
    samples, sample_rate = librosa.load(audio_path, sr=SAMPLE_RATE, mono=True)
    # Return the samples and the sample rate together.
    return samples, sample_rate


# Define a function that computes the cache key for an audio file's analysis.
def cache_key(audio_path):
    # Open the audio file for reading raw bytes.
    with open(audio_path, "rb") as audio_file:
        # Hash the entire file's bytes so any change re-triggers analysis.
        return hashlib.sha1(audio_file.read()).hexdigest()


# Define the main entry: analyze a song and return its analysis record, using the cache.
def analyze_song(audio_path, force=False):
    # Compute the cache key of this exact audio file.
    key = cache_key(audio_path)
    # Build the path where this song's analysis record is cached.
    record_path = os.path.join(cache_directory(), key + ".json")
    # If a cached record exists and force is off, reuse it when its version is current.
    if os.path.isfile(record_path) and not force:
        # Open the cached record file.
        with open(record_path, "r") as record_file:
            # Read the cached analysis record.
            cached = json.load(record_file)
        # Return the cached record only if it was made by this version of the pipeline.
        if cached.get("version") == ANALYSIS_VERSION:
            # Return the still-valid cached record.
            return cached
    # Load the song's samples.
    samples, sample_rate = load_samples(audio_path)
    # Detect the tempo and the beat frame positions with the beat tracker.
    tempo, beat_frames = librosa.beat.beat_track(y=samples, sr=sample_rate)
    # Convert the beat frames into beat times in seconds.
    beat_times = librosa.frames_to_time(beat_frames, sr=sample_rate).tolist()
    # Compute the per-beat timbre and pitch feature matrix.
    features = beat_feature_matrix(samples, sample_rate, beat_frames)
    # Measure how strongly the vocal band is singing on every beat.
    vocal = vocal_activity(samples, sample_rate, beat_frames)
    # Build the beat graph of jump edges from the features and the vocal activity.
    graph = build_beat_graph(features, vocal)
    # Group adjacent phrases into SENTENCES: phrases that sound continuous, or that a
    # vocal line bridges, stay together; boundaries fall only at genuine seams.
    sentences = detect_sentences(features, vocal, len(beat_times))
    # Estimate the song's key from its overall chroma.
    key_estimate = estimate_key(samples, sample_rate)
    # Package everything into one analysis record.
    record = {
        # Record the source file path.
        "source": os.path.abspath(audio_path),
        # Record the song duration in seconds.
        "duration": float(len(samples)) / sample_rate,
        # Record the detected tempo in beats per minute.
        "tempo": float(numpy.atleast_1d(tempo)[0]),
        # Record the estimated key.
        "key": key_estimate,
        # Record the beat times.
        "beats": beat_times,
        # Record the beat graph.
        "graph": graph,
        # Record the per-beat vocal activity (0.0 silent to 1.0 full singing).
        "vocal": [round(float(value), 3) for value in vocal],
        # Record the beat indices where sentences (grouped phrases) begin.
        "sentences": sentences,
        # Record the analysis record format version.
        "version": ANALYSIS_VERSION}
    # Open the cache file for writing.
    with open(record_path, "w") as record_file:
        # Write the analysis record as JSON.
        json.dump(record, record_file)
    # Return the fresh analysis record.
    return record


# Define a function that computes one feature vector per beat (timbre plus chroma).
def beat_feature_matrix(samples, sample_rate, beat_frames):
    # Compute the timbre coefficients for every analysis frame.
    mfcc = librosa.feature.mfcc(y=samples, sr=sample_rate, n_mfcc=MFCC_COUNT)
    # Compute the chroma (pitch class strength) for every analysis frame.
    chroma = librosa.feature.chroma_cqt(y=samples, sr=sample_rate)
    # Average the timbre frames BETWEEN each beat and the next (a beat is a span, not a point).
    beat_mfcc = librosa.util.sync(mfcc, beat_frames, aggregate=numpy.mean)
    # Average the chroma frames between each beat and the next.
    beat_chroma = librosa.util.sync(chroma, beat_frames, aggregate=numpy.mean)
    # Standardize each timbre dimension so no single coefficient dominates.
    beat_mfcc = standardize(beat_mfcc)
    # Standardize each chroma dimension the same way.
    beat_chroma = standardize(beat_chroma)
    # Stack timbre (weighted) on top of chroma (weighted) into one matrix, one column per beat.
    return numpy.vstack([beat_mfcc * TIMBRE_WEIGHT, beat_chroma * CHROMA_WEIGHT])


# Define a helper that standardizes each row of a matrix to zero mean and unit spread.
def standardize(matrix):
    # Compute each row's mean.
    row_means = matrix.mean(axis=1, keepdims=True)
    # Compute each row's spread, avoiding division by zero.
    row_spreads = matrix.std(axis=1, keepdims=True) + 1e-9
    # Return the standardized matrix.
    return (matrix - row_means) / row_spreads


# Define a function that measures per-beat vocal activity from the harmonic vocal band.
def vocal_activity(samples, sample_rate, beat_frames):
    # Compute the song's spectrogram.
    spectrogram = numpy.abs(librosa.stft(samples))
    # Split the spectrogram into its harmonic (sung and played notes) and percussive parts.
    harmonic, _ = librosa.decompose.hpss(spectrogram)
    # Find the frequency of every spectrogram row.
    frequencies = librosa.fft_frequencies(sr=sample_rate)
    # Build a mask selecting only the vocal band rows.
    vocal_band = (frequencies >= VOCAL_LOW_HERTZ) & (frequencies <= VOCAL_HIGH_HERTZ)
    # Sum the harmonic energy inside the vocal band, frame by frame.
    band_energy = (harmonic[vocal_band, :] ** 2).sum(axis=0, keepdims=True)
    # Average the band energy between each beat and the next.
    beat_energy = librosa.util.sync(band_energy, beat_frames, aggregate=numpy.mean)[0]
    # Find the loud reference level (the ninety-fifth percentile beat).
    reference = numpy.percentile(beat_energy, 95.0) + 1e-12
    # Scale to the range zero to one, clipping the loudest outliers.
    return numpy.clip(beat_energy / reference, 0.0, 1.0)


# Define the function that groups adjacent phrases into sentences: a boundary is kept
# only where the music genuinely changes AND no vocal line bridges across the cut,
# so jumping between sentences never feels like a thought chopped in half.
def detect_sentences(features, vocal, beat_count):
    # List every phrase's starting beat.
    starts = list(range(0, beat_count, PHRASE_BEATS))
    # A track with one phrase is one sentence.
    if len(starts) <= 1:
        # The single sentence starts at the beginning.
        return [0]
    # Average each phrase's beat features into one phrase profile.
    profiles = [features[:, s:min(s + PHRASE_BEATS, beat_count)].mean(axis=1) for s in starts]
    # Measure how much the music CHANGES across each phrase boundary.
    changes = numpy.array([float(numpy.linalg.norm(profiles[i + 1] - profiles[i]))
                           for i in range(len(starts) - 1)])
    # Measure how strongly a VOCAL bridges each boundary (singing across the cut).
    bridges = numpy.array([float(numpy.mean(vocal[max(0, starts[i + 1] - 2):starts[i + 1] + 2]))
                           for i in range(len(starts) - 1)])
    # Standardize the change measure so boundaries argue on equal terms.
    changes = (changes - changes.mean()) / (changes.std() + 1e-9)
    # Measure how much the vocal bridges actually vary across this track.
    bridge_spread = float(bridges.std())
    # On an INSTRUMENTAL the bridges barely vary, and standardizing them would turn
    # numerical noise into full-strength votes; trust musical change alone instead.
    if bridge_spread < MIN_BRIDGE_SPREAD:
        # Score boundaries by musical change only.
        scores = changes
    # With real singing present, let a vocal bridge argue against cutting.
    else:
        # Standardize the bridges the same way.
        bridges = (bridges - bridges.mean()) / bridge_spread
        # Score each boundary: high change argues FOR cutting, a vocal bridge AGAINST.
        scores = changes - VOCAL_BRIDGE_WEIGHT * bridges
    # Keep boundaries scoring above the middle of the pack.
    threshold = float(numpy.median(scores))
    # Every track's first sentence starts at the beginning.
    sentence_starts = [0]
    # Count phrases swallowed since the last boundary.
    phrases_since = 0
    # Walk every phrase boundary in order.
    for index in range(len(scores)):
        # One more phrase has joined the current sentence.
        phrases_since += 1
        # Keep this boundary if it is a genuine seam, or the sentence has grown too long.
        if scores[index] >= threshold or phrases_since >= MAX_PHRASES_PER_SENTENCE:
            # Start a new sentence at the next phrase.
            sentence_starts.append(int(starts[index + 1]))
            # Reset the growth counter.
            phrases_since = 0
    # Return the sentence starting beats.
    return sentence_starts


# Define a helper that blends each pair's distance with its following-beats context.
def context_distances(distance_table):
    # Copy the table so the original stays untouched.
    blended = distance_table.copy()
    # Blend in the one-beat-ahead distances (beat i+1 against beat j+1), shifted into place.
    blended[:-1, :-1] += CONTEXT_WEIGHT_ONE * distance_table[1:, 1:]
    # Blend in the two-beats-ahead distances the same way.
    blended[:-2, :-2] += CONTEXT_WEIGHT_TWO * distance_table[2:, 2:]
    # Make the final beats (which lack full context) simply repeat their own distance weight.
    blended[-1, :] *= (1.0 + CONTEXT_WEIGHT_ONE + CONTEXT_WEIGHT_TWO)
    # Do the same for the final column.
    blended[:, -1] *= (1.0 + CONTEXT_WEIGHT_ONE + CONTEXT_WEIGHT_TWO)
    # Return the context-aware distance table.
    return blended


# Define a helper that penalizes jumps landing on or leaving a strongly singing beat.
def vocal_penalty_table(distance_table, vocal):
    # Find the typical distance so the penalty is scaled to this song.
    typical = numpy.median(off_diagonal_values(distance_table))
    # Take each pair's stronger vocal activity (cutting EITHER end mid-word is bad).
    pair_vocal = numpy.maximum(vocal[:, None], vocal[None, :])
    # Return the scaled penalty table.
    return VOCAL_PENALTY_FRACTION * typical * pair_vocal


# Define a function that builds the beat graph: per beat, a list of [target, distance] jump edges.
def build_beat_graph(features, vocal):
    # Count the beats (the columns of the feature matrix).
    beat_count = features.shape[1]
    # Compute the full table of distances between every pair of beats.
    distance_table = pairwise_distances(features)
    # Blend each pair's distance with the distances of the beats that FOLLOW them,
    # so a jump prefers a landing whose continuation also matches (phrase-boundary behavior).
    distance_table = context_distances(distance_table)
    # Penalize jumps that would cut into or out of a strongly singing beat.
    distance_table = distance_table + vocal_penalty_table(distance_table, vocal)
    # Add the bar-position penalty to pairs at different positions within a four-beat bar.
    distance_table = distance_table + bar_penalty_table(beat_count)
    # Choose the similarity threshold as a low percentile of all off-diagonal distances.
    threshold = numpy.percentile(off_diagonal_values(distance_table), SIMILARITY_PERCENTILE)
    # Prepare the graph as one edge list per beat.
    graph = []
    # Walk every beat to collect its edges.
    for beat_index in range(beat_count):
        # Take this beat's distances to every other beat.
        distances = distance_table[beat_index]
        # Order the candidate targets from most to least similar.
        candidates = numpy.argsort(distances)
        # Prepare this beat's edge list.
        edges = []
        # Walk the candidates in order of similarity.
        for target in candidates:
            # Skip trivially-adjacent beats, which are inaudible non-jumps.
            if abs(int(target) - beat_index) <= NEIGHBOR_EXCLUSION:
                # Move on to the next candidate.
                continue
            # Stop when the candidate is no longer similar enough.
            if distances[target] > threshold:
                # Leave the candidate loop.
                break
            # Keep this candidate as a jump edge with its distance.
            edges.append([int(target), float(distances[target])])
            # Stop when this beat has enough edges.
            if len(edges) >= MAX_EDGES_PER_BEAT:
                # Leave the candidate loop.
                break
        # Add this beat's edges to the graph.
        graph.append(edges)
    # Return the finished beat graph.
    return graph


# Define a helper that computes the table of distances between all pairs of feature columns.
def pairwise_distances(features):
    # Compute the squared length of every beat's feature vector.
    squared_lengths = (features ** 2).sum(axis=0)
    # Use the algebraic identity to get all pairwise squared distances at once.
    squared = squared_lengths[:, None] + squared_lengths[None, :] - 2.0 * (features.T @ features)
    # Clip tiny negative values caused by floating-point noise.
    squared = numpy.maximum(squared, 0.0)
    # Return the plain (not squared) distances.
    return numpy.sqrt(squared)


# Define a helper that builds the bar-position penalty table for a number of beats.
def bar_penalty_table(beat_count):
    # Number every beat.
    beat_numbers = numpy.arange(beat_count)
    # Find each beat's position inside a four-beat bar.
    bar_positions = beat_numbers % 4
    # Mark every pair whose bar positions differ.
    mismatch = (bar_positions[:, None] != bar_positions[None, :]).astype(float)
    # Return the penalty for mismatched pairs.
    return mismatch * BAR_POSITION_PENALTY


# Define a helper that returns all values of a square table except the diagonal.
def off_diagonal_values(table):
    # Build a mask that is true everywhere except the diagonal.
    mask = ~numpy.eye(table.shape[0], dtype=bool)
    # Return the masked values.
    return table[mask]


# Define a function that estimates the musical key of the song from its overall chroma.
def estimate_key(samples, sample_rate):
    # Compute the chroma for the whole song.
    chroma = librosa.feature.chroma_cqt(y=samples, sr=sample_rate)
    # Average the chroma over time into one twelve-number profile.
    song_profile = chroma.mean(axis=1)
    # Start with no best correlation found.
    best = {"score": -2.0, "tonic": "C", "mode": "major", "camelot": "8B"}
    # Try every possible tonic pitch class.
    for tonic_index in range(12):
        # Rotate the song profile so this tonic comes first.
        rotated = numpy.roll(song_profile, -tonic_index)
        # Correlate the rotated profile with the major key profile.
        major_score = float(numpy.corrcoef(rotated, MAJOR_PROFILE)[0, 1])
        # Correlate the rotated profile with the minor key profile.
        minor_score = float(numpy.corrcoef(rotated, MINOR_PROFILE)[0, 1])
        # If major at this tonic beats the best so far, record it.
        if major_score > best["score"]:
            # Record the new best as a major key.
            best = {"score": major_score, "tonic": PITCH_NAMES[tonic_index],
                    "mode": "major", "camelot": CAMELOT_MAJOR[tonic_index]}
        # If minor at this tonic beats the best so far, record it.
        if minor_score > best["score"]:
            # Record the new best as a minor key.
            best = {"score": minor_score, "tonic": PITCH_NAMES[tonic_index],
                    "mode": "minor", "camelot": CAMELOT_MINOR[tonic_index]}
    # Return the key estimate without the internal score.
    return {"tonic": best["tonic"], "mode": best["mode"], "camelot": best["camelot"]}
