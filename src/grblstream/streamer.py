import re
import time
import serial

from .widget import ConsoleLine, GCodeContent


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

            # Send next line (if possible)
            self.poll_transmission()

            # Raiser exception on error
            # IMPORTANT: must be the last thing this function does
            if match.group('keyword').lower() == 'error':
                raise GCodeStreamException("error on gcode: '{gcode}' {msg}".format(
                    gcode=line.gcode,
                    msg=response
                ))

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
