"use client";

import Link from "next/link";
import { useAuth } from "./auth-provider";
import { Wordmark } from "./wordmark";
import { NotificationCenter } from "./notification-center";
import { ThemePreference } from "./theme-preference";
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
  ChevronsLeft,
  ChevronsRight,
  MessageCircle,
  Settings,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { user, signOut } = useAuth();
  const [logoutError, setLogoutError] = useState("");
  const demonstrator = user?.role === "DEMONSTRATOR";
  const teacher = user?.role !== "STUDENT";
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(
    () =>
      typeof window !== "undefined" &&
      window.localStorage.getItem("axiom-sidebar-collapsed") === "true",
  );
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
          "a[href], button:not(:disabled), select:not(:disabled), summary",
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
        { href: "/student/course", label: "Course", icon: BookOpen },
        { href: "/student/practice", label: "Practice", icon: Shapes },
        { href: "/student/quizzes", label: "Quizzes", icon: Shapes },
        { href: "/student/history", label: "History", icon: BookOpen },
        ...(user?.is_active
          ? [
              {
                href: "/student/study-partner",
                label: "Study Partner",
                icon: UserRound,
              },
            ]
          : []),
        ...(user?.is_active
          ? [
              {
                href: "/student/messages",
                label: "Messages",
                icon: MessageCircle,
              },
            ]
          : []),
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
  if (user && ["LECTURER", "ADMIN"].includes(user.role))
    links.push({
      href: "/teacher/recruitment",
      label: "Demonstrator Recruitment",
      icon: GraduationCap,
    });
  if (user && ["LECTURER", "ADMIN"].includes(user.role))
    links.push({ href: "/teacher/exams", label: "Exam Builder", icon: Shapes });
  if (user && ["LECTURER", "ADMIN"].includes(user.role))
    links.push({
      href: "/teacher/announcements",
      label: "Announcements",
      icon: MessageCircle,
    });
  if (user && ["LECTURER", "ADMIN"].includes(user.role))
    links.push({
      href: "/teacher/course",
      label: "Course management",
      icon: BookOpen,
    });
  const mobileLinks = teacher
    ? [
        { href: "/teacher", label: "Home", icon: LayoutDashboard },
        { href: "/teacher/course", label: "Course", icon: BookOpen },
        { href: "/teacher/quizzes", label: "Practice", icon: Shapes },
        { href: "/teacher/grading", label: "Grading", icon: BookOpen },
      ]
    : [
        { href: "/student", label: "Home", icon: LayoutDashboard },
        { href: "/student/course", label: "Course", icon: BookOpen },
        { href: "/student/practice", label: "Practice", icon: Shapes },
        user?.is_active
          ? {
              href: "/student/messages",
              label: "Messages",
              icon: MessageCircle,
            }
          : { href: "/student/quizzes", label: "Quizzes", icon: Shapes },
      ];
  const isActive = (href: string, label?: string) =>
    path === href ||
    (href !== (teacher ? "/teacher" : "/student") &&
      path.startsWith(`${href}/`)) ||
    (label === "Question Bank" && path.endsWith("/edit"));
  if (user && ["LECTURER", "ADMIN"].includes(user.role))
    links.push({
      href: "/teacher/practice-sheets",
      label: "Practice Sheets",
      icon: Shapes,
    });
  if (user && ["LECTURER", "ADMIN"].includes(user.role))
    links.push({
      href: "/teacher/assessments",
      label: "Assessment Documents",
      icon: BookOpen,
    });
  const current =
    (path.startsWith("/teacher/assessments")
      ? "Assessment Documents"
      : undefined) ??
    (path.startsWith("/teacher/exams") ? "Exam Builder" : undefined) ??
    (path.startsWith("/teacher/announcements") ? "Announcements" : undefined) ??
    (path.startsWith("/teacher/course") ? "Course management" : undefined) ??
    (path.startsWith("/teacher/practice-sheets")
      ? "Practice Sheets"
      : undefined) ??
    (path.startsWith("/account/profile") ? "Profile" : undefined) ??
    (path.startsWith("/account/settings") ? "Settings" : undefined) ??
    (path.startsWith("/student/study-partner") ? "Study Partner" : undefined) ??
    (path.startsWith("/student/course") ? "Course" : undefined) ??
    (path.startsWith("/teacher/grading/") ? "Manual Grading" : undefined) ??
    links.find((item) => item.href === path)?.label ??
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
        className={`sidebar ${open ? "is-open" : ""} ${collapsed ? "is-collapsed" : ""}`}
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
        <button
          className="sidebar-collapse icon-button"
          aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          title={collapsed ? "Expand navigation" : "Collapse navigation"}
          onClick={() =>
            setCollapsed((current) => {
              const next = !current;
              window.localStorage.setItem(
                "axiom-sidebar-collapsed",
                String(next),
              );
              return next;
            })
          }
        >
          {collapsed ? <ChevronsRight size={18} /> : <ChevronsLeft size={18} />}
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
              className={`nav-link ${isActive(href, label) ? "active" : ""}`}
              aria-current={isActive(href, label) ? "page" : undefined}
              title={collapsed ? label : undefined}
            >
              <Icon size={19} strokeWidth={1.7} />
              <span className="nav-label">{label}</span>
              {isActive(href, label) && <span className="nav-dot" />}
            </Link>
          ))}
        </nav>
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
            {user && <NotificationCenter key={user.id} userId={user.id} />}
            <details className="account-control">
              <summary>
                <span className="account-avatar">
                  {user?.email
                    .split("@", 1)[0]
                    .replace(/[^a-z0-9]/gi, "")
                    .slice(0, 2)
                    .toUpperCase() || "A"}
                </span>
                <span className="account-label">
                  My account<span>{user?.role}</span>
                </span>
                <ChevronDown size={14} />
              </summary>
              <div className="account-menu">
                <strong>{user?.email}</strong>
                <span className="role-chip">{user?.role}</span>
                <Link
                  className="button button-secondary"
                  href="/account/profile"
                >
                  Profile
                </Link>
                <Link
                  className="button button-secondary"
                  href="/account/settings"
                >
                  <Settings size={15} /> Settings
                </Link>
                <ThemePreference />
                {user?.role === "STUDENT" && (
                  <Link
                    className="button button-secondary"
                    href="/student/demonstrator-opportunities"
                  >
                    Demonstrator Applications
                  </Link>
                )}
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
        <nav className="mobile-bottom-nav" aria-label="Quick navigation">
          {mobileLinks.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={isActive(href) ? "active" : ""}
            >
              <Icon size={19} aria-hidden="true" />
              <span>{label}</span>
            </Link>
          ))}
        </nav>
      </div>
    </div>
  );
}
