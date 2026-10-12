"""Semester-variable data, independent of future document template prose."""
from datetime import date as CalendarDate, datetime, time
from decimal import Decimal
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, String, Text, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Numeric
from app.database import Base

EVENT_KINDS = ('MIDTERM', 'ENDTERM', 'SHORT_QUIZ_RETAKE', 'TEST_RETAKE', 'COURSEWORK_PUBLICATION',
               'COURSEWORK_HAND_IN', 'COURSEWORK_RETAKE_PUBLICATION', 'COURSEWORK_RETAKE_HAND_IN')

class AssessmentConfiguration(Base):
    __tablename__ = 'assessment_configurations'
    __table_args__ = (
        UniqueConstraint('academic_year_start', 'term', name='uq_assessment_semester'),
        CheckConstraint('academic_year_start BETWEEN 1900 AND 9998', name='ck_assessment_year'),
        CheckConstraint("term IN ('SPRING','FALL')", name='ck_assessment_term'),
        CheckConstraint("length(trim(display_label)) > 0", name='ck_assessment_label'),
        CheckConstraint('plus_points_maximum BETWEEN 0 AND 100000', name='ck_assessment_plus_maximum'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year_start: Mapped[int]
    term: Mapped[str] = mapped_column(String(10))
    display_label: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_modified_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    events: Mapped[list['AssessmentEvent']] = relationship(cascade='all, delete-orphan', passive_deletes=True, order_by='AssessmentEvent.id')
    course_topics: Mapped[str | None] = mapped_column(Text)
    attendance_rules: Mapped[str | None] = mapped_column(Text)
    total_score_rules: Mapped[str | None] = mapped_column(Text)
    plus_points_maximum: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    plus_points_rules: Mapped[str | None] = mapped_column(Text)
    policies: Mapped[list['AssessmentPolicy']] = relationship(cascade='all, delete-orphan', passive_deletes=True, order_by='AssessmentPolicy.code')
    grade_boundaries: Mapped[list['AssessmentGradeBoundary']] = relationship(cascade='all, delete-orphan', passive_deletes=True, order_by='AssessmentGradeBoundary.grade')

    @property
    def maximum_total_score(self):
        # Component maxima are aggregate (e.g. all short quizzes), never retakes.
        if len(self.policies) != 4 or self.plus_points_maximum is None or any(p.maximum_score is None for p in self.policies):
            return None
        return sum(p.maximum_score for p in self.policies) + self.plus_points_maximum

class AssessmentEvent(Base):
    __tablename__ = 'assessment_events'
    __table_args__ = (
        UniqueConstraint('configuration_id', 'event_type', name='uq_assessment_event_type'),
        CheckConstraint('event_type IN (' + ','.join(repr(k) for k in EVENT_KINDS) + ')', name='ck_assessment_event_type'),
        CheckConstraint('end_time IS NULL OR start_time IS NULL OR end_time > start_time', name='ck_assessment_event_times'),
        CheckConstraint('writing_end_time IS NULL OR writing_start_time IS NULL OR writing_end_time > writing_start_time', name='ck_assessment_writing_times'),
        CheckConstraint('venue IS NULL OR length(trim(venue)) > 0', name='ck_assessment_event_venue'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    configuration_id: Mapped[int] = mapped_column(ForeignKey('assessment_configurations.id', ondelete='CASCADE'))
    event_type: Mapped[str] = mapped_column(String(40))
    date: Mapped[CalendarDate | None] = mapped_column(Date, nullable=True)
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    writing_start_time: Mapped[time | None] = mapped_column(Time)
    writing_end_time: Mapped[time | None] = mapped_column(Time)
    venue: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    document_date: Mapped[CalendarDate | None] = mapped_column(Date, nullable=True)
    latest_arrival_time: Mapped[time | None] = mapped_column(Time)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_modified_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    rooms: Mapped[list['AssessmentRoom']] = relationship(cascade='all, delete-orphan', passive_deletes=True, order_by='AssessmentRoom.id')
    seating_plan: Mapped[str | None] = mapped_column(Text)
    submission_deadline_date: Mapped[CalendarDate | None] = mapped_column(Date)
    submission_deadline_time: Mapped[time | None] = mapped_column(Time)
    submission_venue: Mapped[str | None] = mapped_column(String(200))
    submission_instructions: Mapped[str | None] = mapped_column(Text)
    group_deadlines: Mapped[list['AssessmentGroupDeadline']] = relationship(cascade='all, delete-orphan', passive_deletes=True, order_by='AssessmentGroupDeadline.group_identifier')

class AssessmentPolicy(Base):
    __tablename__ = 'assessment_policies'
    __table_args__ = (
        CheckConstraint("code IN ('SHORT_QUIZZES','MIDTERM','ENDTERM','COURSEWORK')", name='ck_assessment_policy_code'),
        CheckConstraint('maximum_score BETWEEN 0 AND 100000', name='ck_policy_maximum'),
        CheckConstraint('passing_score BETWEEN 0 AND 100000 AND (maximum_score IS NULL OR passing_score <= maximum_score)', name='ck_policy_passing'),
        CheckConstraint('duration_minutes BETWEEN 1 AND 10080', name='ck_policy_duration'),
        CheckConstraint('assessment_count BETWEEN 1 AND 1000', name='ck_policy_count'),
    )
    configuration_id: Mapped[int] = mapped_column(ForeignKey('assessment_configurations.id', ondelete='CASCADE'), primary_key=True)
    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    topics: Mapped[str | None] = mapped_column(Text)
    assessment_mode: Mapped[str | None] = mapped_column(Text)
    duration_minutes: Mapped[int | None]
    duration_description: Mapped[str | None] = mapped_column(Text)
    maximum_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    passing_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    assessment_count: Mapped[int | None]
    success_criteria: Mapped[str | None] = mapped_column(Text)
    permitted_equipment: Mapped[str | None] = mapped_column(Text)
    retake_rules: Mapped[str | None] = mapped_column(Text)
    conduct_instructions: Mapped[str | None] = mapped_column(Text)
    preparation_instructions: Mapped[str | None] = mapped_column(Text)

class AssessmentGradeBoundary(Base):
    __tablename__ = 'assessment_grade_boundaries'
    __table_args__ = (
        CheckConstraint('grade BETWEEN 1 AND 5', name='ck_assessment_grade'),
        CheckConstraint('minimum_score BETWEEN 0 AND 100000', name='ck_assessment_grade_minimum'),
        UniqueConstraint('configuration_id', 'minimum_score', name='uq_assessment_grade_threshold'),
    )
    configuration_id: Mapped[int] = mapped_column(ForeignKey('assessment_configurations.id', ondelete='CASCADE'), primary_key=True)
    grade: Mapped[int] = mapped_column(primary_key=True)
    minimum_score: Mapped[Decimal] = mapped_column(Numeric(8, 2))

class AssessmentGroupDeadline(Base):
    __tablename__ = 'assessment_group_deadlines'
    __table_args__ = (CheckConstraint('length(trim(group_identifier)) > 0', name='ck_deadline_group'),)
    event_id: Mapped[int] = mapped_column(ForeignKey('assessment_events.id', ondelete='CASCADE'), primary_key=True)
    group_identifier: Mapped[str] = mapped_column(String(50), primary_key=True)
    deadline_date: Mapped[CalendarDate | None] = mapped_column(Date)
    deadline_time: Mapped[time | None] = mapped_column(Time)
    venue: Mapped[str | None] = mapped_column(String(200))
    instructions: Mapped[str | None] = mapped_column(Text)

class AssessmentRoom(Base):
    __tablename__ = 'assessment_rooms'
    __table_args__ = (
        UniqueConstraint('event_id', 'room', name='uq_assessment_room_name'),
        UniqueConstraint('event_id', 'id', name='uq_assessment_room_event_id'),
        CheckConstraint('length(trim(room)) > 0', name='ck_assessment_room_name'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey('assessment_events.id', ondelete='CASCADE'))
    room: Mapped[str] = mapped_column(String(200))
    groups: Mapped[list['AssessmentRoomGroup']] = relationship(cascade='all, delete-orphan', passive_deletes=True, order_by='AssessmentRoomGroup.identifier')

class AssessmentRoomGroup(Base):
    __tablename__ = 'assessment_room_groups'
    __table_args__ = (
        ForeignKeyConstraint(['event_id', 'room_id'], ['assessment_rooms.event_id', 'assessment_rooms.id'], ondelete='CASCADE'),
        CheckConstraint('length(trim(identifier)) > 0', name='ck_assessment_group_identifier'),
    )
    # This key also prevents a group being assigned to two rooms of the same event.
    event_id: Mapped[int] = mapped_column(primary_key=True)
    identifier: Mapped[str] = mapped_column(String(50), primary_key=True)
    room_id: Mapped[int] = mapped_column(index=True)
