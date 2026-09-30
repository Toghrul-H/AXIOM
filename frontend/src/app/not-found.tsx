import Link from "next/link";
export default function NotFound() {
  return (
    <section className="panel empty-state">
      <h1>Page not found</h1>
      <p>This page is not part of the course workspace.</p>
      <Link href="/student" className="button button-primary">
        Back to dashboard
      </Link>
    </section>
  );
}
