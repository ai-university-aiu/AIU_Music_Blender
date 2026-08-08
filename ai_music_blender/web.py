# This module is the LOCALHOST WEB FACE: a Flask server, bound to localhost only,
# that serves the arc-diagram page, analysis records, and audio - deciding nothing.

# Import the operating system path tools.
import os
# Import the Flask web framework pieces we use.
from flask import Flask, request, jsonify, send_file, render_template
# Import the engine's cache folder helper.
from .ingest import cache_directory, local_audio_path
# Import the engine's analysis function and cache key.
from .analysis import analyze_song, cache_key
# Import the engine's mash-up renderer.
from .mashup import render_mashup

# Create the Flask application, pointing at our templates folder.
application = Flask(__name__, template_folder="templates")
# Keep a map from analysis cache keys to their audio file paths, for audio serving.
AUDIO_PATHS = {}


# Define the route for the front page.
@application.route("/")
def front_page():
    # Render the arc-diagram page.
    return render_template("index.html")


# Define the route that analyzes a song given its local path or an upload.
@application.route("/analyze", methods=["POST"])
def analyze_route():
    # If a file was uploaded, save it into the cache folder first.
    if "file" in request.files:
        # Take the uploaded file.
        upload = request.files["file"]
        # Build a safe path in the cache folder for the upload.
        saved_path = os.path.join(cache_directory(), "upload_" + os.path.basename(upload.filename))
        # Save the upload.
        upload.save(saved_path)
        # Use the saved upload as the input path.
        path = saved_path
    # Otherwise, expect a local path or link in the form data.
    else:
        # Resolve the given input (path or YouTube link) to a local file.
        path = local_audio_path(request.form["input"])
    # Analyze the song (or fetch its cached analysis).
    record = analyze_song(path)
    # Remember where this record's audio lives, keyed by the record's cache key.
    key = cache_key(path)
    # Store the mapping for the audio route.
    AUDIO_PATHS[key] = path
    # Attach the key so the page can fetch the audio.
    record = dict(record, audio_key=key)
    # Return the analysis record as JSON.
    return jsonify(record)


# Define the route that serves a song's audio bytes by its key.
@application.route("/audio/<key>")
def audio_route(key):
    # Look up the audio path for this key.
    path = AUDIO_PATHS.get(key)
    # Refuse unknown keys.
    if path is None:
        # Answer with a not-found error.
        return ("Unknown audio key", 404)
    # Send the audio file to the browser.
    return send_file(path)


# Define the route that renders a mash-up of two local paths.
@application.route("/mashup", methods=["POST"])
def mashup_route():
    # Resolve the first input to a local path.
    path_a = local_audio_path(request.form["input_a"])
    # Resolve the second input to a local path.
    path_b = local_audio_path(request.form["input_b"])
    # Build the output path in the cache folder.
    output_path = os.path.join(cache_directory(), "web_mashup.wav")
    # Render the mash-up without stems (the web face keeps version one simple).
    report = render_mashup(path_a, path_b, output_path)
    # Analyze the rendered mash-up so it can play in the infinite engine immediately.
    record = analyze_song(output_path)
    # Remember the mash-up's audio for the audio route.
    key = cache_key(output_path)
    # Store the mapping.
    AUDIO_PATHS[key] = output_path
    # Return the report and the playable record together.
    return jsonify({"report": report, "record": dict(record, audio_key=key)})


# Define the function that starts the localhost-only server.
def run_web(port=8765):
    # Announce the address on the console.
    print("AI Music Blender web page: http://localhost:%d  (Ctrl+C to stop)" % port)
    # Run the server, bound to localhost only, per the Ninth Commandment.
    application.run(host="127.0.0.1", port=port, debug=False)
