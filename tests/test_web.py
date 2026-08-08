# This test is acceptance scenario T6: the web face answers the front page and
# the analysis endpoint on localhost, using a synthetic song and no network.

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
# Import the web face's Flask application.
from ai_music_blender.web import application
# Import the synthetic song maker from the engine tests.
from test_engine import make_test_song


# Define the test case for the web face.
class WebTests(unittest.TestCase):
    # T6, part one: the front page answers with the arc diagram page.
    def test_front_page(self):
        # Build a test client for the application.
        client = application.test_client()
        # Ask for the front page.
        answer = client.get("/")
        # Assert the page answered successfully.
        self.assertEqual(answer.status_code, 200)
        # Assert the page is the AI Music Blender page.
        self.assertIn(b"AI Music Blender", answer.data)

    # T6, part two: the analyze endpoint analyzes an uploaded song.
    def test_analyze_endpoint(self):
        # Build a test client for the application.
        client = application.test_client()
        # Create a temporary folder for the synthetic song.
        with tempfile.TemporaryDirectory() as folder:
            # Name the synthetic song.
            song = os.path.join(folder, "song.wav")
            # Synthesize the song.
            make_test_song(song, tempo=120.0, seconds=12.0)
            # Open the song for upload.
            with open(song, "rb") as song_file:
                # Post the song to the analyze endpoint.
                answer = client.post("/analyze", data={"file": (song_file, "song.wav")})
        # Assert the endpoint answered successfully.
        self.assertEqual(answer.status_code, 200)
        # Read the analysis record from the answer.
        record = answer.get_json()
        # Assert the record carries beats.
        self.assertGreater(len(record["beats"]), 0)
        # Assert the record carries an audio key for playback.
        self.assertIn("audio_key", record)


# Run the tests when this file is executed directly.
if __name__ == "__main__":
    # Hand control to the test runner.
    unittest.main()
