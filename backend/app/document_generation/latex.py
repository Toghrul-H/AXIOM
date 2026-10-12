"""Deterministic presentation helpers. Dynamic strings are always plain text."""
from datetime import date, time
from app.document_generation.context import EventDocumentContext

TO_BE_ANNOUNCED = 'to be announced'
ROOMS_PENDING = 'Room assignments will be announced later.'
MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December')
WEEKDAYS = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
ESCAPES = {'\\': r'\textbackslash{}', '{': r'\{', '}': r'\}', '#': r'\#', '$': r'\$', '%': r'\%', '&': r'\&', '_': r'\_', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}

def escape(value: str) -> str:
    # Strip control characters, including TeX's ^^ notation via escaped carets.
    return ''.join(ESCAPES.get(char, char) if ord(char) >= 32 and ord(char) != 127 else ' ' for char in value)

def format_date(value: date | None) -> str:
    if value is None:
        return TO_BE_ANNOUNCED
    return f'{value.day} {MONTHS[value.month - 1]} {value.year} ({WEEKDAYS[value.weekday()]})'

def format_time(value: time | None) -> str:
    if value is None:
        return TO_BE_ANNOUNCED
    return value.strftime('%H:%M:%S' if value.second else '%H:%M')

def interval(start: time | None, end: time | None) -> str:
    if start is None and end is None:
        return TO_BE_ANNOUNCED
    return f'{format_time(start)}--{format_time(end)}'

def writing_times(event: EventDocumentContext) -> tuple[time | None, time | None]:
    # Only fall back when the entire writing interval is absent; do not synthesize
    # a contradictory interval by mixing partially configured writing/schedule times.
    if event.writing_start_time is None and event.writing_end_time is None:
        return event.start_time, event.end_time
    return event.writing_start_time, event.writing_end_time

def venue(event: EventDocumentContext) -> str:
    return escape(event.venue.strip()) if event.venue and event.venue.strip() else TO_BE_ANNOUNCED

def rooms(event: EventDocumentContext) -> str:
    if not event.rooms:
        return ROOMS_PENDING
    lines = [r'\begin{itemize}']
    for room in sorted(event.rooms, key=lambda item: (item.room, item.practice_groups)):
        groups = ', '.join(escape(group) for group in sorted(room.practice_groups))
        lines.append(r'\item Practice groups ' + groups + ' will be in room ' + escape(room.room) + '.')
    return '\n'.join(lines + [r'\end{itemize}'])
