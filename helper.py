
def byte_to_str(byte):
    """
    Returns string representation of given byte 0x2A -> "Ox2A"
    :param byte:
    :return:
    """
    if isinstance(byte, int):
        value = byte
    else:
        value = get_numeric_byte_value(byte)
    return '0x%02X ' % value


def bytes_to_str(bytes):
    """
    Returns string representation of given bytes [0x21, 0x2E] -> "0x21 0x2E"
    :param bytes:
    :return:
    """
    byte_str = ""
    for byte in bytes:
        byte_str += byte_to_str(byte)
    return byte_str


def get_numeric_byte_value(byte):
    return int.from_bytes(byte, "big")


class UnitConverter(object):
    @staticmethod
    def meter_to_feet(meter):
        return meter * 3.28084

    @staticmethod
    def feet_to_meter(feet):
        return feet / 3.28084

    @staticmethod
    def meter_to_fathom(meter):
        return meter * 0.54680665

    @staticmethod
    def fathom_to_meter(fathom):
        return fathom / 0.54680665

    @staticmethod
    def meter_to_nm(meter):
        return meter * 0.0005399568

    @staticmethod
    def nm_to_meter(nm):
        return nm / 0.0005399568

