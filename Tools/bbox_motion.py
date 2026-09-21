"""Dependency-free motion parsing shared by the live viewer and recorder preview."""
import math


def parse_motion(record):
    """Return (world velocity in m/s, speed in m/s); missing/invalid data is None.

    Legacy records may have no motion. Never display those as stationary. Geometry
    display scaling does not change physical speed. A valid vector is authoritative.
    """
    units = {'m/s': 1.0, 'cm/s': .01, 'km/h': 1 / 3.6}
    factor = units.get(str(record.get('velocity_unit', 'm/s')).strip().lower())
    if factor is None:
        return None, None
    velocity = None
    raw = record.get('velocity')
    if isinstance(raw, dict):
        try:
            values = tuple(float(raw[k]) * factor for k in ('x', 'y', 'z'))
            if all(math.isfinite(v) for v in values):
                velocity = values
        except (KeyError, TypeError, ValueError, OverflowError):
            pass
    if velocity is not None:
        return velocity, math.hypot(*velocity)
    try:
        speed = float(record['speed']) * factor
        return None, speed if math.isfinite(speed) and speed >= 0 else None
    except (KeyError, TypeError, ValueError, OverflowError):
        return None, None


def speed_label(speed):
    return '速度未知' if speed is None else f'{speed:.2f} m/s'
