from enum import Enum
from pathlib import Path
import re
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.assessment_models import AssessmentConfiguration, EVENT_KINDS
from app.assessment_schemas import ConfigurationDetail
from app.auth_models import User
from app.document_generation.context import SemesterDocumentContext, build_context
from app.document_generation.latex import escape, format_date, format_time, interval, writing_times, venue, rooms, TO_BE_ANNOUNCED

class DocumentType(str, Enum):
    DATES_OF_ASSESSMENTS = 'DATES_OF_ASSESSMENTS'
    ENDTERM_TEST_INFORMATION = 'ENDTERM_TEST_INFORMATION'
    RULES_OF_ASSESSMENT = 'RULES_OF_ASSESSMENT'
    RULES_OF_EARNING_PLUS_POINTS = 'RULES_OF_EARNING_PLUS_POINTS'
    MIDTERM_TEST_INFORMATION = 'MIDTERM_TEST_INFORMATION'
    TEST_RETAKE_INFORMATION = 'TEST_RETAKE_INFORMATION'
    COURSEWORK_ASSIGNMENT_INFORMATION = 'COURSEWORK_ASSIGNMENT_INFORMATION'

TEMPLATES = {
    DocumentType.DATES_OF_ASSESSMENTS: 'dates_of_assessments.tex',
    DocumentType.ENDTERM_TEST_INFORMATION: 'endterm_test_information.tex',
    DocumentType.RULES_OF_ASSESSMENT: 'rules_of_assessment.tex',
    DocumentType.RULES_OF_EARNING_PLUS_POINTS: 'rules_of_earning_plus_points.tex',
    DocumentType.MIDTERM_TEST_INFORMATION: 'midterm_test_information.tex',
    DocumentType.TEST_RETAKE_INFORMATION: 'test_retake_information.tex',
    DocumentType.COURSEWORK_ASSIGNMENT_INFORMATION: 'coursework_assignment_information.tex',
}

def plain(value) -> str:
    return r'\newline '.join(escape(line) for line in str(value).splitlines()) if value is not None else TO_BE_ANNOUNCED


def submission(event) -> str:
    # Legacy hand-in date/start/venue remain a rendering fallback, not copied data.
    date = event.submission_deadline_date or event.date
    time = event.submission_deadline_time or event.start_time
    venue_value = event.submission_venue or event.venue
    def detail(date, time, venue_value, instructions):
        return 'Date: ' + format_date(date) + '; time: ' + format_time(time) + '; submission venue: ' + plain(venue_value) + ('. ' + plain(instructions) if instructions else '')
    base = detail(date, time, venue_value, event.submission_instructions)
    if not event.group_deadlines:
        return base
    rows = [r'\item ' + plain(row.group_identifier) + ': ' + detail(row.deadline_date or date, row.deadline_time or time, row.venue or venue_value, row.instructions or event.submission_instructions) for row in sorted(event.group_deadlines, key=lambda r:r.group_identifier)]
    return base + r'\begin{itemize}' + '\n'.join(rows) + r'\end{itemize}'


def render_context(context: SemesterDocumentContext, document_type: DocumentType) -> str:
    if document_type == DocumentType.ENDTERM_TEST_INFORMATION and not any(e.event_type == 'ENDTERM' for e in context.events):
        raise ValueError('Configure an Endterm event before rendering Endterm test information')
    values = {'SEMESTER': escape(context.display_label)}
    for kind in EVENT_KINDS:
        event = context.event(kind)
        values[kind + '_DATE'] = format_date(event.date)
        values[kind + '_TIME'] = interval(event.start_time, event.end_time)
        values[kind + '_START'] = format_time(event.start_time)
        values[kind + '_VENUE'] = venue(event)
        start, end = writing_times(event)
        values[kind + '_DOCUMENT_DATE'] = format_date(event.document_date)
        values[kind + '_WRITING_TIME'] = interval(start, end)
        values[kind + '_ROOMS'] = rooms(event)
        values[kind + '_SEATING'] = plain(event.seating_plan)
        values[kind + '_ARRIVAL_SENTENCE'] = ('Please arrive by ' + format_time(event.latest_arrival_time) + ' the latest.'
            if event.latest_arrival_time else 'The latest required arrival time will be announced later.')
        values[kind + '_WRITING_SENTENCE'] = ' '.join([
            ('Writing starts at ' + format_time(start) + '.') if start else 'The writing start time will be announced later.',
            ('Writing finishes at ' + format_time(end) + '.') if end else 'The writing end time will be announced later.',
        ])
    # Policies are shared by documents, never silently copied from a reference semester.
    for code in ('SHORT_QUIZZES','MIDTERM','ENDTERM','COURSEWORK'):
        policy = context.policy(code)
        for field in ('topics','assessment_mode','success_criteria','permitted_equipment','retake_rules','preparation_instructions','conduct_instructions'):
            values[code + '_' + field.upper()] = plain(getattr(policy, field))
        values[code + '_MAXIMUM_SCORE'] = plain(policy.maximum_score)
        values[code + '_PASSING_SCORE'] = plain(policy.passing_score)
        values[code + '_COUNT'] = plain(policy.assessment_count)
        values[code + '_DURATION'] = (plain(policy.duration_minutes) + ' minutes') if policy.duration_minutes is not None else plain(policy.duration_description)
    for kind in ('COURSEWORK_HAND_IN','COURSEWORK_RETAKE_HAND_IN'):
        values[kind + '_SUBMISSION'] = submission(context.event(kind))
    values['COURSEWORK_DEADLINE'] = submission(context.event('COURSEWORK_HAND_IN'))
    values['COURSEWORK_RETAKE_PUBLICATION_DEADLINE'] = format_date(context.event('COURSEWORK_RETAKE_PUBLICATION').date)
    rules = context.rules
    for field in ('course_topics', 'attendance_rules', 'total_score_rules', 'plus_points_maximum', 'plus_points_rules', 'maximum_total_score'):
        values[field.upper()] = plain(getattr(rules, field, None))
    if rules and rules.grade_boundaries:
        rows = sorted(rules.grade_boundaries, key=lambda row: row.grade)
        values['GRADE_BOUNDARIES'] = '\n'.join([
            r'\begin{tabular}{ll}\textbf{Minimum total score (inclusive)} & \textbf{Practice grade}\\',
            *(plain(row.minimum_score) + ' & ' + str(row.grade) + r'\\' for row in reversed(rows)),
            r'\end{tabular}',
            'Each range ends at the next grade threshold (exclusive); course-passing conditions also apply.',
        ])
    else:
        values['GRADE_BOUNDARIES'] = 'Grade boundaries will be announced later.'
    template = (Path(__file__).parent / 'templates' / TEMPLATES[document_type]).read_text(encoding='utf-8')
    # Fixed markers only, one pass; replacement strings cannot become new markers.
    return re.sub(r'@@([A-Z_]+)@@', lambda match: values[match.group(1)], template)

def render_document(session: Session, configuration_id: int, document_type: DocumentType, actor: User) -> str:
    if not actor.is_active or actor.role not in {'LECTURER', 'ADMIN'}:
        raise HTTPException(403, 'Assessment document access denied')
    configuration = session.get(AssessmentConfiguration, configuration_id)
    if configuration is None:
        raise HTTPException(404, 'Assessment configuration not found')
    context = build_context(ConfigurationDetail.model_validate(configuration))
    try:
        return render_context(context, document_type)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
