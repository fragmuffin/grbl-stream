import os
import json
import argparse
import collections

# local libs
import arduino_tools

# Default content for settings file (encoded to json)
#   ~/.grbl-stream.json
DEFAULT_FILENAME = os.path.join(
    os.path.expanduser('~'),
    '.grbl-stream.json'
)

DEFAULT_SETTINGS = {
    'show_tips': True,  # display keyboard binding for beginners
    'keep_open': True,  # keep window open until user presses [enter] or 'q'
                        # if False, script returns as soon as gcode is complete.
    'delay_before_exit': 0,  # time to delay before ending script

    # --- Serial Logging
    'serial_logging': False,
    'serial_log_file': 'grbl-stream.log',  # stored in working path

    # --- Serial Connection
    # serial_device: the serial device GRBL is connected to:
    #   - direct block file (eg: "/dev/ttyACM0")
    #   - arduino's serial number (eg: "55639309235451C071B0")
    #   - None: script will attempt to find it automagically (witchcraft)
    'serial_device': None,
    'serial_baudrate': 115200,

    # --- Status (sending '?')
    'status_polling': True,  # disable for minimal serial comms
    'status_poll_interval': 0.25,  # 4Hz (unit: sec)

    # --- Jogging
    'interactive_jogging': True,  # if set, user input will be required to position machine before streaming starts
    'jogging_unit': 'mm',  # {mm|inch}, if neither will default to 'mm'
    'jogging_values': [0.001, 0.01, 0.1, 1, 10, 25, 50, 100, 250, 500],
    'jogging_init_value': 0.001,  # must be one of the values above
    # use_grbl_jogging: for CNC alignemnt before streaming
    #   - True: prefix jogging commands with "$J=" as documented here:
    #           https://github.com/gnea/grbl/wiki/Grbl-v1.1-Jogging
    #   - False: use standard gcodes for initial positioning (use for < v1.1)
    'use_grbl_jogging': True,

    # --- Streaming
    'stream_pending_count': 5,  # number of lines to show that haven't yet been sent over serial
    'grbl_buffer_size': 128,  # only change if GRBL has been compiled with a different buffer size
    # split_gcodes:
    #   - False: simply stream each gcode line
    #   - True: split gcode lines into their individual gcodes. Transmit them
    #           in processing order outlined by the LinuxCNC guideline.
    'split_gcodes': False,

    # --- Error Handling (TODO)
    # Configure how to handle GRBL errors... namely:
    #   20	Unsupported or invalid g-code command found in block. (eg: M6,G43,G98)
    #   22	Feed rate has not yet been set or is undefined
    #   33	The motion command has an invalid target (raised by arc codes)
    # Handling options: (brainstorming)
    #   - display as warning, and continue stream (what most streamers do)
    #   - halt stream (empty grbl buffer) and run termination sequence (eg: M5)
    #   - halt stream (empty grbl buffer) and re
    # Only works when split_gcodes is True

}


class SettingsFile(collections.MutableMapping):

    def __init__(self, filename):
        self.filename = filename
        self.store = dict()

        # Update from file
        with open(self.filename, 'r') as fh:
            self.update(json.load(fh))

    def __getitem__(self, key):
        return self.store[key]

    def __setitem__(self, key, value):
        self.store[key] = value

    def __delitem__(self, key):
        del self.store[key]

    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)


class Config(object):
    def __init__(self, args, filename):
        assert isinstance(args, argparse.Namespace), "invalid args parameter: %r" % args
        self.args = args

        # --- Settings file
        # Use default config file if no name is given
        if not filename:
            filename = DEFAULT_FILENAME

        # Create file (with default values) if it does not already exist
        if not os.path.isfile(filename):
            with open(filename, 'w') as fh:
                json.dump(DEFAULT_SETTINGS, fh, indent=4, sort_keys=True)

        self.settings = SettingsFile(filename)

        # --- Special Cases
        # 'serial_device'
        if self.serial_device is None:
            # FIXME: there has to be a way to do this native to argparse
            self.args.serial_device = arduino_tools.device_type(self.args.serial_device)

        # 'serial_log_file' & 'serial_logging'
        if self.args.serial_log_file:
            self.args.serial_logging = True

    def __getattr__(self, key):
        # 1st preference: command-line argument
        arg_value = getattr(self.args, key, None)
        if arg_value is not None:
            return arg_value

        # 2nd preference: settings file
        if key in self.settings:
            return self.settings[key]

        else:
            raise AttributeError("'{cls}' object has no attribute '{key}'".format(
                cls=self.__class__.__name__,
                key=key
            ))
