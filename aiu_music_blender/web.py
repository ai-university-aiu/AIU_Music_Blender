# This module is the LOCALHOST WEB FACE: a Flask server, bound to localhost only,
# that serves the arc-diagram page, analysis records, and audio - deciding nothing.

# Import the operating system path tools.
import os
# Import the subprocess tools for the ffmpeg converter.
import subprocess
# Import the Flask web framework pieces we use.
from flask import Flask, request, jsonify, send_file, render_template
# Import the engine's cache folder helper.
from .ingest import cache_directory, local_audio_path
# Import the engine's analysis function and cache key.
from .analysis import analyze_song, cache_key
# Import the engine's mash-up renderer.
from .mashup import render_mashup, render_instrumental

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


# Define a helper that resolves one song from an upload or a link, whichever was sent.
def resolve_song(file_key, form_key):
    # If a file was uploaded under this key, save it into the cache folder.
    if file_key in request.files:
        # Take the uploaded file.
        upload = request.files[file_key]
        # Build a safe path in the cache folder for the upload.
        saved_path = os.path.join(cache_directory(), "upload_" + os.path.basename(upload.filename))
        # Save the upload.
        upload.save(saved_path)
        # Use the saved upload.
        return saved_path
    # Otherwise, resolve the pasted link or path.
    return local_audio_path(request.form[form_key])


# Define the route that renders a mash-up of two songs (each an upload or a link).
@application.route("/mashup", methods=["POST"])
def mashup_route():
    # Resolve the first song from its file or link.
    path_a = resolve_song("file_a", "input_a")
    # Resolve the second song from its file or link.
    path_b = resolve_song("file_b", "input_b")
    # Build the output path in the cache folder.
    output_path = os.path.join(cache_directory(), "web_mashup.wav")
    # Read each song's independent vocal choice from its checkbox.
    vocals_a = request.form.get("vocals_a") == "on"
    # Read the second song's vocal choice.
    vocals_b = request.form.get("vocals_b") == "on"
    # Render the mash-up with the chosen vocals.
    report = render_mashup(path_a, path_b, output_path, vocals_a=vocals_a, vocals_b=vocals_b)
    # Analyze the rendered mash-up so it can play in the infinite engine immediately.
    record = analyze_song(output_path)
    # Remember the mash-up's audio for the audio route.
    key = cache_key(output_path)
    # Store the mapping.
    AUDIO_PATHS[key] = output_path
    # Return the report and the playable record together.
    return jsonify({"report": report, "record": dict(record, audio_key=key)})


# Define the route that strips all vocals from one song and returns its playable record.
@application.route("/instrumental", methods=["POST"])
def instrumental_route():
    # Resolve the input (path or YouTube link) to a local file.
    path = local_audio_path(request.form["input"])
    # Name the cached instrumental by the source song's cache key.
    output_path = os.path.join(cache_directory(), "instrumental_" + cache_key(path) + ".wav")
    # Strip the vocals only if this song's instrumental is not already cached.
    if not os.path.isfile(output_path):
        # Render the vocal-free instrumental.
        render_instrumental(path, output_path)
    # Analyze the instrumental so it can play in the infinite engine.
    record = analyze_song(output_path)
    # Remember the instrumental's audio for the audio route.
    key = cache_key(output_path)
    # Store the mapping.
    AUDIO_PATHS[key] = output_path
    # Return the playable record.
    return jsonify(dict(record, audio_key=key))


# Define the route that converts a loaded track to wav or mp3 and sends it as a download.
@application.route("/export/<key>/<file_format>")
def export_route(key, file_format):
    # Allow only the two supported formats.
    if file_format not in ("wav", "mp3"):
        # Refuse anything else.
        return ("Unsupported format", 400)
    # Look up the audio path for this key.
    source = AUDIO_PATHS.get(key)
    # Refuse unknown keys.
    if source is None:
        # Answer with a not-found error.
        return ("Unknown audio key", 404)
    # Build the converted file's cache path.
    converted = os.path.join(cache_directory(), "export_" + key + "." + file_format)
    # Convert with ffmpeg only if this exact export is not already cached.
    if not os.path.isfile(converted):
        # Run ffmpeg quietly to convert the source to the requested format.
        subprocess.run(["ffmpeg", "-loglevel", "quiet", "-y", "-i", source, converted],
                       check=True)
    # Send the file as a browser download with a friendly name.
    return send_file(converted, as_attachment=True,
                     download_name="aiu_music_blender_" + key[:8] + "." + file_format)


# Define the function that starts the localhost-only server.
def run_web(port=8765):
    # Announce the address on the console.
    print("AIU Music Blender web page: http://localhost:%d  (Ctrl+C to stop)" % port)
    # Run the server, bound to localhost only, per the Ninth Commandment.
    application.run(host="127.0.0.1", port=port, debug=False)
