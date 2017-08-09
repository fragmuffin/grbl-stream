import re
import time
import serial

from .widget import ConsoleLine, GCodeContent

GRBL_ERROR_MAP = {
    1: "G-code words consist of a letter and a value. Letter was not found.",
    2: "Numeric value format is not valid or missing an expected value.",
    3: "Grbl '$' system command was not recognized or supported.",
    4: "Negative value received for an expected positive value.",
    5: "Homing cycle is not enabled via settings.",
    6: "Minimum step pulse time must be greater than 3usec",
    7: "EEPROM read failed. Reset and restored to default values.",
    8: "Grbl '$' command cannot be used unless Grbl is IDLE. Ensures smooth operation during a job.",
    9: "G-code locked out during alarm or jog state",
    10: "Soft limits cannot be enabled without homing also enabled.",
    11: "Max characters per line exceeded. Line was not processed and executed.",
    12: "(Compile Option) Grbl '$' setting value exceeds the maximum step rate supported.",
    13: "Safety door detected as opened and door state initiated.",
    14: "(Grbl-Mega Only) Build info or startup line exceeded EEPROM line length limit.",
    15: "Jog target exceeds machine travel. Command ignored.",
    16: "Jog command with no '=' or contains prohibited g-code.",
    17: "Laser mode requires PWM output.",
    20: "Unsupported or invalid g-code command found in block.",
    21: "More than one g-code command from same modal group found in block.",
    22: "Feed rate has not yet been set or is undefined.",
    23: "G-code command in block requires an integer value.",
    24: "Two G-code commands that both require the use of the XYZ axis words were detected in the block.",
    25: "A G-code word was repeated in the block.",
    26: "A G-code command implicitly or explicitly requires XYZ axis words in the block, but none were detected.",
    27: "N line number value is not within the valid range of 1 - 9,999,999.",
    28: "A G-code command was sent, but is missing some required P or L value words in the line.",
    29: "Grbl supports six work coordinate systems G54-G59. G59.1, G59.2, and G59.3 are not supported.",
    30: "The G53 G-code command requires either a G0 seek or G1 feed motion mode to be active. A different motion was active.",
    31: "There are unused axis words in the block and G80 motion mode cancel is active.",
    32: "A G2 or G3 arc was commanded but there are no XYZ axis words in the selected plane to trace the arc.",
    33: "The motion command has an invalid target. G2, G3, and G38.2 generates this error, if the arc is impossible to generate or if the probe target is the current position.",
    34: "A G2 or G3 arc, traced with the radius definition, had a mathematical error when computing the arc geometry. Try either breaking up the arc into semi-circles or quadrants, or redefine them with the arc offset definition.",
    35: "A G2 or G3 arc, traced with the offset definition, is missing the IJK offset word in the selected plane to trace the arc.",
    36: "There are unused, leftover G-code words that aren't used by any command in the block.",
    37: "The G43.1 dynamic tool length offset command cannot apply an offset to an axis other than its configured axis. The Grbl default axis is the Z-axis.    ",
}

GRBL_ALARM_MAP = {
    1: "Hard limit triggered. Machine position is likely lost due to sudden and immediate halt. Re-homing is highly recommended.",
    2: "G-code motion target exceeds machine travel. Machine position safely retained. Alarm may be unlocked.",
    3: "Reset while in motion. Grbl cannot guarantee position. Lost steps are likely. Re-homing is highly recommended.",
    4: "Probe fail. The probe is not in the expected initial state before starting probe cycle, where G38.2 and G38.3 is not triggered and G38.4 and G38.5 is triggered.",
    5: "Probe fail. Probe did not contact the workpiece within the programmed travel for G38.2 and G38.4.",
    6: "Homing fail. Reset during active homing cycle.",
    7: "Homing fail. Safety door was opened during active homing cycle.",
    8: "Homing fail. Cycle failed to clear limit switch when pulling off. Try increasing pull-off setting or check wiring.",
    9: "Homing fail. Could not find limit switch within search distance. Defined as 1.5 * max_travel on search and 5 * pulloff on locate phases.",
}

