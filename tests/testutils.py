# utilities for the testing suite (as opposed to the tests for utils.py)
import sys
import os
import inspect


# Units Under Test
def add_lib_to_path(scope_varname, rel_path):
    if os.environ.get(scope_varname, 'local') == 'installed':
        # Run tests on the installed libray
        pass  # nothing to be done
    else:
        # Run tests explicitly on files in ../src (ignore any installed libs)
        # Add pygcode (relative to this test-path) to the system path
        _this_path = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        sys.path.insert(0, os.path.join(_this_path, rel_path))


add_lib_to_path('PYGCODE_TESTSCOPE', '../../pygcode/src')
add_lib_to_path('GRBLSTREAM_TESTSCOPE', '../src')
