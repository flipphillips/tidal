from pythonosc import dispatcher, osc_server
import argparse
import signal
import sys
import rtmidi
from pythonosc.udp_client import SimpleUDPClient
import threading

parser = argparse.ArgumentParser()
parser.add_argument("--debug", action="store_true", help="Enable debug output")
parsed_args = parser.parse_args()


# Set up MIDI output
midiout = rtmidi.MidiOut()
ports = midiout.get_ports()
if ports:
    midiout.open_port(0)
else:
    midiout.open_virtual_port("osc2midi")


# Define OSC to MIDI behavior
def note_on_handler(addr, pitch, velocity):
    midi_msg = [0x90, pitch, velocity]
    midiout.send_message(midi_msg)
    if parsed_args.debug:
        print(f"[ON ] {midi_msg} ← {addr}")


def note_off_handler(addr, pitch):
    midi_msg = [0x80, pitch, 0]
    midiout.send_message(midi_msg)
    if parsed_args.debug:
        print(f"[OFF] {midi_msg} ← {addr}")

# midi note mapping
NOTE_MAP = {
    "c": 0, "c#": 1, "db": 1, "d": 2, "d#": 3, "eb": 3,
    "e": 4, "f": 5, "f#": 6, "gb": 6, "g": 7, "g#": 8, "ab": 8,
    "a": 9, "a#": 10, "bb": 10, "b": 11
}

def note_name_to_midi(name):
    try:
        name = name.lower().strip()
        if len(name) < 2:
            return None
        if name[-2] in "#b":
            base = name[:-2]
            accidental = name[-2]
            octave = int(name[-1])
            note = NOTE_MAP[base + accidental]
        else:
            base = name[:-1]
            octave = int(name[-1])
            note = NOTE_MAP[base]
        return note + 12 * (octave + 1)  # MIDI note number
    except:
        return None

# Handle /dirt/play messages
def dirt_play_handler(addr, *args):
    if parsed_args.debug:
        print(f"[OSC] raw args: {args}")
    arg_dict = dict(zip(args[::2], args[1::2])) if len(args) % 2 == 0 else {}
    if parsed_args.debug:
        print(f"[OSC] parsed: {arg_dict}")

    if "note" in arg_dict:
        try:
            pitch = int(float(arg_dict["note"]))
        except ValueError:
            pitch = note_name_to_midi(arg_dict["note"]) or 60
    # if "note" in arg_dict:
    #     pitch = int(float(arg_dict["note"]))
    elif "n" in arg_dict:
        pitch = int(float(arg_dict["n"])) + 60
    else:
        pitch = 60

    try:
        velocity = int(float(arg_dict.get("velocity", 100)))
    except (ValueError, TypeError):
        if parsed_args.debug:
            print(f"[SKIP] Invalid pitch or velocity in {arg_dict}")
        return

    midi_msg_on = [0x90, pitch, velocity]
    midi_msg_off = [0x80, pitch, 0]
    midiout.send_message(midi_msg_on)
    if parsed_args.debug:
        print(f"[DIRT ON ] {midi_msg_on} ← {addr}")

    def send_off():
        midiout.send_message(midi_msg_off)
        if parsed_args.debug:
            print(f"[DIRT OFF] {midi_msg_off} ← {addr}")

    threading.Timer(0.25, send_off).start()


# Set up dispatcher and server
disp = dispatcher.Dispatcher()
disp.map("/note/start", note_on_handler)
disp.map("/note/stop", note_off_handler)
disp.map("/dirt/play", dirt_play_handler)

ip = "0.0.0.0"
port = 57120
if parsed_args.debug:
    print(f"Listening for OSC on {ip}:{port}")
server = osc_server.ThreadingOSCUDPServer((ip, port), disp)


def cleanup_and_exit(signum, frame):
    if parsed_args.debug:
        print("Shutting down gracefully...")
    midiout.close_port()
    sys.exit(0)


signal.signal(signal.SIGINT, cleanup_and_exit)
signal.signal(signal.SIGTERM, cleanup_and_exit)

# Handshake with Tidal

# Fake the SuperDirt handshake response
handshake = SimpleUDPClient("127.0.0.1", 57120)
handshake.send_message("/status", ["SuperDirt", "1.7.3"])
# end of handshake
try:
    server.serve_forever()
except KeyboardInterrupt:
    cleanup_and_exit(signal.SIGINT, None)
