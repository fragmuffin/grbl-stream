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

    def __init__(self, window, label=None, row=0, color_index=0):
        self.window = window
        self._label = label
        self.row = row
        self.color_index = color_index
        self.render()

    def render(self, strong=False):
        (y, x) = self.window.getmaxyx()
        label_str = " {} ".format(self._label)
        addstr_params = [
            self.row, self.label_col, " {} ".format(self._label),
            curses.color_pair(self.color_index) if curses.has_colors() else 0
        ]

        # heading attributes
        attrs = curses.color_pair(self.color_index) if curses.has_colors() else 0
        if strong:
            attrs |= curses.A_BOLD

        self.window.hline(0, 0, curses.ACS_HLINE, x)
        self.window.addstr(self.row, self.label_col, " {} ".format(self._label), attrs)

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
    def __init__(self, gcode, sent=False, status='', tree_chr=None):
        self.gcode = gcode
        self.sent = sent
        self.status = status
        self.tree_chr = tree_chr

    def to_render_list(self, index, width):
        """
        Return list of tuples, where each tuple contains:
            column, string content, colour
        """
        # import .window for colour indexes
        from .window import CPI_GOOD, CPI_ERROR

        # status colour
        status_color = 0
        if 'ok' in self.status:
            status_color = CPI_GOOD
        elif 'error' in self.status:
            status_color = CPI_ERROR

        # Gcode string (tree structure prepended
        gcode_w = max(0, width - (3 + 20))  # sent, status

        # Render List (to return)
        render_list = []
        if self.tree_chr:
            render_list.append((index + 1, self.tree_chr, 0))
            render_list.append((index + 2, curses.ACS_HLINE, 0))
            gcode_child_w = max(0, gcode_w - 4)
            gcode_str = ("{:<%i.%is}" % (gcode_child_w, gcode_child_w)).format(self.gcode)
            render_list.append((index + 4, gcode_str, 0))
        else:
            gcode_str = ("{:<%i.%is}" % (gcode_w, gcode_w)).format(self.gcode)
            render_list.append((index, gcode_str, 0))
        render_list.append((index + gcode_w + 1, '>' if self.sent else ' ', 0))
        render_list.append((index + gcode_w + 3, "{:<20s}".format(self.status), status_color))

        return render_list


class ConsoleLine(Widget):
    def __init__(self, window, content, cur=False):
        self.window = window
        self.content = content
        self._cur = cur

    def render(self, row):
        width = self.window.getmaxyx()[1]

        # Create List of render parameters
        render_list = [
            (0, '> ' if self._cur else '  ', 0),
        ]
        if isinstance(self.content, GCodeContent):
            render_list += self.content.to_render_list(2, max(0, width - 2))
        else:
            render_list += [(2, str(self.content), 0)]

        # Render content
        for (col, content, color_index) in render_list:
            if isinstance(content, int):
                # render individual character (usually one of curses.ACS_*)
                if col < width:
                    self.window.addch(
                        row, col, content,
                        curses.color_pair(color_index) if curses.has_colors() else 0
                    )

            else: # content is assumed to be a string
                ll = max(0, (width - 1) - col)  # line limit
                s = ("{:%i.%is}" % (ll, ll)).format(content).encode('utf-8') if ll else ''  # string
                if s:
                    self.window.addstr(
                        row, col, s,
                        curses.color_pair(color_index) if curses.has_colors() else 0
                    )

    @property
    def cur(self):
        return self._cur

    @cur.setter
    def cur(self, value):
        self._cur = value
