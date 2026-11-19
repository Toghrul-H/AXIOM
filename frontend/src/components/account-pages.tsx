"use client";

import Link from "next/link";

import { useAuth } from "@/components/auth-provider";
import { PageHeading } from "@/components/page-heading";
import { ThemePreference } from "@/components/theme-preference";

function initials(email: string) {
  return (
    email
      .split("@", 1)[0]
      .replace(/[^a-z0-9]/gi, "")
      .slice(0, 2)
      .toUpperCase() || "A"
  );
}

export function AccountProfile() {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <section className="account-page">
      <PageHeading
        eyebrow="ACCOUNT"
        title="Profile"
        description="Your account information and university-provisioned access level."
      />
      <article className="panel account-profile-card">
        <div className="account-profile-avatar" aria-hidden="true">
          {initials(user.email)}
        </div>
        <div>
          <h2>{user.email}</h2>
          <p>
            Your avatar uses initials until a secure avatar service is
            available.
          </p>
        </div>
        <dl className="account-details">
          <div>
            <dt>Primary email</dt>
            <dd>{user.email}</dd>
          </div>
          <div>
            <dt>Role</dt>
            <dd>{user.role}</dd>
          </div>
          <div>
            <dt>First and last name</dt>
            <dd>Not supplied by the current account service.</dd>
          </div>
          <div>
            <dt>Neptun code</dt>
            <dd>Not supplied by the current account service.</dd>
          </div>
          <div>
            <dt>Secondary email</dt>
            <dd>Not supported by the current account service.</dd>
          </div>
        </dl>
        <p className="field-hint">
          University-controlled identity fields are read-only. AXIOM does not
          currently support avatar upload, profile edits, or secondary email
          changes.
        </p>
      </article>
    </section>
  );
}

export function AccountSettings() {
  return (
    <section className="account-page">
      <PageHeading
        eyebrow="ACCOUNT"
        title="Settings"
        description="Manage supported personal display preferences and find account help."
      />
      <div className="account-settings-grid">
        <article className="panel setting-card">
          <h2>Appearance</h2>
          <p>Choose light, dark, or system appearance.</p>
          <ThemePreference />
        </article>
        <article className="panel setting-card">
          <h2>Notifications</h2>
          <p>
            Use the notification bell to review platform notifications.
            Per-category notification preferences are not available yet.
          </p>
        </article>
        <article className="panel setting-card">
          <h2>Security</h2>
          <p>
            Use password recovery to set a new password and revoke existing
            sessions.
          </p>
          <Link className="button button-secondary" href="/forgot-password">
            Password recovery
          </Link>
        </article>
        <article className="panel setting-card">
          <h2>Privacy</h2>
          <p>
            Read how AXIOM handles account, learning, and course-material
            information.
          </p>
          <Link className="button button-secondary" href="/privacy">
            Privacy policy
          </Link>
        </article>
        <article className="panel setting-card">
          <h2>Account deletion</h2>
          <p>
            Account deletion is not self-service because academic records and
            course data require an authorized retention review.
          </p>
          <a
            className="button button-secondary"
            href="mailto:axiom.elte@gmail.com"
          >
            Request account review
          </a>
        </article>
      </div>
    </section>
  );
}
