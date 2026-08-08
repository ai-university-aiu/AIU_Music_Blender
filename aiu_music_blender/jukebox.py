# This module is the CLASSIC INFINITE JUKEBOX, and it is sacred: it hides HOW THE
# WALK IS CHOSEN behind one small interface, and plays or renders a song forever.

# Import the random number tools for the walk.
import random
# Import the subprocess tools for live audition through ffplay.
import subprocess
# Import the numerical array library for sample math.
import numpy
# Import the audio file writer.
import soundfile
# Import the analysis pipeline and its sample rate.
from .analysis import analyze_song, SAMPLE_RATE, load_samples

# Define the crossfade length, in seconds, applied at every jump so jumps are click-free.
CROSSFADE_SECONDS = 0.012
# Define the default probability of jumping at a beat that has jump edges.
DEFAULT_CHAOS = 0.25


# Define a class that walks a beat graph forever.
class InfiniteWalk:
    # Define how a walk is created from an analysis record.
    def __init__(self, record, chaos=DEFAULT_CHAOS, seed=None):
        # Keep the analysis record.
        self.record = record
        # Keep the chaos (jump probability) setting.
        self.chaos = chaos
        # Create this walk's own random number generator, seeded if a seed was given.
        self.random_generator = random.Random(seed)
        # Start the walk at beat zero.
        self.current_beat = 0

    # Define the one interface of the walker: produce the next beat index.
    def next_beat(self):
        # Remember the beat we are about to leave.
        leaving_beat = self.current_beat
        # Look up the jump edges of the beat we are leaving.
        edges = self.record["graph"][leaving_beat]
        # Count the beats in the song.
        beat_count = len(self.record["beats"])
        # If we are at the final beat, jump back into the song so it never ends.
        if leaving_beat >= beat_count - 1:
            # Move to the most musical earlier landing: the best edge if any, else the middle.
            self.current_beat = edges[0][0] if edges else beat_count // 2
        # Otherwise, with probability chaos, take a jump edge instead of the next beat.
        elif edges and self.random_generator.random() < self.chaos:
            # Choose an edge weighted toward smaller (more similar) distances.
            self.current_beat = self.weighted_edge_choice(edges)
        # Otherwise, simply advance to the next beat in order.
        else:
            # Move one beat forward.
            self.current_beat = leaving_beat + 1
        # Report whether this step was a jump (not a simple advance).
        jumped = self.current_beat != leaving_beat + 1
        # Return the new beat index and whether we jumped to it.
        return self.current_beat, jumped

    # Define the helper that chooses a jump edge, favoring more similar targets.
    def weighted_edge_choice(self, edges):
        # Turn each edge's distance into a weight where smaller distance means larger weight.
        weights = [1.0 / (0.001 + distance) for _, distance in edges]
        # Draw one edge according to the weights.
        chosen = self.random_generator.choices(edges, weights=weights, k=1)[0]
        # Return the chosen edge's target beat.
        return chosen[0]


# Define a helper that slices a song's samples for one beat span.
def beat_samples(samples, record, beat_index):
    # Read the start time of this beat.
    start_time = record["beats"][beat_index]
    # Read the end time: the next beat, or the song's end for the final beat.
    beats = record["beats"]
    # Choose the end time for this beat span.
    end_time = beats[beat_index + 1] if beat_index + 1 < len(beats) else record["duration"]
    # Convert the times to sample positions.
    start_sample = int(start_time * SAMPLE_RATE)
    # Convert the end time to a sample position.
    end_sample = int(end_time * SAMPLE_RATE)
    # Return the samples of this beat span.
    return samples[start_sample:end_sample]