GRBL_SETTING_MAP = {
    0: "Step pulse time, microseconds",
    1: "Step idle delay, milliseconds",
    2: "Step pulse invert, mask",
    3: "Step direction invert, mask",
    4: "Invert step enable pin, boolean",
    5: "Invert limit pins, boolean",
    6: "Invert probe pin, boolean",
    10: "Status report options, mask",
    11: "Junction deviation, millimeters",
    12: "Arc tolerance, millimeters",
    13: "Report in inches, boolean",
    20: "Soft limits enable, boolean",
    21: "Hard limits enable, boolean",
    22: "Homing cycle enable, boolean",
    23: "Homing direction invert, mask",
    24: "Homing locate feed rate, mm/min",
    25: "Homing search seek rate, mm/min",
    26: "Homing switch debounce delay, milliseconds",
    27: "Homing switch pull-off distance, millimeters",
    30: "Maximum spindle speed, RPM",
    31: "Minimum spindle speed, RPM",
    32: "Laser-mode enable, boolean",
    100: "X-axis steps per millimeter",
    101: "Y-axis steps per millimeter",
    102: "Z-axis steps per millimeter",
    110: "X-axis maximum rate, mm/min",
    111: "Y-axis maximum rate, mm/min",
    112: "Z-axis maximum rate, mm/min",
    120: "X-axis acceleration, mm/sec^2",
    121: "Y-axis acceleration, mm/sec^2",
    122: "Z-axis acceleration, mm/sec^2",
    130: "X-axis maximum travel, millimeters",
    131: "Y-axis maximum travel, millimeters",
    132: "Z-axis maximum travel, millimeters",
}

class SerialPort(object):
    def __init__(self, device, baudrate, logfilename=None):
        self.device = device
        self.baudrate = baudrate
        self.serial = serial.Serial(self.device, self.baudrate)
        self.logfilename = logfilename
        self.log = None

        self._cur_line = ''  # buffered line chars before '\n' received

        if self.logfilename:
            self.log = open(self.logfilename, 'w')

    def __del__(self):
        self.serial.close()
        if self.log:
            self.log.close()

    def _log_write(self, prefix, msg):
        if self.log:
            self.log.write("[{time:.2f}] {prefix} {msg}\n".format(
                time=time.time(),
                prefix=prefix,
                msg=msg.replace('\n', r'\n').replace('\r', r'\r'),
            ))

    def write(self, data):
        self._log_write('>>', data)
        self.serial.write(data)

    def readlines(self, timeout=None):
        start_time = time.time()
        orig_timeout = self.serial.timeout

        def _new_timeout():
            """Return linearly diminished timeout (with realtime)"""
            if timeout is None:
                return None
            cur_time = time.time()
            if cur_time - start_time >= timeout:
                return 0.0
            return timeout - (cur_time - start_time)

        while True:
            # Set read timeout
            time_remaining = _new_timeout()
            if time_remaining == 0:
                break
            self.serial.timeout = time_remaining

            # read
            # FIXME: char by char (a bit clunky, but easy to write)
            try:
                received_chr = self.serial.read()
            except serial.serialutil.SerialException:
                continue # terminal resize interrupts serial read
            self._cur_line += received_chr
            if self._cur_line.endswith('\n'):
                self._log_write('<<', self._cur_line)
                received_line = re.sub(r'\r?\n$', '', self._cur_line)
                self._cur_line = ''
                yield received_line

        self.serial.timeout = orig_timeout


class GCodeStreamException(Exception):
    """Raised when GRBL responds with error"""
    pass


