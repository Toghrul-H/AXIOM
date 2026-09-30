"""Relational course structure and response/skill separation; preserve legacy questions."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

RESPONSE_TYPES = ["FREE_RESPONSE", "SINGLE_CHOICE", "MULTIPLE_SELECT", "TRUE_FALSE"]
SKILLS = ["CALCULATION", "DEFINITION", "PROOF", "THEOREM", "EXAMPLE", "APPLICATION", "CONSTRUCTION", "CLASSIFICATION", "UNSPECIFIED"]
SUITABILITIES = ["GENERAL_PRACTICE", "WEEKLY_QUIZ", "MIDTERM", "ENDTERM", "COURSEWORK", "RETAKE", "THEORY_SHORT", "THEORY_PROOF"]


def create_lookup(name: str, codes: list[str]) -> None:
    table = op.create_table(
        name,
        sa.Column("code", sa.String(40), primary_key=True),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
    )
    op.bulk_insert(table, [{"code": code, "label": "Needs classification" if code == "UNSPECIFIED" else code.replace("_", " ").title(), "sort_order": i * 10} for i, code in enumerate(codes)])


def upgrade() -> None:
    connection = op.get_bind()
    legacy = list(connection.execute(sa.text("SELECT * FROM questions ORDER BY id")).mappings())
    for row in legacy:
        if row["question_type"] == "multiple_choice":
            options = row["options"] or []
            if len(options) < 2 or len(set(options)) != len(options) or row["correct_answer"] not in options:
                raise RuntimeError(f"Question {row['id']} has invalid legacy choices. Fix it before migrating; nothing has been dropped.")
        if row["question_type"] == "true_false" and row["correct_answer"] not in ("true", "false"):
            raise RuntimeError(f"Question {row['id']} has an invalid boolean answer. Fix it before migrating.")

    topics = op.create_table(
        "topics", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(120), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("topics.id", ondelete="RESTRICT")),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.CheckConstraint("parent_id IS NULL OR parent_id <> id", name="ck_topics_not_self"),
    )
    op.create_index("ix_topics_parent_id", "topics", ["parent_id"])
    topic_ids = {}
    roots = [("foundations", "Foundations"), ("complex-numbers", "Complex Numbers"), ("combinatorics", "Combinatorics"), ("graphs", "Graphs")]
    for order, (slug, name) in enumerate(roots):
        topic_ids[name.casefold()] = connection.execute(topics.insert().values(slug=slug, name=name, sort_order=order * 10).returning(topics.c.id)).scalar_one()
    for order, (slug, name) in enumerate([("logic", "Logic"), ("sets", "Sets"), ("binary-relations", "Binary Relations"), ("functions", "Functions")]):
        topic_ids[name.casefold()] = connection.execute(topics.insert().values(slug=slug, name=name, parent_id=topic_ids["foundations"], sort_order=order * 10).returning(topics.c.id)).scalar_one()
    topic_ids["relations"] = topic_ids["binary relations"]
    topic_ids["graph theory"] = topic_ids["graphs"]

    create_lookup("response_types", RESPONSE_TYPES)
    create_lookup("skill_types", SKILLS)
    create_lookup("assessment_suitabilities", SUITABILITIES)
    problem_sets = op.create_table(
        "problem_sets", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
    )
    op.bulk_insert(problem_sets, [{"code": f"PS{i}", "name": f"Problem Set {i}", "sort_order": i * 10} for i in range(1, 13)])
    op.add_column("questions", sa.Column("topic_id", sa.Integer(), nullable=True))
    op.add_column("questions", sa.Column("title", sa.String(200)))
    op.add_column("questions", sa.Column("skill_type", sa.String(40), nullable=True))
    op.add_column("questions", sa.Column("correct_boolean", sa.Boolean()))
    op.add_column("questions", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("questions", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.drop_constraint("ck_questions_type", "questions", type_="check")
    op.alter_column("questions", "question_type", new_column_name="response_type", type_=sa.String(40))
    op.alter_column("questions", "correct_answer", new_column_name="expected_answer", nullable=True)

    option_table = op.create_table(
        "question_options", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("question_id", "position", name="uq_question_options_position", deferrable=True, initially="DEFERRED"),
        sa.CheckConstraint("position >= 0", name="ck_question_options_position"),
    )
    op.create_index("ix_question_options_question_id", "question_options", ["question_id"])
    for row in legacy:
        key = row["topic"].strip().casefold()
        if key not in topic_ids:
            topic_ids[key] = connection.execute(topics.insert().values(slug=f"legacy-topic-{row['id']}", name=row["topic"], sort_order=1000 + row["id"]).returning(topics.c.id)).scalar_one()
        kind = {"short_answer": "FREE_RESPONSE", "multiple_choice": "SINGLE_CHOICE", "true_false": "TRUE_FALSE"}[row["question_type"]]
        connection.execute(sa.text("""
            UPDATE questions SET topic_id=:topic, response_type=:kind, skill_type='UNSPECIFIED',
            expected_answer=:answer, correct_boolean=:boolean, updated_at=created_at WHERE id=:id
        """), {"topic": topic_ids[key], "kind": kind, "answer": row["correct_answer"] if kind == "FREE_RESPONSE" else None,
                "boolean": row["correct_answer"] == "true" if kind == "TRUE_FALSE" else None, "id": row["id"]})
        if kind == "SINGLE_CHOICE":
            connection.execute(option_table.insert(), [{"question_id": row["id"], "text": value, "position": i, "is_correct": value == row["correct_answer"]} for i, value in enumerate(row["options"])])

    op.alter_column("questions", "topic_id", nullable=False)
    op.alter_column("questions", "skill_type", nullable=False)
    for column, target, target_column in [("topic_id", "topics", "id"), ("response_type", "response_types", "code"), ("skill_type", "skill_types", "code")]:
        op.create_foreign_key(f"fk_questions_{column}", "questions", target, [column], [target_column], ondelete="RESTRICT")
    for column in ("topic_id", "difficulty", "response_type", "skill_type", "is_active"):
        op.create_index(f"ix_questions_{column}", "questions", [column])
    op.create_check_constraint("ck_questions_answer_storage", "questions",
        "(response_type = 'FREE_RESPONSE' AND expected_answer IS NOT NULL AND correct_boolean IS NULL) OR "
        "(response_type = 'TRUE_FALSE' AND expected_answer IS NULL AND correct_boolean IS NOT NULL) OR "
        "(response_type IN ('SINGLE_CHOICE', 'MULTIPLE_SELECT') AND expected_answer IS NULL AND correct_boolean IS NULL)")
    op.create_table("question_problem_sets",
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("problem_set_id", sa.Integer(), sa.ForeignKey("problem_sets.id", ondelete="RESTRICT"), primary_key=True))
    op.create_index("ix_question_problem_sets_problem_set_id", "question_problem_sets", ["problem_set_id"])
    op.create_table("question_suitabilities",
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("suitability_code", sa.String(40), sa.ForeignKey("assessment_suitabilities.code", ondelete="RESTRICT"), primary_key=True))
    op.create_index("ix_question_suitabilities_suitability_code", "question_suitabilities", ["suitability_code"])
    # All legacy values have been copied or transformed above, in this transaction.
    op.drop_column("questions", "topic")
    op.drop_column("questions", "options")


def downgrade() -> None:
    raise RuntimeError("0002 cannot be reversed without losing new classifications and multiple-select answers. Use a reviewed forward migration or restore a pre-migration backup; no data has been dropped.")
