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
    # If a cached record exists and force is off, reuse it.
    if os.path.isfile(record_path) and not force:
        # Open the cached record file.
        with open(record_path, "r") as record_file:
            # Return the cached analysis record.
            return json.load(record_file)
    # Load the song's samples.
    samples, sample_rate = load_samples(audio_path)
    # Detect the tempo and the beat frame positions with the beat tracker.
    tempo, beat_frames = librosa.beat.beat_track(y=samples, sr=sample_rate)
    # Convert the beat frames into beat times in seconds.
    beat_times = librosa.frames_to_time(beat_frames, sr=sample_rate).tolist()
    # Compute the per-beat timbre and pitch feature matrix.
    features = beat_feature_matrix(samples, sample_rate, beat_frames)
    # Build the beat graph of jump edges from the features.
    graph = build_beat_graph(features)
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
        # Record the analysis record format version.
        "version": 1}
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


# Define a function that builds the beat graph: per beat, a list of [target, distance] jump edges.
def build_beat_graph(features):
    # Count the beats (the columns of the feature matrix).
    beat_count = features.shape[1]
    # Compute the full table of distances between every pair of beats.
    distance_table = pairwise_distances(features)
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
