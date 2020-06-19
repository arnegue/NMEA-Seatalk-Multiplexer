
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


a = bytes_to_str(bytearray([0x21, 0x2E]))
print(a)