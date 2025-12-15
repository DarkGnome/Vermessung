from pathlib import Path

# Configuration for the activity log application.

# List of employees available in the dropdown. Adjust as needed.
EMPLOYEES = [
    "Anna",
    "Benedikt",
    "Carla",
    "Dieter",
    "Elena",
]

# Supported activities for the log.
ACTIVITIES = [
    "freie",
    "Aufmaß",
    "Absteckung",
    "Absteckdaten",
    "Bestandsplan",
    "Sonstiges",
]

# Allowed time share values (fractions of a workday).
TIME_SHARES = [round(i / 10, 1) for i in range(1, 11)]

# Name of the data directory that will be created under the OneDrive folder.
DATA_DIR_NAME = "TBC"

# Database and export filenames.
DB_FILENAME = "activity_log.db"
EXPORT_FILENAME = "activity_log_export.csv"


def fallback_home_dir() -> Path:
    """Return a fallback directory under the user's home folder."""
    return Path.home() / DATA_DIR_NAME