class GCodeStreamer(object):
    # - keep track of GRBL buffer size
    # - transmit to GRBL
    # - read GRLB responses and delegate accordingly

    class Line(object):
        # - handle status & screen update
        #   - new
        #   - sent
        #   - received (status string) (raise exception if bad
        # - send
        #   - publish on screen
        # - set status
        #   - publish status on screen
        #   - report bad status back to streamer
        def __init__(self, gcode, widget=None):
            # verify parameter(s)
            if widget is not None:
                assert isinstance(widget, ConsoleLine), "bad widget type: %r" % widget
                assert isinstance(widget.content, GCodeContent), "bad widget content: %r" % widget.content

            # initialize
            self.gcode = gcode
            self.widget = widget

        def set_sent(self, value=True):
            if self.widget:
                self.widget.content.sent = value

        def set_status(self, msg):
            if self.widget:
                self.widget.content.status = msg

        def _normalized(self):
            return re.sub(r'\(.*?\)|;.*|\s', '', self.gcode).upper()

        def __str__(self):
            """
            :return: str to be sent over serial (including newline)
            """
            return self._normalized() + "\n"

        def __len__(self):
            return len(str(self))

        def __bool__(self):
            if self._normalized():
                return True
            return False

        __nonzero__ = __bool__  # python 2.x compatability


    DEFAULT_MAX_BUFFER = 128
    RESPONSE_REGEX = re.compile(r'^(?P<keyword>(ok|error))', re.I)

    def __init__(self, serial, max_buffer=None):
        assert isinstance(serial, SerialPort), "bad serial type: %r" % serial
        self.serial = serial
        self.max_buffer = max_buffer if max_buffer is not None else self.DEFAULT_MAX_BUFFER

        # --- Lines
        # Description:
        #    a moving window buffer of GCodeStreamer.Line instances sent to GRBL.
        #    this moving window stretches between:
        #       [0]  oldest sent gcode that has not yet received a GRBL response.
        #            once status is received, [0] is removed: self.sent_lines.pop(0)
        #       [-1] most recent gcode sent to GRBL device.
        self.sent_lines = []
        self.pending_lines = []

    def is_valid_response(self, response_msg):  # TODO: delete if not used
        """returns truthy: regex match if valid, None otherwise"""
        return self.RESPONSE_REGEX.search(response_msg)

    def process_response(self, response):
        """
        A response from GRBL is assumed to be to gcode at self.sent_lines[0]
        Once processed, the first of self.sent_lines is removed
        :param response: str received from GRBL device
        """
        match = self.RESPONSE_REGEX.search(response)
        if match:  # received text is a valid response to a line
            # Pop oldest line
            line = self.sent_lines.pop(0)
            line.set_status(response)
            if match.group('keyword').lower() == 'error':
                raise GCodeStreamException("error on gcode: '{gcode}' {msg}".format(
                    gcode=line.gcode,
                    msg=response
                ))

            # Send next line (if possible)
            self.poll_transmission()
        else:
            raise GCodeStreamException("unidentified message: %s" % response)

    def can_send(self, line):
        """
        Can the given line be transmitted?
        :return: True if line will not push GRBL's buffer over it's limit
        """
        assert isinstance(line, GCodeStreamer.Line)
        return (self.used_buffer + len(line)) <= self.max_buffer

    def send(self, line):
        """Add to pending lines, then poll transmission (once)"""
        assert isinstance(line, GCodeStreamer.Line)
        self.pending_lines.append(line)
        self.poll_transmission()

    def _transmit(self, line):
        assert isinstance(line, GCodeStreamer.Line)
        self.serial.write(str(line)) # Send to GRBL device

    def poll_transmission(self):
        """
        Send next line if there's enough room in GRBL's buffer.
        :return: True if there's data to transmit, False if it's all been sent
        """
        if not self.pending_lines:
            return False
        elif self.can_send(self.pending_lines[0]):
            line = self.pending_lines.pop(0)
            self._transmit(line)
            self.sent_lines.append(line) # Add to line buffer
            line.set_sent()
        return True

    @property
    def finished(self):
        if self.sent_lines or self.pending_lines:
            return False
        return True

    @property
    def used_buffer(self):
        return sum(len(l) for l in self.sent_lines)

    @property
    def pending_count(self):
        return len(self.pending_lines)
