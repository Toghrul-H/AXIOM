"use client";
import { Plus, X } from "lucide-react";
import { OptionInput } from "@/lib/questions";

export function ChoiceEditor({
  options,
  multiple,
  onChange,
}: {
  options: OptionInput[];
  multiple: boolean;
  onChange: (options: OptionInput[]) => void;
}) {
  return (
    <fieldset className="choice-editor">
      <legend>Answer options *</legend>
      <p className="field-hint">
        {multiple
          ? "Check every correct option. At least one must be correct."
          : "Choose exactly one correct option."}{" "}
        Add 2–20 distinct options.
      </p>
      {options.map((option, index) => (
        <div className="choice-row" key={option.id ?? `new-${index}`}>
          <label className="correct-control">
            <input
              aria-label={`Option ${index + 1} is correct`}
              type={multiple ? "checkbox" : "radio"}
              name="correct-option"
              checked={option.is_correct}
              onChange={(e) =>
                onChange(
                  options.map((o, i) => ({
                    ...o,
                    is_correct:
                      i === index
                        ? e.target.checked
                        : multiple
                          ? o.is_correct
                          : false,
                  })),
                )
              }
            />
            <span>{String.fromCharCode(65 + index)}</span>
          </label>
          <input
            aria-label={`Option ${index + 1} text`}
            required
            maxLength={20000}
            value={option.text}
            placeholder={`Option ${index + 1}`}
            onChange={(e) =>
              onChange(
                options.map((o, i) =>
                  i === index ? { ...o, text: e.target.value } : o,
                ),
              )
            }
          />
          <button
            type="button"
            className="icon-button"
            aria-label={`Remove option ${index + 1}`}
            disabled={options.length <= 2}
            onClick={() => onChange(options.filter((_, i) => i !== index))}
          >
            <X size={17} />
          </button>
        </div>
      ))}
      <button
        type="button"
        className="button button-quiet"
        disabled={options.length >= 20}
        onClick={() => onChange([...options, { text: "", is_correct: false }])}
      >
        <Plus size={15} />
        Add option
      </button>
    </fieldset>
  );
}
