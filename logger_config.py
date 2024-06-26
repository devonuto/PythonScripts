import logging
import os

def setup_custom_logger(name):
    formatter = logging.Formatter(fmt='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

     # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Create file handler which logs even debug messages
    file_handler = logging.FileHandler(os.path.join(script_dir, name + '.log'))
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger