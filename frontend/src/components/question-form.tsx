"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, Check } from "lucide-react";
import {
  Difficulty,
  Metadata,
  OptionInput,
  Question,
  QuestionInput,
  questionsApi,
  QuestionType,
} from "@/lib/questions";
import { orderedTopics, useMetadata } from "@/lib/use-metadata";
import { PageHeading } from "./page-heading";
import { ChoiceEditor } from "./choice-editor";
import { AssociationPicker } from "./association-picker";

export function QuestionForm({ question }: { question?: Question }) {
  const { metadata, error } = useMetadata();
  if (error)
    return (
      <div className="panel error-state" role="alert">
        <h2>Course structure unavailable</h2>
        <p>{error}</p>
        <button
          className="button button-secondary"
          onClick={() => window.location.reload()}
        >
          Retry
        </button>
      </div>
    );
  if (!metadata)
    return (
      <div className="panel loading-state" role="status">
        Loading course structure…
      </div>
    );
  return <QuestionEditor question={question} metadata={metadata} />;
}

function QuestionEditor({
  question,
  metadata,
}: {
  question?: Question;
  metadata: Metadata;
}) {
  const router = useRouter();
  const [topic, setTopic] = useState(String(question?.topic.id ?? ""));
  const [title, setTitle] = useState(question?.title ?? "");
  const [difficulty, setDifficulty] = useState<Difficulty>(
    question?.difficulty ?? "easy",
  );
  const [type, setType] = useState<QuestionType>(
    question?.response_type ?? "FREE_RESPONSE",
  );
  const [skill, setSkill] = useState(question?.skill_type ?? "");
  const [text, setText] = useState(question?.question_text ?? "");
  const [answer, setAnswer] = useState(question?.expected_answer ?? "");
  const [booleanAnswer, setBooleanAnswer] = useState(
    question?.correct_boolean === null ||
      question?.correct_boolean === undefined
      ? ""
      : String(question.correct_boolean),
  );
  const [explanation, setExplanation] = useState(question?.explanation ?? "");
  const [active, setActive] = useState(question?.is_active ?? true);
  const [options, setOptions] = useState<OptionInput[]>(
    question?.options.length
      ? question.options.map(({ id, text, is_correct }) => ({
          id,
          text,
          is_correct,
        }))
      : [
          { text: "", is_correct: false },
          { text: "", is_correct: false },
        ],
  );
  const [problemSets, setProblemSets] = useState<string[]>(
    question?.problem_sets.map((p) => String(p.id)) ?? [],
  );
  const [tags, setTags] = useState<string[]>(
    question?.assessment_suitabilities.map((tag) => tag.code) ?? [],
  );
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const choice = type === "SINGLE_CHOICE" || type === "MULTIPLE_SELECT";

  function changeType(value: QuestionType) {
    setType(value);
    setError("");
    if (value === "SINGLE_CHOICE") {
      const firstCorrect = options.findIndex((o) => o.is_correct);
      setOptions(
        options.map((o, i) => ({ ...o, is_correct: i === firstCorrect })),
      );
    }
  }
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;
    setError("");
    if (
      !topic ||
      !skill ||
      !text.trim() ||
      (type === "FREE_RESPONSE" && !answer.trim()) ||
      (type === "TRUE_FALSE" && !booleanAnswer)
    ) {
      setError("Complete all required classification and answer fields.");
      return;
    }
    const cleanedOptions = options.map((o) => ({ ...o, text: o.text.trim() }));
    const correctCount = cleanedOptions.filter((o) => o.is_correct).length;
    if (
      choice &&
      (cleanedOptions.some((o) => !o.text) ||
        new Set(cleanedOptions.map((o) => o.text)).size !==
          cleanedOptions.length ||
        correctCount < 1 ||
        (type === "SINGLE_CHOICE" && correctCount !== 1))
    ) {
      setError(
        "Use distinct, nonempty options. Mark exactly one correct option for single choice, or at least one for multiple select.",
      );
      return;
    }
    const body: QuestionInput = {
      topic_id: Number(topic),
      title: title.trim() || null,
      difficulty,
      response_type: type,
      skill_type: skill,
      question_text: text.trim(),
      expected_answer: type === "FREE_RESPONSE" ? answer.trim() : null,
      correct_boolean: type === "TRUE_FALSE" ? booleanAnswer === "true" : null,
      explanation: explanation.trim() || null,
      is_active: active,
      options: choice ? cleanedOptions : [],
      problem_set_ids: problemSets.map(Number),
      assessment_suitability_codes: tags,
    };
    setSaving(true);
    try {
      if (question) await questionsApi.update(question.id, body);
      else await questionsApi.create(body);
      router.push("/teacher/questions");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save question.");
      setSaving(false);
    }
  }
  return (
    <>
      <Link className="back-link" href="/teacher/questions">
        <ArrowLeft size={15} />
        Back to Question Bank
      </Link>
      <PageHeading
        eyebrow="TEACHING RESOURCES"
        title={question ? "Edit question" : "Add question"}
        description="Classify the academic skill separately from how the answer is submitted."
      />
      <form className="panel question-form structured-form" onSubmit={submit}>
        <fieldset disabled={saving}>
          <legend className="sr-only">Question details</legend>
          <div className="form-section-heading">
            <span>01</span>
            <div>
              <h2>Course classification</h2>
              <p>
                Choose the most specific topic that fits. Foundations includes
                its four subtopics.
              </p>
            </div>
          </div>
          <div className="field">
            <label htmlFor="title">
              Title / short identifier{" "}
              <span className="optional">Optional</span>
            </label>
            <input
              id="title"
              maxLength={200}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="A concise label for this question"
            />
          </div>
          <div className="field-grid">
            <div className="field">
              <label htmlFor="topic">Topic / subtopic *</label>
              <select
                id="topic"
                required
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
              >
                <option value="">Select a topic</option>
                {orderedTopics(metadata.topics).map(({ topic, label }) => (
                  <option value={topic.id} key={topic.id}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="difficulty">Difficulty *</label>
              <select
                id="difficulty"
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value as Difficulty)}
              >
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </select>
            </div>
          </div>
          <div className="field-grid">
            <div className="field">
              <label htmlFor="response-type">Response type *</label>
              <select
                id="response-type"
                value={type}
                onChange={(e) => changeType(e.target.value as QuestionType)}
              >
                {metadata.response_types.map((r) => (
                  <option value={r.code} key={r.code}>
                    {r.label}
                  </option>
                ))}
              </select>
              <span className="field-hint">How the learner answers.</span>
            </div>
            <div className="field">
              <label htmlFor="skill-type">Skill type *</label>
              <select
                id="skill-type"
                required
                value={skill}
                onChange={(e) => setSkill(e.target.value)}
              >
                <option value="">Select an academic skill</option>
                {metadata.skill_types.map((s) => (
                  <option value={s.code} key={s.code}>
                    {s.label}
                  </option>
                ))}
              </select>
              <span className="field-hint">What the question tests.</span>
            </div>
          </div>
          <AssociationPicker
            legend="Problem sets (optional, choose any)"
            choices={metadata.problem_sets.map((p) => ({
              value: String(p.id),
              label: p.code,
            }))}
            selected={problemSets}
            onChange={setProblemSets}
          />
          <AssociationPicker
            legend="Assessment suitability (optional, choose any)"
            choices={metadata.assessment_suitabilities.map((tag) => ({
              value: tag.code,
              label: tag.label,
            }))}
            selected={tags}
            onChange={setTags}
          />
          <p className="field-hint">
            Suitability describes where this question could be used, not an
            assessment where it was actually used.
          </p>
          <label className="active-toggle">
            <input
              type="checkbox"
              checked={active}
              onChange={(e) => setActive(e.target.checked)}
            />
            Active question
          </label>
          <div className="form-section-heading separated">
            <span>02</span>
            <div>
              <h2>Question and answer</h2>
              <p>Use plain text and mathematical Unicode symbols.</p>
            </div>
          </div>
          <div className="field">
            <label htmlFor="question-text">Question text *</label>
            <textarea
              id="question-text"
              required
              maxLength={20000}
              rows={5}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </div>
          {choice ? (
            <ChoiceEditor
              options={options}
              multiple={type === "MULTIPLE_SELECT"}
              onChange={setOptions}
            />
          ) : type === "TRUE_FALSE" ? (
            <div className="field">
              <label htmlFor="boolean-answer">Correct answer *</label>
              <select
                id="boolean-answer"
                required
                value={booleanAnswer}
                onChange={(e) => setBooleanAnswer(e.target.value)}
              >
                <option value="">Select true or false</option>
                <option value="true">True</option>
                <option value="false">False</option>
              </select>
            </div>
          ) : (
            <div className="field">
              <label htmlFor="expected-answer">
                Expected / reference answer *
              </label>
              <textarea
                id="expected-answer"
                required
                maxLength={20000}
                rows={4}
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
              />
              <p className="field-hint">
                Reference only. Free-response answers, proofs, and explanations
                are not automatically graded.
              </p>
            </div>
          )}
          <div className="field">
            <label htmlFor="explanation">
              Full solution / explanation{" "}
              <span className="optional">Optional</span>
            </label>
            <textarea
              id="explanation"
              maxLength={20000}
              rows={6}
              value={explanation}
              onChange={(e) => setExplanation(e.target.value)}
              placeholder="Explain the reasoning and steps."
            />
          </div>
        </fieldset>
        {error && (
          <div role="alert" className="error-message">
            {error}
          </div>
        )}
        <div className="form-actions">
          <span className="field-hint">* Required fields</span>
          <div>
            {!saving && (
              <Link
                href="/teacher/questions"
                className="button button-secondary"
              >
                Cancel
              </Link>
            )}
            <button
              type="submit"
              disabled={saving}
              className="button button-primary"
            >
              <Check size={17} />
              {saving
                ? "Saving…"
                : question
                  ? "Save changes"
                  : "Create question"}
            </button>
          </div>
        </div>
      </form>
    </>
  );
}
