from setuptools import setup

setup(
    name='nmea_seatalk_multiplexer',
    version='1.0',
    url='',
    license='',
    author='Frosty',
    author_email='',
    description='', install_requires=['curio>=1.0', 'pyserial',
                                      "contextvars"]  # dependency of curio....
)
