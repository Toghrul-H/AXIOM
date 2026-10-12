from datetime import date, time
from dataclasses import replace
import pytest
from app.document_generation.context import SemesterDocumentContext, EventDocumentContext, RoomAssignmentContext
from app.document_generation.latex import escape, format_date, format_time, writing_times
from app.document_generation.service import DocumentType, render_context
from app.assessment_policy_schemas import PolicyRead, SubmissionDeadline

@pytest.fixture
def context():
    event = EventDocumentContext('ENDTERM', date=date(2027, 5, 19), start_time=time(10), end_time=time(12),
        writing_start_time=time(10, 15), writing_end_time=time(11, 45), latest_arrival_time=time(10, 5),
        document_date=date(2027, 5, 10), notes='Private note never printed',
        rooms=(RoomAssignmentContext('Room B', ('lab-A', '42')), RoomAssignmentContext('Room A', ('7', '1'))))
    return SemesterDocumentContext(2026, 'SPRING', 'Spring 2026/27', (event,))

def test_render_documents_intervals_arrival_and_stable_prose(context):
    dates = render_context(context, DocumentType.DATES_OF_ASSESSMENTS)
    endterm = render_context(context, DocumentType.ENDTERM_TEST_INFORMATION)
    assert 'Spring 2026/27' in dates and 'Spring 2024/25' not in dates
    assert '10:00--12:00' in dates and '10:15--11:45' not in dates
    assert '10:15--11:45' in endterm and '10:00--12:00' not in endterm
    assert endterm.count('Please arrive by 10:05 the latest.') == 2
    assert '16:05' not in endterm and '2025' not in dates + endterm
    assert '19 May 2027 (Wednesday)' in endterm
    assert 'Retake of short quizzes' in dates
    assert 'at least 16 points' not in dates and '90 minutes' not in endterm
    assert 'Private note' not in endterm + dates
    for result in [dates, endterm]:
        assert result.startswith(r'\documentclass') and result.rstrip().endswith(r'\end{document}')
        assert '@@' not in result and 'None' not in result and 'null' not in result
    assert render_context(context, DocumentType.ENDTERM_TEST_INFORMATION) == endterm
    assert endterm.index('Room A') < endterm.index('Room B')
    assert 'Practice groups 1, 7' in endterm and '42, lab-A' in endterm

def test_missing_data_and_fallbacks(context):
    empty = replace(context, events=())
    assert 'to be announced' in render_context(empty, DocumentType.DATES_OF_ASSESSMENTS)
    with pytest.raises(ValueError, match='Configure an Endterm'):
        render_context(empty, DocumentType.ENDTERM_TEST_INFORMATION)
    scheduled_only = replace(context.events[0], writing_start_time=None, writing_end_time=None, rooms=(), latest_arrival_time=None)
    text = render_context(replace(context, events=(scheduled_only,)), DocumentType.ENDTERM_TEST_INFORMATION)
    assert '10:00--12:00' in text and 'Venue: to be announced.' in text
    assert 'Room assignments will be announced later.' in text
    assert text.count('The latest required arrival time will be announced later.') == 2
    partial = replace(scheduled_only, writing_start_time=time(11))
    assert writing_times(partial) == (time(11), None)

def test_latex_escaping_and_one_pass_interpolation(context):
    hostile = r'\input{secret} # $ % & _ ~ ^ ^^41'
    escaped = escape(hostile)
    assert r'\input{secret}' not in escaped
    for literal in [r'\textbackslash{}', r'\{', r'\}', r'\#', r'\$', r'\%', r'\&', r'\_', r'\textasciitilde{}', r'\textasciicircum{}']:
        assert literal in escaped
    event = replace(context.events[0], venue=hostile, rooms=(RoomAssignmentContext(hostile, (hostile,)),))
    result = render_context(replace(context, events=(event,)), DocumentType.ENDTERM_TEST_INFORMATION)
    assert escaped in result and r'\input{secret}' not in result
    marker = render_context(replace(context, display_label='@@SEMESTER@@'), DocumentType.DATES_OF_ASSESSMENTS)
    assert '@@SEMESTER@@' in marker  # Input is never interpreted a second time.

def test_formatting():
    assert format_date(date(2025, 5, 19)) == '19 May 2025 (Monday)'
    assert format_time(time(10, 15)) == '10:15'
    assert format_time(time(10, 15, 30)) == '10:15:30'

def test_shared_policies_submission_overrides_and_escaping(context):
    policy = PolicyRead(code='ENDTERM', topics='Graphs & counting', duration_minutes=75,
        maximum_score='35.5', passing_score='14', assessment_mode='Written',
        permitted_equipment='Pen only', conduct_instructions='Before: bring ID.\nAfter: await feedback.')
    hand_in = EventDocumentContext('COURSEWORK_HAND_IN', submission_deadline_date=date(2027,5,1),
        submission_deadline_time=time(10), submission_venue='General room',
        group_deadlines=(SubmissionDeadline(group_identifier='Group_B', deadline_date=date(2027,5,2)),
                         SubmissionDeadline(group_identifier='Group A', venue=r'\input{bad}')))
    context = replace(context, events=(*context.events, hand_in), policies=(policy,))
    dates = render_context(context, DocumentType.DATES_OF_ASSESSMENTS)
    detail = render_context(context, DocumentType.ENDTERM_TEST_INFORMATION)
    for result in (dates, detail):
        assert 'Graphs \\& counting' in result and '75 minutes' in result and '35.5' in result
    assert '2 May 2027' in dates and 'General room' in dates and '10:00' in dates
    assert dates.index('Group A') < dates.index(r'Group\_B')
    assert r'\input{bad}' not in dates and escape(r'\input{bad}') in dates
    assert 'Before: bring ID.' in detail and 'After: await feedback.' in detail
