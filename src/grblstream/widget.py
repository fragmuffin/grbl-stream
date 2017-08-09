import curses
import time

class Widget(object):
    def render(self, *largs, **kwargs):
        raise NotImplementedError("render() function not implemented for %r" % self.__class__)


class Label(Widget):
    def __init__(self, window, row, col, len, text='', prefix=''):
        self.window = window
        self.row = row
        self.col = col
        self.len = len
        self._text = text
        self.prefix = prefix
        self.render()

    def render(self):
        text = self._text + (' ' * max(0, self.len - len(self._text)))
        self.window.addstr(self.row, self.col, self.prefix + text)

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, val):
        self._text = val
        self.render()


class NumberLabel(Widget):
    def __init__(self, window, row, col, value=0.0):
        self.window = window
        self.row = row
        self.col = col
        self._value = value
        self.render()

    def render(self):
        val_text = "{:>8s}".format("{:.3f}".format(self.value))
        self.window.addstr(self.row, self.col, val_text)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._value = v
        self.render()


class Button(Widget):
    def __init__(self, window, label, row, col):
        self.window = window
        self.label = label
        self.row = row
        self.col = col

        self.render()

    def flash(self):
        self.render(strong=True)
        self.window.refresh()
        time.sleep(0.1)
        self.render()
        self.window.refresh()

    def render(self, strong=False):
        addstr_params = [self.row, self.col, '[{}]'.format(self.label)]
        if strong:
            addstr_params.append(curses.A_BOLD)
        self.window.addstr(*addstr_params)


class Banner(Widget):
    label_col = 4 # <space>text<space>

    def __init__(self, window, label=None, row=0):
        self.window = window
        self._label = label
        self.row = row
        self.render()

    def render(self, strong=False):
        (y, x) = self.window.getmaxyx()
        label_str = " {} ".format(self._label)
        hline_params = [0, 0, curses.ACS_HLINE, x]
        addstr_params = [self.row, self.label_col, " {} ".format(self._label)]
        if strong:
            hline_params.append(curses.A_BOLD)
            addstr_params.append(curses.A_BOLD)

        self.window.hline(*hline_params)
        self.window.addstr(*addstr_params)

    @property
    def label(self):
        return self._label

    @label.setter
    def label(self, value):
        self._label = value
        self.render()


# Line types:
#   gcode:  <'>' if cur> <gcode> > <response>
#   info:   <'>' if cur> <info text>

class GCodeContent(object):
    def __init__(self, gcode, sent=False, status=''):
        self.gcode = gcode
        self.sent = sent
        self.status = status

    def to_str(self, width):
        gcode_w = max(0, width - 23)
        return ("{gcode:<%i.%is} {sent} {status:<20s}" % (gcode_w, gcode_w)).format(
            gcode=self.gcode,
            sent='>' if self.sent else ' ',
            status=self.status,
        )

class ConsoleLine(Widget):
    def __init__(self, window, content, cur=False):
        self.window = window
        self.content = content
        self._cur = cur
        self._width = 0
        self.update_width()

    def render(self, row):
        line = '> ' if self._cur else '  '
        if isinstance(self.content, GCodeContent):
            line += self.content.to_str(max(0, self._width - len(line)))
        else:
            line += str(self.content)
        line = ("{:%i.%is}" % (self._width-1,self._width-1)).format(line)
        try:
            self.window.addstr(row, 0, line)
        except curses.error:
            raise RuntimeError("%i>%s<" % (row, line))

    def update_width(self, width=None):
        if width is None: # get width from window
            self._width = self.window.getmaxyx()[1]
        else:
            self._width = width

    @property
    def cur(self):
        return self._cur

    @cur.setter
    def cur(self, value):
        self._cur = value
