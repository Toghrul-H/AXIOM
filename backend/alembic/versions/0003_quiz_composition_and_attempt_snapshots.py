"""quiz composition and attempt snapshots

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Additive quiz schema; existing Question Bank data is untouched.
    op.create_table('quizzes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), server_default='DRAFT', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('DRAFT','ACTIVE','INACTIVE')", name='ck_quizzes_status'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quizzes_status'), 'quizzes', ['status'], unique=False)
    op.create_table('quiz_attempts',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('quiz_id', sa.Integer(), nullable=False),
    sa.Column('development_session_id', sa.Uuid(), nullable=False),
    sa.Column('quiz_title', sa.String(length=200), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='IN_PROGRESS', nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('objective_score', sa.Integer(), nullable=True),
    sa.Column('objective_total', sa.Integer(), nullable=False),
    sa.CheckConstraint("(status = 'IN_PROGRESS' AND submitted_at IS NULL AND objective_score IS NULL) OR (status = 'SUBMITTED' AND submitted_at IS NOT NULL AND objective_score IS NOT NULL)", name='ck_quiz_attempts_submission'),
    sa.CheckConstraint("status IN ('IN_PROGRESS','SUBMITTED')", name='ck_quiz_attempts_status'),
    sa.CheckConstraint('objective_score IS NULL OR (objective_score >= 0 AND objective_score <= objective_total)', name='ck_quiz_attempts_score'),
    sa.ForeignKeyConstraint(['quiz_id'], ['quizzes.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quiz_attempts_development_session_id'), 'quiz_attempts', ['development_session_id'], unique=False)
    op.create_index(op.f('ix_quiz_attempts_quiz_id'), 'quiz_attempts', ['quiz_id'], unique=False)
    op.create_table('attempt_answers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('quiz_attempt_id', sa.Uuid(), nullable=False),
    sa.Column('question_id', sa.Integer(), nullable=True),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('points', sa.Integer(), nullable=False),
    sa.Column('question_text', sa.Text(), nullable=False),
    sa.Column('response_type', sa.String(length=40), nullable=False),
    sa.Column('expected_answer', sa.Text(), nullable=True),
    sa.Column('correct_boolean', sa.Boolean(), nullable=True),
    sa.Column('explanation', sa.Text(), nullable=True),
    sa.Column('selected_option_ids', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('boolean_answer', sa.Boolean(), nullable=True),
    sa.Column('free_response', sa.Text(), nullable=True),
    sa.Column('is_correct', sa.Boolean(), nullable=True),
    sa.Column('points_awarded', sa.Integer(), nullable=True),
    sa.CheckConstraint('points_awarded IS NULL OR (points_awarded >= 0 AND points_awarded <= points)', name='ck_attempt_answers_awarded'),
    sa.CheckConstraint('position >= 0 AND points > 0', name='ck_attempt_answers_position_points'),
    sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['quiz_attempt_id'], ['quiz_attempts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('quiz_attempt_id', 'position', name='uq_attempt_answers_position')
    )
    op.create_index(op.f('ix_attempt_answers_question_id'), 'attempt_answers', ['question_id'], unique=False)
    op.create_index(op.f('ix_attempt_answers_quiz_attempt_id'), 'attempt_answers', ['quiz_attempt_id'], unique=False)
    op.create_table('quiz_questions',
    sa.Column('quiz_id', sa.Integer(), nullable=False),
    sa.Column('question_id', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('points', sa.Integer(), nullable=False),
    sa.CheckConstraint('points > 0 AND points <= 1000', name='ck_quiz_questions_points'),
    sa.CheckConstraint('position >= 0', name='ck_quiz_questions_position'),
    sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['quiz_id'], ['quizzes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('quiz_id', 'question_id'),
    sa.UniqueConstraint('quiz_id', 'position', deferrable=True, initially='DEFERRED', name='uq_quiz_questions_position')
    )
    op.create_index(op.f('ix_quiz_questions_question_id'), 'quiz_questions', ['question_id'], unique=False)
    op.create_table('attempt_options',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('attempt_answer_id', sa.Integer(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('is_correct', sa.Boolean(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['attempt_answer_id'], ['attempt_answers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('attempt_answer_id', 'position', name='uq_attempt_options_position')
    )
    op.create_index(op.f('ix_attempt_options_attempt_answer_id'), 'attempt_options', ['attempt_answer_id'], unique=False)



def downgrade() -> None:
    # Destructive: removes quizzes and historical attempts, not bank data.
    op.drop_index(op.f('ix_attempt_options_attempt_answer_id'), table_name='attempt_options')
    op.drop_table('attempt_options')
    op.drop_index(op.f('ix_quiz_questions_question_id'), table_name='quiz_questions')
    op.drop_table('quiz_questions')
    op.drop_index(op.f('ix_attempt_answers_quiz_attempt_id'), table_name='attempt_answers')
    op.drop_index(op.f('ix_attempt_answers_question_id'), table_name='attempt_answers')
    op.drop_table('attempt_answers')
    op.drop_index(op.f('ix_quiz_attempts_quiz_id'), table_name='quiz_attempts')
    op.drop_index(op.f('ix_quiz_attempts_development_session_id'), table_name='quiz_attempts')
    op.drop_table('quiz_attempts')
    op.drop_index(op.f('ix_quizzes_status'), table_name='quizzes')
    op.drop_table('quizzes')


