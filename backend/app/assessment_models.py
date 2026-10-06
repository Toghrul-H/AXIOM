"""Semester-variable data, independent of future document template prose."""
from datetime import date as CalendarDate, datetime, time
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, String, Text, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
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
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year_start: Mapped[int]
    term: Mapped[str] = mapped_column(String(10))
    display_label: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_modified_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    events: Mapped[list['AssessmentEvent']] = relationship(cascade='all, delete-orphan', passive_deletes=True, order_by='AssessmentEvent.id')

class AssessmentEvent(Base):
    __tablename__ = 'assessment_events'
    __table_args__ = (
        UniqueConstraint('configuration_id', 'event_type', name='uq_assessment_event_type'),
        CheckConstraint('event_type IN (' + ','.join(repr(k) for k in EVENT_KINDS) + ')', name='ck_assessment_event_type'),
        CheckConstraint('end_time IS NULL OR start_time IS NULL OR end_time > start_time', name='ck_assessment_event_times'),
        CheckConstraint('venue IS NULL OR length(trim(venue)) > 0', name='ck_assessment_event_venue'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    configuration_id: Mapped[int] = mapped_column(ForeignKey('assessment_configurations.id', ondelete='CASCADE'))
    event_type: Mapped[str] = mapped_column(String(40))
    date: Mapped[CalendarDate | None] = mapped_column(Date, nullable=True)
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    venue: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    document_date: Mapped[CalendarDate | None] = mapped_column(Date, nullable=True)
    latest_arrival_time: Mapped[time | None] = mapped_column(Time)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_modified_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    rooms: Mapped[list['AssessmentRoom']] = relationship(cascade='all, delete-orphan', passive_deletes=True, order_by='AssessmentRoom.id')

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
