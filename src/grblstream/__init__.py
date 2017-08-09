# =========================== Package Information ===========================
# Version Planning:
#   0.1.x               - Development Status :: 2 - Pre-Alpha
#   0.2.x               - Development Status :: 3 - Alpha
#   0.3.x               - Development Status :: 4 - Beta
#   1.x                 - Development Status :: 5 - Production/Stable
#   <any above>.y       - developments on that version (pre-release)
#   <any above>*.dev*   - development release (intended purely to test deployment)
__version__ = "0.1.0"

__title__ = "grblstream"
__description__ = "Command-line GRBL streaming script"
__url__ = "https://github.com/fragmuffin/grbl-stream"

__author__ = "Peter Boin"
__email__ = "peter.boin@gmail.com"

__license__ = "GPLv3"

# not text-parsable
__copyright__ = "Copyright (c) 2017 {0}".format(__author__)


__all__ = [
    # modules
    'arduino_tools',
    'settingsfile',
    'streamer',
    'widget',
    'window',

]

# modules
import arduino_tools
import settingsfile
import streamer
import widget
import window

# settingsfile
from config import Config, DEFAULT_SETTINGS

# window
from window import keypress
