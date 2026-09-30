"""Small opt-in development examples; these are NOT official ELTE questions."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_engine
from app.models import ProblemSet, Question, Topic
from app.schemas import QuestionCreate
from app.services.questions import save_question


def seed() -> None:
    # Problem-set links are illustrative development associations, not syllabus mappings.
    examples = [
        ("logic", "Logic implication", "TRUE_FALSE", "CLASSIFICATION", "If p is false, the implication p → q is false for every q. True or false?", {"correct_boolean": False}, "An implication with a false premise is true in classical propositional logic."),
        ("sets", "Set membership", "MULTIPLE_SELECT", "CALCULATION", "Select every element of {1, 2, 3} ∩ {2, 3, 4}.", {"options": [{"text": "1"}, {"text": "2", "is_correct": True}, {"text": "3", "is_correct": True}, {"text": "4"}]}, "The shared elements are exactly 2 and 3."),
        ("binary-relations", "Symmetric relation", "FREE_RESPONSE", "DEFINITION", "Define a symmetric binary relation R on a set A.", {"expected_answer": "For all a, b in A, aRb implies bRa."}, "Every related pair must also occur in the reverse direction. Reflexivity is a separate property."),
        ("functions", "Function image", "SINGLE_CHOICE", "APPLICATION", "For f: ℤ → ℤ defined by f(x) = 2x, what is f(3)?", {"options": [{"text": "3"}, {"text": "6", "is_correct": True}, {"text": "9"}]}, "Substitute x = 3: f(3) = 2 × 3 = 6."),
        ("complex-numbers", "Complex multiplication", "FREE_RESPONSE", "CALCULATION", "Compute (1 + i)(1 − i).", {"expected_answer": "2"}, "The product is 1 − i² = 1 − (−1) = 2. This reference answer is not automatically graded."),
        ("combinatorics", "Choosing a pair", "SINGLE_CHOICE", "CALCULATION", "How many two-element subsets does a five-element set have?", {"options": [{"text": "5"}, {"text": "10", "is_correct": True}, {"text": "20"}]}, "Choose 2 of 5 without order: 5! / (2!3!) = 10."),
        ("graphs", "Degree sum parity", "FREE_RESPONSE", "PROOF", "Prove that the number of odd-degree vertices in a finite undirected graph is even.", {"expected_answer": "The sum of all vertex degrees equals twice the number of edges and is even. The even-degree vertices contribute an even sum, so the odd-degree vertices also have even total degree. A sum of odd integers is even only when there are an even number of summands."}, "Use the handshaking lemma and parity. This is a reference proof, not an automatically checked solution."),
    ]
    with Session(get_engine()) as session:
        topics = {t.slug: t.id for t in session.scalars(select(Topic))}
        sets = list(session.scalars(select(ProblemSet).order_by(ProblemSet.sort_order)))
        created = 0
        for index, (slug, name, kind, skill, prompt, answer, solution) in enumerate(examples):
            title = f"[DEV] {name}"
            if session.scalar(select(Question.id).where(Question.title == title)) is not None:
                continue
            payload = QuestionCreate(
                topic_id=topics[slug], title=title, difficulty="medium" if skill == "PROOF" else "easy",
                response_type=kind, skill_type=skill, question_text=prompt, explanation=solution,
                problem_set_ids=[sets[index].id],
                assessment_suitability_codes=["GENERAL_PRACTICE", "THEORY_PROOF" if skill == "PROOF" else "WEEKLY_QUIZ"],
                **answer,
            )
            save_question(session, payload)
            created += 1
        print(f"Created {created} development questions; existing matching titles were left unchanged.")


if __name__ == "__main__":
    seed()
