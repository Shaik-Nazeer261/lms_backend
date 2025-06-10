import datetime

def parse_duration(duration_str):
    """Convert a duration string like 'HH:MM' or 'MM:SS' to a timedelta object."""
    parts = duration_str.split(':')
    parts = [int(p) for p in parts]
    
    if len(parts) == 2:
        minutes, seconds = parts
        return datetime.timedelta(minutes=minutes, seconds=seconds)
    elif len(parts) == 3:
        hours, minutes, seconds = parts
        return datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)
    else:
        return datetime.timedelta()

def format_duration(seconds):
    """Convert seconds to HH:MM:SS format."""
    return str(datetime.timedelta(seconds=seconds))
