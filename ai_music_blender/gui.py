# This module is the UBUNTU DESKTOP FACE: a GTK 3 window that opens songs, runs
# both modes through the engine, and plays results - deciding nothing itself.

# Import the subprocess tools for playback and background work.
import subprocess
# Import the threading tools so long engine work never freezes the window.
import threading
# Import the GTK binding loader.
import gi
# Ask for GTK version 3, the version the target machine provides.
gi.require_version("Gtk", "3.0")
# Import GTK and the main-loop helper.
from gi.repository import Gtk, GLib
# Import the engine's analysis function.
from .analysis import analyze_song
# Import the engine's renderers.
from .jukebox import render_walk
# Import the engine's mash-up renderer.
from .mashup import render_mashup


# Define the application window.
class BlenderWindow(Gtk.Window):
    # Define how the window is built.
    def __init__(self):
        # Create the window with the project title.
        super().__init__(title="AIU Music Blender")
        # Give the window a comfortable default size.
        self.set_default_size(560, 320)
        # Track the player process so Stop can end it.
        self.player = None
        # Build a vertical box to stack the controls.
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        # Give the column a margin.
        column.set_border_width(12)
        # Put the column in the window.
        self.add(column)
        # Add the first song chooser.
        self.chooser_a = Gtk.FileChooserButton(title="Choose Song A")
        # Label and pack the first chooser.
        column.pack_start(self.labeled("Song A (jukebox, or mash-up vocal):", self.chooser_a),
                          False, False, 0)
        # Add the second song chooser (for mash-ups).
        self.chooser_b = Gtk.FileChooserButton(title="Choose Song B")
        # Label and pack the second chooser.
        column.pack_start(self.labeled("Song B (mash-up instrumental, optional):",
                                       self.chooser_b), False, False, 0)
        # Add the chaos slider.
        self.chaos = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.0, 1.0, 0.05)
        # Start the slider at the engine default.
        self.chaos.set_value(0.25)
        # Label and pack the chaos slider.
        column.pack_start(self.labeled("Chaos (jump probability):", self.chaos), False, False, 0)
        # Build a row for the action buttons.
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        # Add the play-forever button.
        self.add_button(row, "Play Forever", self.on_play_forever)
        # Add the mash-up button.
        self.add_button(row, "Make Mash-Up", self.on_mashup)
        # Add the stop button.
        self.add_button(row, "Stop", self.on_stop)
        # Pack the button row.
        column.pack_start(row, False, False, 0)
        # Add the status line.
        self.status = Gtk.Label(label="Choose a song to begin.")
        # Pack the status line.
        column.pack_start(self.status, False, False, 0)

    # Define a helper that wraps a control with a label above it.
    def labeled(self, text, control):
        # Build a small vertical box.
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        # Add the label, left-aligned.
        label = Gtk.Label(label=text, xalign=0.0)
        # Pack the label.
        box.pack_start(label, False, False, 0)
        # Pack the control.
        box.pack_start(control, False, False, 0)
        # Return the labeled control.
        return box

    # Define a helper that adds one button to a row.
    def add_button(self, row, text, handler):
        # Create the button.
        button = Gtk.Button(label=text)
        # Connect the button to its handler.
        button.connect("clicked", handler)
        # Pack the button.
        row.pack_start(button, True, True, 0)

    # Define a helper that shows a status message from any thread.
    def say(self, message):
        # Ask the main loop to update the label safely.
        GLib.idle_add(self.status.set_text, message)

    # Define a helper that runs engine work in a background thread.
    def in_background(self, work):
        # Start the work in a daemon thread so the window stays live.
        threading.Thread(target=work, daemon=True).start()

    # Define a helper that plays an audio file with the system player.
    def play_file(self, path):
        # Stop any earlier playback first.
        self.on_stop(None)
        # Start ffplay without a window.
        self.player = subprocess.Popen(["ffplay", "-loglevel", "quiet", "-nodisp",
                                        "-autoexit", path])

    # Define the handler for the play-forever button.
    def on_play_forever(self, _button):
        # Read the chosen song.
        path = self.chooser_a.get_filename()
        # Refuse politely when no song is chosen.
        if not path:
            # Explain what is needed.
            self.say("Choose Song A first.")
            # Stop here.
            return
        # Read the chaos setting now, on the main thread.
        chaos = self.chaos.get_value()
        # Define the background work.
        def work():
            # Tell the user analysis may take a moment.
            self.say("Analyzing and rendering ten minutes of forever...")
            # Render a ten-minute walk to the cache.
            from .ingest import cache_directory
            # Build the render path.
            import os
            # Name the rendered file.
            rendered = os.path.join(cache_directory(), "gui_forever.wav")
            # Render the walk with the chosen chaos.
            record = render_walk(path, rendered, 600.0, chaos=chaos)
            # Report and play the render.
            self.say("Playing: %.1f BPM, %d beats. Press Stop to end."
                     % (record["tempo"], len(record["beats"])))
            # Play the rendered walk.
            self.play_file(rendered)
        # Run the work in the background.
        self.in_background(work)

    # Define the handler for the mash-up button.
    def on_mashup(self, _button):
        # Read both chosen songs.
        path_a = self.chooser_a.get_filename()
        # Read the second song.
        path_b = self.chooser_b.get_filename()
        # Refuse politely when either song is missing.
        if not path_a or not path_b:
            # Explain what is needed.
            self.say("Choose Song A and Song B for a mash-up.")
            # Stop here.
            return
        # Define the background work.
        def work():
            # Tell the user the blend is running.
            self.say("Blending... (tempo match, key match, mix)")
            # Import the cache folder helper.
            from .ingest import cache_directory
            # Import the path tools.
            import os
            # Name the blended file.
            blended = os.path.join(cache_directory(), "gui_mashup.wav")
            # Render the mash-up.
            report = render_mashup(path_a, path_b, blended)
            # Report the honest result and play it.
            self.say("Blend score %.3f, stretch %.1f%%, key %+d. Playing."
                     % (report["compatibility"]["score"],
                        report["compatibility"]["stretch"] * 100.0,
                        report["key_shift_applied"]))
            # Play the blend.
            self.play_file(blended)
        # Run the work in the background.
        self.in_background(work)

    # Define the handler for the stop button.
    def on_stop(self, _button):
        # If a player is running, end it.
        if self.player is not None:
            # Stop the player.
            self.player.terminate()
            # Forget the player.
            self.player = None


# Define the function that opens the desktop app.
def run_gui():
    # Create the window.
    window = BlenderWindow()
    # Close the whole app when the window closes.
    window.connect("destroy", Gtk.main_quit)
    # Show everything in the window.
    window.show_all()
    # Hand control to the GTK main loop.
    Gtk.main()
