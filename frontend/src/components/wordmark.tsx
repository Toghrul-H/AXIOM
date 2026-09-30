export function Wordmark() {
  return (
    <span className="wordmark">
      <svg
        className="wordmark-logo"
        viewBox="0 0 240 58"
        role="img"
        aria-label="AXIOM"
      >
        <g
          fill="none"
          stroke="currentColor"
          strokeWidth="3.5"
          strokeLinejoin="miter"
        >
          <path d="M4 47 23 10 42 47 M13 32h20 M53 11l30 36 M83 11 53 47 M99 11v36 M155 29c0-12-5-19-15-19s-15 7-15 19 5 19 15 19 15-7 15-19Z M173 47V11l23 25 23-25v36" />
          <path
            className="wordmark-frame"
            strokeWidth="1.2"
            d="M91 19V3h72v52H91V39"
          />
        </g>
        <path fill="var(--gold)" d="m99 25 4 4-4 4-4-4Z" />
      </svg>
      <span className="wordmark-subtitle">Discrete Mathematics</span>
    </span>
  );
}
