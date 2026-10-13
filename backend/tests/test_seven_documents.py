from dataclasses import replace
from datetime import date, time
import pytest
from app.assessment_policy_schemas import PolicyRead, RulesRead, SubmissionDeadline, GradeBoundary
from app.document_generation.context import SemesterDocumentContext, EventDocumentContext, RoomAssignmentContext
from app.document_generation.service import DocumentType, render_context
from app.document_generation.latex import escape

@pytest.fixture
def semester():
    events = tuple(EventDocumentContext(kind, date=date(2031,5,20), start_time=time(9), end_time=time(12),
        writing_start_time=time(9,15), writing_end_time=time(10,45), latest_arrival_time=time(9,5),
        venue='Campus & Hall', seating_plan='Alternate columns',
        rooms=(RoomAssignmentContext('Room_Z',('G&1',)),)) for kind in ('MIDTERM','ENDTERM','TEST_RETAKE'))
    hand_in=EventDocumentContext('COURSEWORK_HAND_IN',submission_deadline_date=date(2031,5,1),
        submission_deadline_time=time(11),submission_venue='General hall',
        group_deadlines=(SubmissionDeadline(group_identifier='Tuesday',deadline_date=date(2031,5,2)),
            SubmissionDeadline(group_identifier='Thursday',deadline_time=time(14),venue='Lab_B')))
    policies=tuple(PolicyRead(code=code,topics=f'{code} topic & proof',maximum_score=maximum,
        passing_score=maximum/2,duration_minutes=duration,permitted_equipment='Pencil & ruler',
        conduct_instructions='Before: bring ID.\nAfter: await feedback.',
        preparation_instructions='Question 1: show calculation steps.', retake_rules='Submit to replace the original score.')
        for code,maximum,duration in [('MIDTERM',42,70),('ENDTERM',56,95),('COURSEWORK',24,120),('SHORT_QUIZZES',18,8)])
    rules=RulesRead(course_topics='Semester syllabus',attendance_rules='Attendance policy',
        total_score_rules='Pass components before adding plus points',plus_points_maximum='12.5',
        plus_points_rules='Homework: 0.5 points; coding: follow published deadline.',maximum_total_score='152.5',
        grade_boundaries=[GradeBoundary(grade=i+1,minimum_score=value) for i,value in enumerate([0,50,70,90,110])])
    return SemesterDocumentContext(2030,'SPRING','Spring 2030/31',(*events,hand_in),policies,rules)

@pytest.mark.parametrize('kind',list(DocumentType))
def test_all_seven_render_and_missing_fields(semester,kind):
    output=render_context(semester,kind)
    assert output.startswith(r'\documentclass') and output.rstrip().endswith(r'\end{document}')
    assert '@@' not in output and 'None' not in output and 'null' not in output
    empty=replace(semester,events=(EventDocumentContext('ENDTERM'),),policies=(),rules=None)
    output=render_context(empty,kind)
    assert 'to be announced' in output
    for historical in ('2025','2026','16:05','12:05','0-821','90 minutes','40 points','penultimate class'):
        assert historical not in output

@pytest.mark.parametrize('kind', [DocumentType.MIDTERM_TEST_INFORMATION,DocumentType.TEST_RETAKE_INFORMATION])
def test_writing_arrival_rooms_and_partial_fallback(semester,kind):
    output=render_context(semester,kind)
    assert '09:15--10:45' in output and '09:00--12:00' not in output
    assert output.count('Please arrive by 09:05 the latest.')==2
    assert 'Room\\_Z' in output and 'G\\&1' in output
    events=tuple(replace(e,writing_start_time=None,writing_end_time=None) for e in semester.events)
    assert '09:00--12:00' in render_context(replace(semester,events=events),kind)
    events=tuple(replace(e,writing_start_time=time(10),writing_end_time=None) for e in semester.events)
    assert '10:00--to be announced' in render_context(replace(semester,events=events),kind)

def test_authoritative_scores_and_rules_across_documents(semester):
    outputs={kind:render_context(semester,kind) for kind in DocumentType}
    for kind in (DocumentType.DATES_OF_ASSESSMENTS,DocumentType.ENDTERM_TEST_INFORMATION,DocumentType.TEST_RETAKE_INFORMATION,DocumentType.RULES_OF_ASSESSMENT):
        assert '95 minutes' in outputs[kind] and '56' in outputs[kind]
    assert '70 minutes' in outputs[DocumentType.TEST_RETAKE_INFORMATION]
    for kind in (DocumentType.RULES_OF_ASSESSMENT,DocumentType.RULES_OF_EARNING_PLUS_POINTS):
        assert '12.5' in outputs[kind] and 'Homework: 0.5 points' in outputs[kind]
        assert 'Pass components before adding plus points' in outputs[kind]
    assert '152.5' in outputs[DocumentType.RULES_OF_ASSESSMENT]
    assert r'110 & 5\\' in outputs[DocumentType.RULES_OF_ASSESSMENT]
    changed=replace(semester,policies=tuple(p.model_copy(update={'duration_minutes':83}) if p.code=='ENDTERM' else p for p in semester.policies))
    for kind in (DocumentType.DATES_OF_ASSESSMENTS,DocumentType.ENDTERM_TEST_INFORMATION,DocumentType.TEST_RETAKE_INFORMATION,DocumentType.RULES_OF_ASSESSMENT):
        assert '83 minutes' in render_context(changed,kind) and '95 minutes' not in render_context(changed,kind)

@pytest.mark.parametrize('kind',[DocumentType.DATES_OF_ASSESSMENTS,DocumentType.RULES_OF_ASSESSMENT,DocumentType.COURSEWORK_ASSIGNMENT_INFORMATION])
def test_group_deadlines_shared(semester,kind):
    output=render_context(semester,kind)
    assert 'Tuesday: Date: 2 May 2031' in output
    assert 'Thursday: Date: 1 May 2031' in output
    assert 'time: 14:00; submission venue: Lab\\_B' in output
    assert 'time: 11:00; submission venue: General hall' in output

@pytest.mark.parametrize('kind',list(DocumentType))
def test_untrusted_text_is_escaped_in_every_template(semester,kind):
    hostile=r'\input{secret} # $ % & _ ~ ^ ^^41 @@MIDTERM_DATE@@'
    policies=tuple(p.model_copy(update={'topics':hostile,'conduct_instructions':hostile,'preparation_instructions':hostile}) for p in semester.policies)
    rules=semester.rules.model_copy(update={'plus_points_rules':hostile,'attendance_rules':hostile})
    output=render_context(replace(semester,policies=policies,rules=rules),kind)
    assert escape(hostile) in output
    assert r'\input{secret}' not in output
    assert r'@@MIDTERM\_DATE@@' in output  # Escaped user text is never interpolated again.

def test_endterm_arrival_fallback_separates_missing_conduct(semester):
    empty = replace(semester, events=(EventDocumentContext('ENDTERM'),), policies=())
    output = render_context(empty, DocumentType.ENDTERM_TEST_INFORMATION)
    assert 'announced later.\nto be announced' not in output
    assert r'\textbf{Conduct instructions:} to be announced' in output
