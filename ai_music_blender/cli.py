# This module is the COMMAND LINE FACE: it decides nothing and hides nothing,
# translating typed commands into engine calls, per the Tenth Commandment.

# Import the command line argument parser.
import argparse
# Import the engine's ingest function.
from .ingest import local_audio_path
# Import the engine's analysis function.
from .analysis import analyze_song
# Import the engine's jukebox functions.
from .jukebox import play_walk, render_walk, DEFAULT_CHAOS
# Import the engine's mash-up functions.
from .mashup import render_mashup, score_compatibility


# Define the function that builds the command line parser.
def build_parser():
    # Create the top-level parser with the program's name and story.
    parser = argparse.ArgumentParser(
        prog="ai-music-blender",
        description="AI Music Blender: the self-hosted infinite jukebox and mash-up machine.")
    # Create the sub-command holder.
    commands = parser.add_subparsers(dest="command", required=True)
    # Define the analyze sub-command.
    analyze = commands.add_parser("analyze", help="Analyze a song and print what was found.")
    # The analyze sub-command takes one input (file or YouTube link).
    analyze.add_argument("input", help="Audio file path or YouTube link.")
    # Define the jukebox sub-command (the sacred classic mode).
    jukebox = commands.add_parser("jukebox", help="Play one song forever, or render a walk.")
    # The jukebox sub-command takes one input.
    jukebox.add_argument("input", help="Audio file path or YouTube link.")
    # The jukebox chaos option sets the jump probability.
    jukebox.add_argument("--chaos", type=float, default=DEFAULT_CHAOS,
                         help="Jump probability from 0.0 (calm) to 1.0 (wild).")
    # The jukebox seed option makes the walk reproducible and shareable.
    jukebox.add_argument("--seed", type=int, default=None,
                         help="Seed number for a reproducible, shareable walk.")
    # The jukebox render option writes a file instead of playing live.
    jukebox.add_argument("--render", metavar="OUTPUT", default=None,
                         help="Render the walk to this audio file instead of playing.")
    # The jukebox length option sets the rendered length in seconds.
    jukebox.add_argument("--length", type=float, default=120.0,
                         help="Rendered length in seconds (with --render).")
    # Define the mashup sub-command (The_AI_Mashup_Machine).
    mashup = commands.add_parser("mashup", help="Blend two songs into a mash-up.")
    # The mashup sub-command takes the first song.
    mashup.add_argument("input_a", help="First song (its vocal rides on top with --stems).")
    # The mashup sub-command takes the second song.
    mashup.add_argument("input_b", help="Second song (its instrumental carries with --stems).")
    # The mashup output option names the rendered file.
    mashup.add_argument("-o", "--output", default="mashup.wav", help="Output audio file.")
    # The mashup stems option engages Demucs stem separation.
    mashup.add_argument("--stems", action="store_true",
                        help="Separate stems with Demucs: vocals of A over instrumental of B.")
    # Define the web sub-command (the localhost face).
    web = commands.add_parser("web", help="Start the localhost web page.")
    # The web port option chooses the localhost port.
    web.add_argument("--port", type=int, default=8765, help="Localhost port (default 8765).")
    # Define the gui sub-command (the Ubuntu app face).
    commands.add_parser("gui", help="Open the Ubuntu desktop app.")
    # Return the finished parser.
    return parser


# Define a helper that prints an analysis record as a friendly summary.
def print_analysis(record):
    # Count the jump edges across the whole graph.
    edge_count = sum(len(edges) for edges in record["graph"])
    # Print the tempo.
    print("Tempo: %.1f beats per minute" % record["tempo"])
    # Print the key.
    print("Key: %s %s (Camelot %s)" % (record["key"]["tonic"], record["key"]["mode"],
                                       record["key"]["camelot"]))
    # Print the beat count and duration.
    print("Beats: %d across %.1f seconds" % (len(record["beats"]), record["duration"]))
    # Print the jump edge count.
    print("Jump edges found: %d" % edge_count)


# Define the handler for the analyze command.
def run_analyze(arguments):
    # Resolve the input to a local audio path.
    path = local_audio_path(arguments.input)
    # Analyze the song.
    record = analyze_song(path)
    # Print the friendly summary.
    print_analysis(record)


# Define the handler for the jukebox command.
def run_jukebox(arguments):
    # Resolve the input to a local audio path.
    path = local_audio_path(arguments.input)
    # When rendering was requested, render the walk to the output file.
    if arguments.render is not None:
        # Render the walk.
        record = render_walk(path, arguments.render, arguments.length,
                             chaos=arguments.chaos, seed=arguments.seed)
        # Report what was rendered.
        print("Rendered %.0f seconds of infinite walk to %s" % (arguments.length,
                                                                arguments.render))
        # Print the analysis summary too.
        print_analysis(record)
    # Otherwise, play the walk live until Ctrl+C.
    else:
        # Announce how to stop.
        print("Playing forever - press Ctrl+C to stop.")
        # Define a small listener that prints a marker at every jump.
        def on_beat(beat_index, jumped):
            # Print a jump marker only when a jump happened.
            if jumped:
                # Show the beat the walk jumped to.
                print("  jump -> beat %d" % beat_index)
        # Play the walk live.
        play_walk(path, chaos=arguments.chaos, seed=arguments.seed, on_beat=on_beat)


# Define the handler for the mashup command.
def run_mashup(arguments):
    # Resolve the first input to a local audio path.
    path_a = local_audio_path(arguments.input_a)
    # Resolve the second input to a local audio path.
    path_b = local_audio_path(arguments.input_b)
    # Render the mash-up and collect the honest report.
    report = render_mashup(path_a, path_b, arguments.output, use_stems=arguments.stems)
    # Print the compatibility score.
    print("Compatibility score: %.3f (stretch %.1f%%, key shift %+d semitones)"
          % (report["compatibility"]["score"], report["compatibility"]["stretch"] * 100.0,
             report["compatibility"]["key_shift"]))
    # Print what was actually applied.
    print("Applied: target tempo %.1f, stretch A %.3f, stretch B %.3f, key shift %+d, stems %s"
          % (report["target_tempo"], report["stretch_a"], report["stretch_b"],
             report["key_shift_applied"], report["stems"]))
    # Print where the blend was written.
    print("Wrote %s - now try: ai-music-blender jukebox %s" % (report["output"],
                                                               report["output"]))


# Define the main entry point of the command line face.
def main(argument_list=None):
    # Build the parser.
    parser = build_parser()
    # Parse the arguments.
    arguments = parser.parse_args(argument_list)
    # Route the analyze command.
    if arguments.command == "analyze":
        # Run the analyze handler.
        run_analyze(arguments)
    # Route the jukebox command.
    elif arguments.command == "jukebox":
        # Run the jukebox handler.
        run_jukebox(arguments)
    # Route the mashup command.
    elif arguments.command == "mashup":
        # Run the mashup handler.
        run_mashup(arguments)
    # Route the web command.
    elif arguments.command == "web":
        # Import the web face only when asked for, so Flask is not loaded needlessly.
        from .web import run_web
        # Start the localhost web server.
        run_web(port=arguments.port)
    # Route the gui command.
    elif arguments.command == "gui":
        # Import the GUI face only when asked for, so GTK is not loaded needlessly.
        from .gui import run_gui
        # Open the desktop app.
        run_gui()
