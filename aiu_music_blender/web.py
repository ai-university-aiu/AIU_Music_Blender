# This module is the LOCALHOST WEB FACE: a Flask server, bound to localhost only,
# that serves the arc-diagram page, analysis records, and audio - deciding nothing.

# Import the operating system path tools.
import os
# Import the subprocess tools for the ffmpeg converter.
import subprocess
# Import the numerical array library for mixing stems.
import numpy
# Import the audio file writer for the bounced mix.
import soundfile
# Import the Flask web framework pieces we use.
from flask import Flask, request, jsonify, send_file, render_template
# Import the engine's cache folder helper.
from .ingest import cache_directory, local_audio_path
# Import the engine's analysis function and cache key.
from .analysis import analyze_song, cache_key, load_samples, SAMPLE_RATE
# Import the engine's mash-up renderer.
from .mashup import render_mashup, render_instrumental, render_all_stems, STEM_NAMES

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
    # Read each song's already-an-instrumental declaration (skips vocal removal for it).
    instrumental_a = request.form.get("instrumental_a") == "on"
    # Read the second song's declaration.
    instrumental_b = request.form.get("instrumental_b") == "on"
    # Render the mash-up with the chosen vocals and declarations.
    report = render_mashup(path_a, path_b, output_path, vocals_a=vocals_a, vocals_b=vocals_b,
                           instrumental_a=instrumental_a, instrumental_b=instrumental_b)
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


# Define a helper that produces ALL FOUR stem records for a song, separating ONCE:
# Demucs makes every stem in one run, so asking for one stem fills all four caches.
def stem_records(path):
    # Name every stem's cached track by the stem and the source song's cache key.
    key = cache_key(path)
    # Build the four cache paths.
    outputs = {name: os.path.join(cache_directory(), name + "_" + key + ".wav")
               for name in STEM_NAMES}
    # Find the stems not yet cached.
    missing = {name: p for name, p in outputs.items() if not os.path.isfile(p)}
    # Separate once to fill every missing stem.
    if missing:
        # Render all missing stems from one Demucs run.
        render_all_stems(path, missing)
    # Build the playable record for every stem.
    records = {}
    # Walk the four stems.
    for name, output_path in outputs.items():
        # Analyze this stem-only track (cached after the first time).
        record = analyze_song(output_path)
        # Remember the track's audio for the audio route.
        stem_key = cache_key(output_path)
        # Store the mapping.
        AUDIO_PATHS[stem_key] = output_path
        # Keep the record with its audio key.
        records[name] = dict(record, audio_key=stem_key)
    # Return all four records.
    return records


# Define the route that returns ALL FOUR stem records for a song, separating once.
@application.route("/stems", methods=["POST"])
def stems_route():
    # Resolve the song from its upload or its link.
    path = resolve_song("file", "input")
    # Return every stem's playable record.
    return jsonify(stem_records(path))


# Define the route that returns one stem only, built on the same one-run helper.
@application.route("/stem/<stem_name>", methods=["POST"])
def stem_route(stem_name):
    # Allow only the four real stem names.
    if stem_name not in STEM_NAMES:
        # Refuse anything else.
        return ("Unknown stem", 400)
    # Resolve the song and build all four records (one separation fills every cache).
    records = stem_records(resolve_song("file", "input"))
    # Return the asked-for stem's playable record.
    return jsonify(records[stem_name])


# Define the older beat route as the drums case of the general stem route.
@application.route("/beats", methods=["POST"])
def beats_route():
    # Delegate to the general stem route with the drums stem.
    return stem_route("drums")


# Define the route that bounces the Mixing Desk: the four stems mixed STRAIGHT
# THROUGH from beginning to end (no jumps), at the frozen slider volumes.
@application.route("/mix_export/<file_format>", methods=["POST"])
def mix_export_route(file_format):
    # Allow only the two supported formats.
    if file_format not in ("wav", "mp3"):
        # Refuse anything else.
        return ("Unsupported format", 400)
    # Start the mix empty.
    mix = None
    # Collect a fingerprint of the request for caching the bounce.
    fingerprint_parts = []
    # Walk the four stems, each with its key and its frozen volume.
    for stem in ("drums", "bass", "vocals", "other"):
        # Read this stem's audio key.
        key = request.form.get("key_" + stem)
        # Read this stem's frozen volume (zero to one).
        gain = max(0.0, min(1.0, float(request.form.get("gain_" + stem, "1"))))
        # Refuse unknown keys.
        if key not in AUDIO_PATHS:
            # Answer with a not-found error.
            return ("Unknown audio key for " + stem, 404)
        # Remember this stem in the fingerprint.
        fingerprint_parts.append(key + (":%0.2f" % gain))
        # Load this stem's samples.
        samples, _ = load_samples(AUDIO_PATHS[key])
        # Scale by the frozen volume.
        samples = samples * gain
        # Start or grow the mix, padding to the longer length.
        if mix is None:
            # The first stem starts the mix.
            mix = samples
        else:
            # Match lengths by padding the shorter with silence.
            length = max(len(mix), len(samples))
            # Pad the mix if needed.
            mix = numpy.pad(mix, (0, length - len(mix)))
            # Pad this stem if needed.
            samples = numpy.pad(samples, (0, length - len(samples)))
            # Add this stem into the mix.
            mix = mix + samples
    # Keep the mix inside the legal sample range.
    peak = numpy.max(numpy.abs(mix)) + 1e-9
    # Normalize only if the mix would clip.
    if peak > 1.0:
        # Scale down to the peak.
        mix = mix / peak
    # Name the bounce by its fingerprint so identical bounces are cached.
    import hashlib
    # Hash the fingerprint.
    bounce_name = hashlib.sha1("|".join(fingerprint_parts).encode()).hexdigest()[:16]
    # Build the bounced wav's cache path.
    bounced_wav = os.path.join(cache_directory(), "mixdesk_" + bounce_name + ".wav")
    # Write the wav only if this exact bounce is not already cached.
    if not os.path.isfile(bounced_wav):
        # Write the mixed samples.
        soundfile.write(bounced_wav, mix, SAMPLE_RATE)
    # For wav, send the bounce directly.
    if file_format == "wav":
        # Send the file as a browser download.
        return send_file(bounced_wav, as_attachment=True,
                         download_name="aiu_mixing_desk_" + bounce_name[:8] + ".wav")
    # For mp3, convert with ffmpeg (cached per bounce).
    bounced_mp3 = os.path.join(cache_directory(), "mixdesk_" + bounce_name + ".mp3")
    # Convert only if not already cached.
    if not os.path.isfile(bounced_mp3):
        # Run ffmpeg quietly.
        subprocess.run(["ffmpeg", "-loglevel", "quiet", "-y", "-i", bounced_wav, bounced_mp3],
                       check=True)
    # Send the mp3 as a browser download.
    return send_file(bounced_mp3, as_attachment=True,
                     download_name="aiu_mixing_desk_" + bounce_name[:8] + ".mp3")


# Define the function that starts the localhost-only server.
def run_web(port=8765):
    # Announce the address on the console.
    print("AIU Music Blender web page: http://localhost:%d  (Ctrl+C to stop)" % port)
    # Run the server, bound to localhost only, per the Ninth Commandment.
    application.run(host="127.0.0.1", port=port, debug=False)
