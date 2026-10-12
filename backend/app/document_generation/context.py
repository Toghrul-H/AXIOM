from dataclasses import dataclass
from datetime import date as CalendarDate, time
from app.assessment_schemas import ConfigurationDetail
from app.assessment_policy_schemas import PolicyRead, SubmissionDeadline, RulesRead

@dataclass(frozen=True)
class RoomAssignmentContext:
    room: str
    practice_groups: tuple[str, ...]

@dataclass(frozen=True)
class EventDocumentContext:
    event_type: str
    date: CalendarDate | None = None
    start_time: time | None = None
    end_time: time | None = None
    writing_start_time: time | None = None
    writing_end_time: time | None = None
    latest_arrival_time: time | None = None
    document_date: CalendarDate | None = None
    venue: str | None = None
    notes: str | None = None
    seating_plan: str | None = None
    submission_deadline_date: CalendarDate | None = None
    submission_deadline_time: time | None = None
    submission_venue: str | None = None
    submission_instructions: str | None = None
    group_deadlines: tuple[SubmissionDeadline, ...] = ()
    rooms: tuple[RoomAssignmentContext, ...] = ()

@dataclass(frozen=True)
class SemesterDocumentContext:
    academic_year_start: int
    term: str
    display_label: str
    events: tuple[EventDocumentContext, ...]

    policies: tuple[PolicyRead, ...] = ()
    rules: RulesRead | None = None

    def policy(self, code: str) -> PolicyRead:
        return next((policy for policy in self.policies if policy.code == code), PolicyRead(code=code))

    def event(self, kind: str) -> EventDocumentContext:
        return next((event for event in self.events if event.event_type == kind), EventDocumentContext(kind))

def build_context(configuration: ConfigurationDetail) -> SemesterDocumentContext:
    events = []
    for event in sorted(configuration.events, key=lambda item: item.event_type):
        fields = event.model_dump(exclude={'id', 'created_at', 'updated_at', 'last_modified_by_id', 'rooms', 'group_deadlines'})
        rooms = tuple(sorted((RoomAssignmentContext(room.room, tuple(sorted(group.identifier for group in room.groups)))
                              for room in event.rooms), key=lambda item: (item.room, item.practice_groups)))
        events.append(EventDocumentContext(**fields, rooms=rooms, group_deadlines=tuple(event.group_deadlines)))
    rules = RulesRead.model_validate(configuration.model_dump(include=set(RulesRead.model_fields)))
    return SemesterDocumentContext(configuration.academic_year_start, configuration.term, configuration.display_label, tuple(events), tuple(configuration.policies), rules)
