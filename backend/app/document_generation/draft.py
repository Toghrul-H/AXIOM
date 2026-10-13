"""Read-only drafts use the same validated fields and LaTeX templates as export."""
from pydantic import Field, model_validator
from app.schemas import Schema
from app.assessment_schemas import ConfigurationCreate, EventWrite, RoomWrite
from app.assessment_policy_schemas import PolicyRead, RulesWrite, RulesRead
from app.document_generation.context import SemesterDocumentContext, EventDocumentContext, RoomAssignmentContext

class DraftEvent(EventWrite):
    rooms: list[RoomWrite] = Field(default_factory=list, max_length=500)

    @model_validator(mode='after')
    def unique_rooms(self):
        names = [room.room for room in self.rooms]
        groups = [group for room in self.rooms for group in room.groups]
        if len(set(names)) != len(names) or len(set(groups)) != len(groups):
            raise ValueError('Rooms and practice group assignments must be unique within an event')
        return self

class DraftWrite(Schema):
    metadata: ConfigurationCreate
    events: list[DraftEvent] = Field(default_factory=list, max_length=8)
    policies: list[PolicyRead] = Field(default_factory=list, max_length=4)
    rules: RulesWrite | None = None

    @model_validator(mode='after')
    def unique_components(self):
        if len({e.event_type for e in self.events}) != len(self.events) or len({p.code for p in self.policies}) != len(self.policies):
            raise ValueError('Duplicate draft event or policy')
        return self

    def context(self, saved_rules: RulesRead):
        # No ORM mutation, flush, commit or saving of draft content.
        rules = self.rules or saved_rules
        total = None
        if len(self.policies) == 4 and rules.plus_points_maximum is not None and all(p.maximum_score is not None for p in self.policies):
            total = sum(p.maximum_score for p in self.policies) + rules.plus_points_maximum
        if total is not None and any(b.minimum_score > total for b in rules.grade_boundaries):
            raise ValueError('A grade threshold exceeds the draft maximum total score')
        rule_values = rules.model_dump(exclude={'maximum_total_score'})
        events = tuple(EventDocumentContext(
            **e.model_dump(exclude={'rooms', 'group_deadlines'}),
            group_deadlines=tuple(e.group_deadlines),
            rooms=tuple(RoomAssignmentContext(r.room, tuple(r.groups)) for r in e.rooms),
        ) for e in self.events)
        return SemesterDocumentContext(self.metadata.academic_year_start, self.metadata.term,
            self.metadata.display_label, events, tuple(self.policies), RulesRead(**rule_values, maximum_total_score=total))
