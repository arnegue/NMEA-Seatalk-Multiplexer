import curio
import logger
import device
import device_io

TCP_PIN_R = 14
TCP_PIN_G = 7
TCP_PIN_B = 6

# USB0 Radio
# USB1 GPS
# USB2 Wind
# USB3 Seatalk


async def test_file():
    file = device_io.File("logs/example_gps_dump.log")
    for i in range(3):
        r = await file.read(2)
        print(r)


async def test_serial():
    serial = device_io.Serial("COM2")
    for i in range(5):
        r = await serial.read(2)
        print(r)


async def main():
    await test_serial()
    return
    logger.info("Starting...")
    #st = seatalk.SeatalkDevice("Seatalk", port="COM10")
    st = device.FileDevice("./logs/example_gps_dump.log")
    await st.initialize()
    while 1:
        nmea_sentence = await st.get_nmea_sentence()
        if nmea_sentence:
            logger.info(nmea_sentence)


curio.run(main)