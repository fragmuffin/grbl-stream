import curses

# local
from .widget import Banner, Button, NumberLabel, Label
from .widget import ConsoleLine, GCodeContent


def keypress(screen):
    key = None
    try:
        key = screen.getkey()
    except curses.error as e:
        pass # raised if no key event is buffered
             # (because that's elegant... hmm)
    return key


class AccordionWindow(object):
    """
    A region of the screen that can push those above and below it around.
    eg: as an active accordion window's content grows, it can push the window
    below it down, and make it smaller.
    """

    def __init__(self, screen, title, soft_height=2, min_height=0):
        self.screen = screen
        self.title = title
        self.soft_height = soft_height
        self.min_height = min_height

        self.focus = False
        self.lines = []  # list of ConsoleLine instances (first are at the top)

        self.window = None
        self.banner = None
        self.add_line_callback = None

    def init_window(self, row, height):
        self.window = curses.newwin(height, self.screen.getmaxyx()[1], row, 0)
        self.banner = Banner(self.window, self.title)

    def _add_line(self, line):
        i = len(self.lines)
        self.lines.append(line)
        if self.add_line_callback:
            self.add_line_callback(self)

    def move_window(self, row, height):
        width = self.screen.getmaxyx()[1]
        self.window.resize(height, width)
        for line in self.lines:
            line.update_width(width)
        self.window.mvwin(row, 0)
        #self.window.box()
        #self.window.addstr(0, 5, self.title)

    def render(self, active=False):
        #self.window.clear()  # FIXME: start fresh every render?, inefficient
        self.banner.render(strong=active)
        (rows, cols) = self.window.getmaxyx()
        if rows > 1: # we have room to render lines
            for (i, line) in enumerate(self.lines[-(rows - 1):]):
                line.render(i + 1)
        self.refresh()

    def __eq__(self, other):
        return self.title == other.title

    def refresh(self):
        self.window.refresh()

    def clear(self):
        self.lines = []
        self.window.clear()


class StatusWindow(object):
    row = 0
    banner_prefix = 'Status: '
    BACKDROP = [
        'Jog: [xxxx.yyy ]       MPos      WPos',
        '   [Y+]    [Z+]   X |xxxx.yyy |xxxx.yyy |   Feed Rate: ?',
        '[X-]  [X+]        Y |xxxx.yyy |xxxx.yyy |   Spindle:   ?',
        '   [Y-]    [Z-]   Z |xxxx.yyy |xxxx.yyy |   ',
    ]

    def __init__(self, screen):
        self.screen = screen
        (max_y, max_x) = self.screen.getmaxyx()
        self.window = curses.newwin(5, max_x, self.row, 0)
        self.status = ''
        self.banner = Banner(self.window, self.banner_prefix)

        # Widgets
        self.widgets = {
            'X+': Button(self.window, 'X+', 3, 6),
            'X-': Button(self.window, 'X-', 3, 0),
            'Y+': Button(self.window, 'Y+', 2, 3),
            'Y-': Button(self.window, 'Y-', 4, 3),
            'Z+': Button(self.window, 'Z+', 2, 11),
            'Z-': Button(self.window, 'Z-', 4, 11),
            'jog': NumberLabel(self.window, 1, 6, 0.001),
            'MPosX': NumberLabel(self.window, 2, 21),
            'MPosY': NumberLabel(self.window, 3, 21),
            'MPosZ': NumberLabel(self.window, 4, 21),
            'WPosX': NumberLabel(self.window, 2, 31),
            'WPosY': NumberLabel(self.window, 3, 31),
            'WPosZ': NumberLabel(self.window, 4, 31),
            'feed_rate': Label(self.window, 2, 44, len=20, text='?', prefix='Feed Rate: '),
            'spindle': Label(self.window, 3, 44, len=20, text='?', prefix='Spindle:   '),
        }

        self.render()
        self.refresh()

    def render(self):
        (screen_height, screen_width) = self.screen.getmaxyx()
        for (i, line) in enumerate(self.BACKDROP):
           self.window.addstr(i + 1, 0, line[:screen_width])
        for widget in self.widgets.values():
            widget.render()

    def set_status(self, status):
        self.status = status
        self.banner.label = "{prefix}{label}".format(
            prefix=self.banner_prefix,
            label=status,
        )
        self.refresh()

    @property
    def is_idle(self):
        return self.status == 'Idle'

    def refresh(self):
        self.window.refresh()


class AccordionWindowManager(object):
    def __init__(self, screen, windows, header_height, footer_height=0):

        self.screen = screen
        self.windows = windows
        self.header_height = header_height
        self.footer_height = footer_height

        self._focus_index = 0

        self._log = []

        # Initialize accordion window's curses.Window instance
        def _add_line_cb(window):
            self.update_distrobution()
            window.render()

        cur_row = self.header_height
        for (i, window) in enumerate(self.windows):
            window.init_window(cur_row, window.soft_height)
            window.refresh()
            window.add_line_callback = _add_line_cb
            cur_row += window.min_height

    @property
    def focus(self):
        return self.windows[self._focus_index]

    @focus.setter
    def focus(self, value):
        self._focus_index = self.windows.index(value)
        self.update_distrobution()

    def update_distrobution(self):
        # rows available across space
        rows = self.screen.getmaxyx()[0] - (self.header_height + self.footer_height)
        min_occupied = sum(w.min_height for w in self.windows)
        available = rows - min_occupied
        if rows - min_occupied < 3:
            pass # TODO: not enough room to respect min_heights
        # focussed window height
        #   - self.focus.min_height
        #   - len(self.focus.lines) + 1
        #   - available + self.focus.min_height  # max available space
        extra_alocate = max(0, (len(self.focus.lines) + 1) - self.focus.min_height)
        height_f = min(available, extra_alocate) + self.focus.min_height
        available -= height_f - self.focus.min_height

        cur_row = self.header_height
        for w in self.windows:
            if w == self.focus:
                height = height_f
            else:
                extra_alocate = max(0, (len(w.lines) + 1) - w.min_height)
                height = min(available, extra_alocate) + w.min_height
                available -= height - w.min_height

            w.move_window(cur_row, height)
            w.render(active=True if w == self.focus else False)
            cur_row += height

        self.refresh()

    def refresh(self):
        for w in self.windows:
            w.refresh()


class InitWindow(AccordionWindow):
    def add_line(self, text):
        obj = ConsoleLine(self.window, text)
        self._add_line(obj)
        return obj


class JoggingWindow(AccordionWindow):
    def add_line(self, gcode, sent=False, status=''):
        obj = ConsoleLine(self.window, GCodeContent(
            gcode=gcode, sent=sent, status=status
        ))
        self._add_line(obj)
        return obj


class StreamWindow(AccordionWindow):
    def add_line(self, gcode, sent=False, status=''):
        obj = ConsoleLine(self.window, GCodeContent(
            gcode=gcode, sent=sent, status=status
        ))
        self._add_line(obj)
        return obj
