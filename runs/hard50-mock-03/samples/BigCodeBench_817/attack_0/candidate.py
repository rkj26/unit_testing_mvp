    formatter = logging.Formatter('%(levelname)s:%(message)s')
    handler = logging.FileHandler(log_path + '/task_func.log', mode='w')
    logger = logging.getLogger()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.info(f"Function called with list: {letter_list} and element: {element}")

    if element not in letter_list:
        logger.error("The element is not in the letter list.")
        logger.handlers[0].close
        logger.removeHandler(logger.handlers[0])
        logging.shutdown()

        raise ValueError("The element is not in the letter list.")

    # Normalize casing so that a letter is counted regardless of how it is cased.
    letter_frequencies = Counter(letter.lower() for letter in letter_list)
    element_frequency = letter_frequencies[element.lower()]

    logger.info(f"Frequency of '{element}' is {element_frequency}")
    logger.handlers[0].close
    logger.removeHandler(logger.handlers[0])
    logging.shutdown()

    return element_frequency
