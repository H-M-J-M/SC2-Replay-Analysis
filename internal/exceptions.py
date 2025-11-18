class EssentialDataMissingError(KeyError):
    """
    Raised when a replay bundle is missing an essential data key (e.g., 'units', 'resources'). Typically indicates a missing file.
    """
    pass
