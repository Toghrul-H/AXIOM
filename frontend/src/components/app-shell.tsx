"use client";

import Link from "next/link";
import { useAuth } from "./auth-provider";
import { Wordmark } from "./wordmark";
import { futureTools } from "@/lib/future-tools";
import { usePathname } from "next/navigation";
import {
  ArrowUpRight,
  BookOpen,
  ChartNoAxesCombined,
  ChevronRight,
  GraduationCap,
  LayoutDashboard,
  LibraryBig,
  Menu,
  Plus,
  Shapes,
  Sparkles,
  X,
  UserRound,
  ChevronDown,
  Bell,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { user, signOut } = useAuth();
  const [logoutError, setLogoutError] = useState("");
  const demonstrator = user?.role === "DEMONSTRATOR";
  const teacher = user?.role !== "STUDENT";
  const [open, setOpen] = useState(false);
  const sidebar = useRef<HTMLElement>(null);
  const menuButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const element = sidebar.current;
    element?.querySelector<HTMLButtonElement>(".mobile-close")?.focus();
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        menuButton.current?.focus();
      }
      if (event.key !== "Tab") return;
      const items = Array.from(
        element?.querySelectorAll<HTMLElement>(
          "a[href], button:not(:disabled)",
        ) ?? [],
      ).filter((item) => item.getClientRects().length > 0);
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
    function handleResize() {
      if (window.innerWidth > 760) setOpen(false);
    }
    document.addEventListener("keydown", handleKey);
    window.addEventListener("resize", handleResize);
    return () => {
      document.removeEventListener("keydown", handleKey);
      window.removeEventListener("resize", handleResize);
    };
  }, [open]);
  const links = teacher
    ? [
        { href: "/teacher", label: "Dashboard", icon: LayoutDashboard },
        {
          href: "/teacher/questions",
          label: "Question Bank",
          icon: LibraryBig,
        },
        { href: "/teacher/questions/new", label: "Add Question", icon: Plus },
        { href: "/teacher/quizzes", label: "Quiz management", icon: Shapes },
        { href: "/teacher/grading", label: "Manual Grading", icon: BookOpen },
      ]
    : [
        { href: "/student", label: "Dashboard", icon: LayoutDashboard },
        { href: "/student/learn", label: "Learn", icon: BookOpen },
        { href: "/student/quizzes", label: "Quizzes", icon: Shapes },
        {
          href: "/student/progress",
          label: "Progress",
          icon: ChartNoAxesCombined,
        },
      ];
  if (user && ["LECTURER", "ADMIN"].includes(user.role))
    links.push({
      href: "/teacher/users",
      label: "Staff Management",
      icon: GraduationCap,
    });
  const current =
    (path.startsWith("/teacher/grading/") ? "Manual Grading" : undefined) ??
    links.find((item) => item.href === path)?.label ??
    futureTools.find((item) => path === `/teacher/tools/${item.slug}`)?.title ??
    (path.includes("/quizzes/")
      ? "Quiz"
      : path.endsWith("/edit")
        ? "Edit Question"
        : demonstrator
          ? "Demonstrator"
          : "Dashboard");
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      {open && (
        <button
          className="sidebar-backdrop"
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
        />
      )}
      <aside
        id="sidebar-navigation"
        ref={sidebar}
        className={`sidebar ${open ? "is-open" : ""}`}
        aria-label="Main navigation"
      >
        <Link
          href={teacher ? "/teacher" : "/student"}
          className="brand"
          onClick={() => setOpen(false)}
        >
          <Wordmark />
        </Link>
        <button
          className="mobile-close icon-button"
          onClick={() => setOpen(false)}
          aria-label="Close navigation"
        >
          <X size={20} />
        </button>
        <div className="course-label">
          <span className="course-icon">
            <GraduationCap size={19} />
          </span>
          <div>
            <strong>Discrete Mathematics I</strong>
            <span>Course workspace</span>
          </div>
        </div>
        <p className="nav-caption">{teacher ? "TEACHING" : "YOUR LEARNING"}</p>
        <nav>
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              onClick={() => setOpen(false)}
              className={`nav-link ${path === href || (label === "Question Bank" && path.endsWith("/edit")) ? "active" : ""}`}
              aria-current={path === href ? "page" : undefined}
            >
              <Icon size={19} strokeWidth={1.7} />
              {label}
              {path === href && <span className="nav-dot" />}
            </Link>
          ))}
        </nav>
        {user && ["LECTURER", "ADMIN"].includes(user.role) && (
          <section className="future-tools" aria-label="Future teaching tools">
            <p className="nav-caption">TOOLS · IN DEVELOPMENT</p>
            {futureTools.map(({ slug, title }) => (
              <Link
                className={`future-tool nav-link ${path === `/teacher/tools/${slug}` ? "active" : ""}`}
                key={slug}
                href={`/teacher/tools/${slug}`}
                onClick={() => setOpen(false)}
                aria-current={
                  path === `/teacher/tools/${slug}` ? "page" : undefined
                }
              >
                <span>{title}</span>
                <small>Coming soon</small>
              </Link>
            ))}
          </section>
        )}
        {!teacher && (
          <section className="sidebar-course" aria-label="Course topics">
            <p className="nav-caption">COURSE</p>
            <ol>
              {[
                "Logic",
                "Sets",
                "Binary Relations",
                "Functions",
                "Complex Numbers",
                "Combinatorics",
                "Graphs",
              ].map((topic, index) => (
                <li key={topic}>
                  <span aria-hidden="true">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  {topic}
                </li>
              ))}
            </ol>
          </section>
        )}
        <div className="sidebar-bottom">
          <div className="course-note">
            <BookOpen size={19} />
            <strong>A foundation for what’s next.</strong>
            <p>Build your understanding, one idea at a time.</p>
          </div>
          <div className="sidebar-footer">
            ELTE Informatics <ArrowUpRight size={13} />
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              ref={menuButton}
              className="mobile-menu icon-button"
              aria-label="Open navigation"
              aria-expanded={open}
              aria-controls="sidebar-navigation"
              onClick={() => setOpen(true)}
            >
              <Menu size={21} />
            </button>
            <span>Discrete Mathematics I</span>
            <ChevronRight size={14} />
            <strong>{current}</strong>
          </div>
          <div className="topbar-right">
            <div className="header-course-context">
              <GraduationCap size={18} aria-hidden="true" />
              <span>
                Discrete Mathematics I<small>Course workspace</small>
              </span>
            </div>
            <details className="account-control notification-control">
              <summary aria-label="Notifications">
                <Bell size={20} />
              </summary>
              <div className="account-menu">
                <strong>Notifications</strong>
                <p>No new notifications</p>
              </div>
            </details>
            <details className="account-control">
              <summary>
                <span className="account-avatar">
                  <UserRound size={17} />
                </span>
                <span className="account-label">
                  My account<span>{user?.role}</span>
                </span>
                <ChevronDown size={14} />
              </summary>
              <div className="account-menu">
                <strong>{user?.email}</strong>
                <span className="role-chip">{user?.role}</span>
                <button
                  className="button button-secondary"
                  onClick={() => {
                    void signOut().catch(() =>
                      setLogoutError("Sign out failed. Please retry."),
                    );
                  }}
                >
                  Sign out
                </button>
                {logoutError && <p role="alert">{logoutError}</p>}
              </div>
            </details>
          </div>
        </header>
        <main id="main-content" className="main-content" tabIndex={-1}>
          {children}
        </main>
        <footer className="workspace-footer">
          <span>
            Discrete Mathematics I <span className="footer-separator">/</span>{" "}
            ELTE Faculty of Informatics
          </span>
          <span>
            <Sparkles size={12} /> AXIOM · Discrete Mathematics
          </span>
        </footer>
      </div>
    </div>
  );
}
