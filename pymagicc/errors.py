class NoReaderWriterError(ValueError):
    """Exception raised when a valid Reader or Writer could not be found for the file"""

    pass


class InvalidTemporalResError(ValueError):
    """Exception raised when a file has a temporal resolution which cannot be processed"""

    pass