# Define a helper that appends one beat span to a chunk list, crossfading at jumps.
def append_with_crossfade(chunks, new_chunk, jumped):
    # Compute the crossfade length in samples.
    fade_length = int(CROSSFADE_SECONDS * SAMPLE_RATE)
    # If this beat follows a jump and both sides are long enough, blend the seam.
    if jumped and chunks and len(chunks[-1]) > fade_length and len(new_chunk) > fade_length:
        # Build the equal-power fade-out curve.
        fade_out = numpy.cos(numpy.linspace(0, numpy.pi / 2, fade_length)) ** 2
        # Build the matching fade-in curve.
        fade_in = 1.0 - fade_out
        # Blend the tail of the previous chunk with the head of the new chunk.
        chunks[-1][-fade_length:] = (chunks[-1][-fade_length:] * fade_out
                                     + new_chunk[:fade_length] * fade_in)
        # Append the rest of the new chunk after the blended seam.
        chunks.append(new_chunk[fade_length:].copy())
    # Otherwise, append the new chunk untouched.
    else:
        # Append the whole new chunk.
        chunks.append(new_chunk.copy())


# Define the function that renders a walk of a requested length to an audio file.
def render_walk(input_path, output_path, length_seconds, chaos=DEFAULT_CHAOS, seed=None):
    # Analyze the song (or fetch its cached analysis).
    record = analyze_song(input_path)
    # Load the song's samples for slicing.
    samples, _ = load_samples(input_path)
    # Create the walker.
    walk = InfiniteWalk(record, chaos=chaos, seed=seed)
    # Start the rendered chunk list with the first beat, unfaded.
    chunks = [beat_samples(samples, record, 0).copy()]
    # Track the rendered length in samples.
    rendered = len(chunks[0])
    # Compute the target length in samples.
    target = int(length_seconds * SAMPLE_RATE)
    # Keep walking until the render is long enough.
    while rendered < target:
        # Take the next step of the walk.
        beat_index, jumped = walk.next_beat()
        # Slice the samples of the visited beat.
        chunk = beat_samples(samples, record, beat_index)
        # Append the visited beat, crossfading if we jumped to it.
        append_with_crossfade(chunks, chunk, jumped)
        # Grow the rendered length.
        rendered += len(chunks[-1])
    # Join all chunks and trim to exactly the target length.
    rendered_samples = numpy.concatenate(chunks)[:target]
    # Write the rendered walk to the output audio file.
    soundfile.write(output_path, rendered_samples, SAMPLE_RATE)
    # Return the analysis record so callers can report on it.
    return record


# Define the function that auditions a walk live through the speakers with ffplay.
def play_walk(input_path, chaos=DEFAULT_CHAOS, seed=None, on_beat=None):
    # Analyze the song (or fetch its cached analysis).
    record = analyze_song(input_path)
    # Load the song's samples for slicing.
    samples, _ = load_samples(input_path)
    # Create the walker.
    walk = InfiniteWalk(record, chaos=chaos, seed=seed)
    # Start the ffplay program reading raw samples from a pipe, with no window.
    player = subprocess.Popen(
        ["ffplay", "-loglevel", "quiet", "-nodisp", "-f", "f32le",
         "-ar", str(SAMPLE_RATE), "-i", "pipe:0"],
        stdin=subprocess.PIPE)
    # Begin at beat zero without a jump.
    beat_index, jumped = 0, False
    # Guard the streaming loop so Ctrl+C stops cleanly.
    try:
        # Stream beats forever.
        while True:
            # Tell any listener (screen printer, test) which beat is playing.
            if on_beat is not None:
                # Call the listener with the beat index and whether we jumped.
                on_beat(beat_index, jumped)
            # Slice the samples of the current beat.
            chunk = beat_samples(samples, record, beat_index)
            # Send the beat's samples to the player.
            player.stdin.write(chunk.astype(numpy.float32).tobytes())
            # Take the next step of the walk.
            beat_index, jumped = walk.next_beat()
    # When the user presses Ctrl+C, fall through to cleanup.
    except (KeyboardInterrupt, BrokenPipeError):
        # Continue to cleanup.
        pass
    # Always close the player's input and stop it.
    finally:
        # Close the pipe to the player.
        player.stdin.close()
        # Stop the player program.
        player.terminate()
    # Return the analysis record so callers can report on it.
    return record
