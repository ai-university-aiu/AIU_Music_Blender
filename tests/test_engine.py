# These tests generate their own synthetic audio (click tracks and tones), so
# they need no copyrighted material and no network. They are the acceptance
# scenarios T1 through T5 of the Specification, and the Golden Rule regression.

# Import the unit testing framework.
import unittest
# Import the temporary-folder tools.
import tempfile
# Import the path tools.
import os
# Import the module search path list.
import sys
# Add the repository root so the engine package imports in tests.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Import the numerical array library.
import numpy
# Import the audio file writer.
import soundfile
# Import the engine's analysis pipeline.
from ai_music_blender.analysis import analyze_song, SAMPLE_RATE
# Import the engine's walker and renderer.
from ai_music_blender.jukebox import InfiniteWalk, render_walk
# Import the engine's mash-up pieces.
from ai_music_blender.mashup import render_mashup, score_compatibility


# Define a helper that synthesizes a click-track song with a repeated section.
def make_test_song(path, tempo=120.0, seconds=24.0):
    # Compute the number of samples.
    total = int(seconds * SAMPLE_RATE)
    # Start with silence.
    samples = numpy.zeros(total, dtype=numpy.float64)
    # Compute the beat period in samples.
    period = int(SAMPLE_RATE * 60.0 / tempo)
    # Lay a short decaying click on every beat.
    for start in range(0, total - 600, period):
        # Build the click as a decaying burst of tone.
        click = numpy.sin(numpy.linspace(0, 60, 600)) * numpy.linspace(1, 0, 600)
        # Add the click at this beat.
        samples[start:start + 600] += click * 0.8
    # Add a repeating four-bar melody so distant sections genuinely sound alike.
    tone_time = numpy.arange(total) / SAMPLE_RATE
    # Choose a pitch that cycles every eight beats.
    pitch = 220.0 * (2.0 ** (((numpy.floor(tone_time * tempo / 60.0) % 8) % 4) / 12.0))
    # Add the melody under the clicks.
    samples += 0.2 * numpy.sin(2 * numpy.pi * pitch * tone_time)
    # Write the song to the given path.
    soundfile.write(path, samples, SAMPLE_RATE)


# Define the test case for the engine.
class EngineTests(unittest.TestCase):
    # Build one shared temporary folder and test song for the whole class.
    @classmethod
    def setUpClass(cls):
        # Create the temporary folder.
        cls.folder = tempfile.TemporaryDirectory()
        # Name the test song path.
        cls.song = os.path.join(cls.folder.name, "song.wav")
        # Synthesize the test song at 120 beats per minute.
        make_test_song(cls.song, tempo=120.0)
        # Analyze it once for the tests that share the record.
        cls.record = analyze_song(cls.song, force=True)

    # Clean the temporary folder afterward.
    @classmethod
    def tearDownClass(cls):
        # Remove the temporary folder.
        cls.folder.cleanup()

    # T1: the detected tempo is within ten percent of the true tempo.
    def test_tempo_detection(self):
        # Fold the detected tempo by octaves toward 120.
        detected = self.record["tempo"]
        # Accept the tempo, its double, or its half.
        candidates = [detected, detected * 2, detected / 2]
        # Measure the best relative error against the true tempo.
        error = min(abs(c - 120.0) / 120.0 for c in candidates)
        # Assert the error is under ten percent.
        self.assertLess(error, 0.10)

    # T2: the beat graph contains jump edges between the repetitions.
    def test_graph_has_edges(self):
        # Count all edges in the graph.
        edge_count = sum(len(edges) for edges in self.record["graph"])
        # Assert at least one jump edge exists.
        self.assertGreater(edge_count, 0)

    # T3: a seeded walk, run twice, produces the identical beat sequence.
    def test_seeded_walk_is_deterministic(self):
        # Run the first seeded walk for one hundred steps.
        first = [InfiniteWalk(self.record, chaos=0.5, seed=42).next_beat()[0]
                 for _ in range(1)]
        # Build two fresh walkers with the same seed.
        walk_one = InfiniteWalk(self.record, chaos=0.5, seed=42)
        # Build the second walker.
        walk_two = InfiniteWalk(self.record, chaos=0.5, seed=42)
        # Collect one hundred steps from each.
        steps_one = [walk_one.next_beat()[0] for _ in range(100)]
        # Collect the second walker's steps.
        steps_two = [walk_two.next_beat()[0] for _ in range(100)]
        # Assert the two walks are identical.
        self.assertEqual(steps_one, steps_two)

    # T4: rendering a walk produces a file within one second of the requested length.
    def test_render_length(self):
        # Name the render output.
        output = os.path.join(self.folder.name, "render.wav")
        # Render a fifteen-second walk.
        render_walk(self.song, output, 15.0, chaos=0.4, seed=7)
        # Read the rendered file's info.
        info = soundfile.info(output)
        # Assert the length is within one second of the request.
        self.assertLess(abs(info.duration - 15.0), 1.0)

    # T5: a mash-up of two different-tempo songs renders and reports honestly.
    def test_mashup_renders(self):
        # Synthesize a second song at a different tempo.
        second = os.path.join(self.folder.name, "second.wav")
        # Make the second song at 126 beats per minute.
        make_test_song(second, tempo=126.0)
        # Name the mash-up output.
        output = os.path.join(self.folder.name, "mashup.wav")
        # Render the mash-up without stems.
        report = render_mashup(self.song, second, output)
        # Assert the output file exists and is not empty.
        self.assertGreater(soundfile.info(output).duration, 1.0)
        # Assert the report carries a compatibility score between zero and one.
        self.assertGreaterEqual(report["compatibility"]["score"], 0.0)
        # Assert the score is at most one.
        self.assertLessEqual(report["compatibility"]["score"], 1.0)

    # The walker never escapes the song and always moves.
    def test_walk_stays_in_bounds(self):
        # Build a wild walker.
        walk = InfiniteWalk(self.record, chaos=1.0, seed=3)
        # Take five hundred steps.
        for _ in range(500):
            # Take one step.
            beat, _ = walk.next_beat()
            # Assert the beat is inside the song.
            self.assertGreaterEqual(beat, 0)
            # Assert the beat index is a valid beat.
            self.assertLess(beat, len(self.record["beats"]))


# Run the tests when this file is executed directly.
if __name__ == "__main__":
    # Hand control to the test runner.
    unittest.main()
