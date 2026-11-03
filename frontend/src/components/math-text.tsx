import katex from "katex";

/**
 * Safely renders the inline `$...$` mathematical fragments used by the
 * verified DMI import data. KaTeX escapes input by default; `trust: false`
 * explicitly disables HTML/URL-producing LaTeX commands.
 */
export function MathText({
  text,
  className,
}: {
  text: string;
  className?: string;
}) {
  const parts = text.split(/(\$[^$\n]+\$)/g);
  return (
    <span className={className ? `math-text ${className}` : "math-text"}>
      {parts.map((part, index) => {
        if (!part.startsWith("$") || !part.endsWith("$")) return part;
        const source = part.slice(1, -1);
        return (
          <span
            // The index is stable because this is a pure rendering of text.
            key={`${source}-${index}`}
            role="math"
            aria-label={source}
            dangerouslySetInnerHTML={{
              __html: katex.renderToString(source, {
                displayMode: false,
                throwOnError: false,
                strict: "ignore",
                trust: false,
              }),
            }}
          />
        );
      })}
    </span>
  );
}
