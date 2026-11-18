import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy · AXIOM",
  description: "Privacy information for the AXIOM learning platform.",
};

export default function PrivacyPage() {
  return (
    <main className="privacy-page">
      <article className="panel privacy-card">
        <p className="eyebrow">AXIOM · Discrete Mathematics I</p>
        <h1>Privacy Policy</h1>
        <p className="privacy-updated">Last reviewed: November 18, 2026</p>

        <section>
          <h2>Purpose</h2>
          <p>
            AXIOM is an educational platform for Discrete Mathematics I. This
            page describes the information handled when the platform is used. It
            is not a replacement for any applicable ELTE or course policy.
          </p>
        </section>

        <section>
          <h2>Account and authentication data</h2>
          <p>
            AXIOM stores account email addresses, account roles, account status,
            email-verification status, and account timestamps. Passwords are
            stored as password hashes, not as readable passwords. The platform
            uses server-side sessions and CSRF protections to keep authenticated
            actions tied to the signed-in account.
          </p>
        </section>

        <section>
          <h2>Learning and course activity</h2>
          <p>
            When course features are used, AXIOM stores the information needed
            for those features, such as quiz attempts and answers, progress,
            manual-grading records, selected practice activity, and
            staff-created course content. Optional Study Partner and
            demonstrator recruitment features may store the profile, request,
            questionnaire, or message information entered for those features.
          </p>
        </section>

        <section>
          <h2>Course materials and Google Drive</h2>
          <p>
            Authorized teaching staff can upload supported course materials.
            AXIOM stores their title, description, file metadata, checksum, and
            access status. Uploaded file content is stored in a dedicated
            private Google Drive folder controlled by the platform
            administrator.
          </p>
          <p>
            Google Drive OAuth is used only by the platform administrator for
            private AXIOM course-material storage. AXIOM does not ask students
            to connect a Google account and does not access students&apos;
            personal Google Drives. The platform serves authorized material
            downloads through AXIOM; it does not create public Google Drive
            sharing links.
          </p>
        </section>

        <section>
          <h2>Access and sharing</h2>
          <p>
            Access is role-based. Students can access published course content
            and materials made available to them. Authorized staff manage course
            content and materials. The platform may send account-verification or
            password-recovery email through its configured email-delivery
            provider when those features are used.
          </p>
          <p>
            This policy does not make a claim about a broader retention,
            disclosure, or data-sharing practice beyond the platform behavior
            described above.
          </p>
        </section>

        <section>
          <h2>Retention and contact</h2>
          <p>
            The source repository does not define a universal retention period
            for account, learning, or course-material data. AXIOM does not
            currently provide a self-service account-deletion or data-access
            request workflow. Authorized staff deletion attempts to remove both
            the AXIOM material metadata and its associated private Google Drive
            file. If a provider or database failure occurs, deletion may require
            retry or administrator reconciliation.
          </p>
          <p>
            For privacy, data-access, correction, or deletion requests, contact{" "}
            <a href="mailto:axiom.elte@gmail.com">axiom.elte@gmail.com</a>.
            Requests are handled manually: AXIOM verifies account ownership,
            reviews the request, and processes it according to applicable
            obligations and the platform&apos;s actual technical capabilities.
            This does not provide automatic deletion, a fixed response time, or
            a guarantee of a particular retention period.
          </p>
        </section>

        <p className="privacy-actions">
          <Link className="button button-secondary" href="/login">
            Return to sign in
          </Link>
        </p>
      </article>
    </main>
  );
}
