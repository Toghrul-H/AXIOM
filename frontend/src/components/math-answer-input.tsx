"use client";
import { useId, useLayoutEffect, useRef, useState } from "react";
import {
  MathProfile,
  MathSymbol,
  MATH_PROFILES,
  symbolsForProfile,
  insertMathSymbol,
} from "@/lib/math-symbols";

export function MathAnswerInput({
  value,
  onChange,
  profile = "general",
  extraSymbols = [],
  label = "Your written response",
  rows = 8,
  maxLength = 20000,
  disabled = false,
}: {
  value: string;
  onChange: (value: string) => void;
  profile?: MathProfile;
  extraSymbols?: readonly MathSymbol[];
  label?: string;
  rows?: number;
  maxLength?: number;
  disabled?: boolean;
}) {
  const id = useId();
  const input = useRef<HTMLTextAreaElement>(null);
  const caret = useRef<number | null>(null);
  const [message, setMessage] = useState("");
  useLayoutEffect(() => {
    if (caret.current === null || !input.current) return;
    input.current.focus();
    input.current.setSelectionRange(caret.current, caret.current);
    caret.current = null;
  }, [value]);
  function insert(s: MathSymbol) {
    const field = input.current;
    if (!field) return;
    const result = insertMathSymbol(
      value,
      field.selectionStart,
      field.selectionEnd,
      s,
      maxLength,
    );
    if (!result) {
      setMessage(`Answer limit of ${maxLength} characters reached.`);
      field.focus();
      return;
    }
    setMessage("");
    caret.current = result.cursor;
    if (result.text === value) {
      field.focus();
      field.setSelectionRange(result.cursor, result.cursor);
      caret.current = null;
    } else onChange(result.text);
  }
  return (
    <div className="field math-answer-input">
      <label htmlFor={id}>{label}</label>
      <textarea
        ref={input}
        id={id}
        value={value}
        rows={rows}
        maxLength={maxLength}
        disabled={disabled}
        aria-describedby={`${id}-hint`}
        onChange={(e) => {
          caret.current = null;
          setMessage("");
          onChange(e.target.value);
        }}
      />
      <p className="field-hint" id={`${id}-hint`}>
        {MATH_PROFILES[profile].label} symbols · Insert at the cursor, or keep
        typing normally.
      </p>
      <div
        className="math-symbols"
        role="group"
        aria-label={`${MATH_PROFILES[profile].label} mathematical symbols`}
      >
        {symbolsForProfile(profile, extraSymbols).map((s) => (
          <button
            key={s.text}
            type="button"
            disabled={disabled}
            title={`${s.text} — ${s.label}`}
            aria-label={`${s.label} (${s.text})`}
            onPointerDown={(e) => e.preventDefault()}
            onClick={() => insert(s)}
          >
            {s.text}
          </button>
        ))}
      </div>
      <span role="status" className="field-hint">
        {message}
      </span>
    </div>
  );
}
