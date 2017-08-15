import argparse
import re

# ---------------- Arduino Util ---------------------
def arduino_comports():
    """
    List of serial comports serial numbers of Arduino boards connected to this machine
    :return: generator of comports connected to arduino
    """
    #for comport in arduino_comports():
    #    comport.serial_number # '55639303235351C071B0'
    #    comport.device # '/def/ttyACM0'
    from serial.tools.list_ports_posix import comports

    arduino_manufacturer_regex = re.compile(r'arduino', re.IGNORECASE) # simple, because I've only got one to test on
    for comport in comports():
        if comport.manufacturer:
            match = arduino_manufacturer_regex.search(comport.manufacturer)
            if match:
                yield comport


def device_type(value):
    """
    Use as a 'type' for argparse parameter
    """

    def _safe_comport_wrapper(key):
        # define comports list
        try:
            comports = [cp for cp in arduino_comports() if key(cp)]
        except Exception:
            print("ERROR: could not utilise serial library to find connected Arduino "
                  "(for given device: %s) just try the serial device (eg: /dev/ttyACM0)" % value)
            raise
        if len(comports) == 1:
            # exchange serial number for serial device Arduino is connected to
            return comports[0]
        else:
            raise argparse.ArgumentTypeError("could not find Arduino from '%s', just try the serial device (eg: /dev/ttyACM0)" % value)

    if value is None:
        comport = _safe_comport_wrapper(lambda cp: True) # all
        value = comport.device
    elif re.search(r'^[0-9a-f]{15,25}$', value, re.IGNORECASE):
        comport = _safe_comport_wrapper(lambda cp: cp.serial_number.upper() == value.upper())
        value = comport.device

    return value
