export function GuestModeNotice({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p className="guest-contextual-notice" role="status">
      {message}
    </p>
  );
}
