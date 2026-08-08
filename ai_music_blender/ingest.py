# This module hides WHERE AUDIO COMES FROM: callers ask for a local path, and
# whether that means checking a file or downloading from YouTube is invisible to them.

# Import the module for talking to the operating system's file paths.
import os
# Import the module for running system programs such as yt-dlp.
import subprocess
# Import the module for hashing text into stable cache names.
import hashlib

# Define the folder where downloads and analyses are cached.
CACHE_DIRECTORY = os.path.expanduser("~/.cache/ai_music_blender")


# Define a function that makes sure the cache folder exists and returns it.
def cache_directory():
    # Create the cache folder, and any parents, if they are missing.
    os.makedirs(CACHE_DIRECTORY, exist_ok=True)
    # Return the cache folder path.
    return CACHE_DIRECTORY


# Define a function that turns an input string (file path or YouTube link) into a local audio path.
def local_audio_path(input_string):
    # If the input string looks like a web link, then download it locally.
    if input_string.startswith("http://") or input_string.startswith("https://"):
        # Return the path of the locally downloaded audio.
        return download_from_youtube(input_string)
    # Expand a leading tilde to the user's home folder.
    expanded_path = os.path.expanduser(input_string)
    # If the file does not exist, stop with a clear error.
    if not os.path.isfile(expanded_path):
        # Raise an error naming the missing file.
        raise FileNotFoundError("No such audio file: " + expanded_path)
    # Return the verified local path unchanged.
    return expanded_path


# Define a function that downloads the audio of a YouTube link into the cache and returns its path.
def download_from_youtube(link):
    # Hash the link so the same link always maps to the same cached file name.
    link_hash = hashlib.sha1(link.encode("utf-8")).hexdigest()[:16]
    # Build the output path template for the downloader, letting it pick the extension.
    output_template = os.path.join(cache_directory(), "youtube_" + link_hash + ".%(ext)s")
    # Look for an already-downloaded file for this link before downloading again.
    existing = find_downloaded_file(link_hash)
    # If a cached download exists, reuse it instead of downloading again.
    if existing is not None:
        # Return the cached download.
        return existing
    # Run the yt-dlp program to download the best audio, converted to m4a, quietly.
    subprocess.run(
        ["yt-dlp", "--no-playlist", "-f", "bestaudio", "-x", "--audio-format", "m4a",
         "-o", output_template, link],
        check=True)
    # Look again for the file the downloader produced.
    downloaded = find_downloaded_file(link_hash)
    # If the download cannot be found, stop with a clear error.
    if downloaded is None:
        # Raise an error naming the failed link.
        raise RuntimeError("Download appeared to succeed but no file was found for: " + link)
    # Return the downloaded audio path.
    return downloaded


# Define a helper that finds a cached download by its link hash, or returns None.
def find_downloaded_file(link_hash):
    # Walk every file name in the cache folder.
    for file_name in os.listdir(cache_directory()):
        # If the file name belongs to this link's download, it is our cached copy.
        if file_name.startswith("youtube_" + link_hash + "."):
            # Return the full path of the cached copy.
            return os.path.join(cache_directory(), file_name)
    # Report that no cached copy exists.
    return None
