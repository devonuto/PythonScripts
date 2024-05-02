import logging

def setup_custom_logger(name):
    formatter = logging.Formatter(fmt='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG)

    # Create file handler which logs even debug messages
    file_handler = logging.FileHandler(name + '.log')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.WARNING)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger