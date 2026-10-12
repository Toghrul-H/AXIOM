"""Shared semester policies and group-specific submission deadlines.

Revision ID: 0012
Revises: 0011
"""
from alembic import op
import sqlalchemy as sa

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None

def upgrade():
    for name in ('course_topics','attendance_rules','total_score_rules','plus_points_rules'):
        op.add_column('assessment_configurations', sa.Column(name, sa.Text(), nullable=True))
    op.add_column('assessment_configurations', sa.Column('plus_points_maximum', sa.Numeric(8,2), nullable=True))
    op.create_check_constraint('ck_assessment_plus_maximum', 'assessment_configurations', 'plus_points_maximum BETWEEN 0 AND 100000')
    for name, type_ in [('seating_plan',sa.Text()),('submission_deadline_date',sa.Date()),('submission_deadline_time',sa.Time()),('submission_venue',sa.String(200)),('submission_instructions',sa.Text())]:
        op.add_column('assessment_events', sa.Column(name, type_, nullable=True))
    op.create_table('assessment_policies',
        sa.Column('configuration_id',sa.Integer(),sa.ForeignKey('assessment_configurations.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('code',sa.String(20),primary_key=True),
        *[sa.Column(name,sa.Text(),nullable=True) for name in ('topics','assessment_mode','duration_description','success_criteria','permitted_equipment','retake_rules','conduct_instructions','preparation_instructions')],
        sa.Column('duration_minutes',sa.Integer(),nullable=True),
        sa.Column('assessment_count',sa.Integer(),nullable=True),
        sa.Column('maximum_score',sa.Numeric(8,2),nullable=True),
        sa.Column('passing_score',sa.Numeric(8,2),nullable=True),
        sa.CheckConstraint("code IN ('SHORT_QUIZZES','MIDTERM','ENDTERM','COURSEWORK')",name='ck_assessment_policy_code'),
        sa.CheckConstraint('maximum_score BETWEEN 0 AND 100000',name='ck_policy_maximum'),
        sa.CheckConstraint('passing_score BETWEEN 0 AND 100000 AND (maximum_score IS NULL OR passing_score <= maximum_score)',name='ck_policy_passing'),
        sa.CheckConstraint('duration_minutes BETWEEN 1 AND 10080',name='ck_policy_duration'),
        sa.CheckConstraint('assessment_count BETWEEN 1 AND 1000',name='ck_policy_count'))
    op.create_table('assessment_grade_boundaries',
        sa.Column('configuration_id',sa.Integer(),sa.ForeignKey('assessment_configurations.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('grade',sa.Integer(),primary_key=True),
        sa.Column('minimum_score',sa.Numeric(8,2),nullable=False),
        sa.CheckConstraint('grade BETWEEN 1 AND 5',name='ck_assessment_grade'),
        sa.CheckConstraint('minimum_score BETWEEN 0 AND 100000',name='ck_assessment_grade_minimum'),
        sa.UniqueConstraint('configuration_id','minimum_score',name='uq_assessment_grade_threshold'))
    op.create_table('assessment_group_deadlines',
        sa.Column('event_id',sa.Integer(),sa.ForeignKey('assessment_events.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('group_identifier',sa.String(50),primary_key=True),
        sa.Column('deadline_date',sa.Date(),nullable=True),
        sa.Column('deadline_time',sa.Time(),nullable=True),
        sa.Column('venue',sa.String(200),nullable=True),
        sa.Column('instructions',sa.Text(),nullable=True),
        sa.CheckConstraint('length(trim(group_identifier)) > 0',name='ck_deadline_group'))

def downgrade():
    for table in ('assessment_group_deadlines','assessment_grade_boundaries','assessment_policies'):
        op.drop_table(table)
    for name in ('seating_plan','submission_deadline_date','submission_deadline_time','submission_venue','submission_instructions'):
        op.drop_column('assessment_events',name)
    op.drop_constraint('ck_assessment_plus_maximum','assessment_configurations',type_='check')
    for name in ('course_topics','attendance_rules','total_score_rules','plus_points_rules','plus_points_maximum'):
        op.drop_column('assessment_configurations',name)
