import curio
import logger
import device

TCP_PIN_R = 14
TCP_PIN_G = 7
TCP_PIN_B = 6

# USB0 Radio
# USB1 GPS
# USB2 Wind
# USB3 Seatalk


async def main():
    logger.info("Starting...")
    #st = seatalk.SeatalkDevice("Seatalk", port="COM10")
    st = device.FileDevice("./logs/example_gps_dump.log")
    await st.initialize()
    while 1:
        nmea_sentence = await st.get_nmea_sentence()
        if nmea_sentence:
            logger.info(nmea_sentence)


curio.run(main)