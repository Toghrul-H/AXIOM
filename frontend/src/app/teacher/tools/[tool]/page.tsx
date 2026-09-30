import Link from "next/link";
import { notFound } from "next/navigation";
import { futureTools } from "@/lib/future-tools";
import { PageHeading } from "@/components/page-heading";

export default async function Page({
  params,
}: {
  params: Promise<{ tool: string }>;
}) {
  const { tool } = await params;
  const item = futureTools.find((item) => item.slug === tool);
  if (!item) notFound();
  return (
    <>
      <PageHeading
        eyebrow="AXIOM · TEACHING TOOLS"
        title={item.title}
        description={item.description}
      />
      <section className="panel tool-placeholder">
        <span className="development-label">IN DEVELOPMENT</span>
        <h2>A future teaching resource</h2>
        <p>This tool is planned for a future AXIOM milestone.</p>
        <Link className="button button-secondary" href="/teacher">
          Return to course overview
        </Link>
      </section>
    </>
  );
}
