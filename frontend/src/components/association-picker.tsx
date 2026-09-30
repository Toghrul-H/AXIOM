"use client";

export function AssociationPicker({
  legend,
  choices,
  selected,
  onChange,
}: {
  legend: string;
  choices: { value: string; label: string }[];
  selected: string[];
  onChange: (values: string[]) => void;
}) {
  return (
    <fieldset className="association-picker">
      <legend>{legend}</legend>
      <div>
        {choices.map((choice) => (
          <label className="check-chip" key={choice.value}>
            <input
              type="checkbox"
              checked={selected.includes(choice.value)}
              onChange={(e) =>
                onChange(
                  e.target.checked
                    ? [...selected, choice.value]
                    : selected.filter((value) => value !== choice.value),
                )
              }
            />
            <span>{choice.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
