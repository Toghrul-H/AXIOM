# AXIOM Lecturer User Guide

This guide describes the implemented interface reviewed on 28 October 2026. AXIOM is Toghrul Hasanli's academic internship project for Discrete Mathematics I, not an officially endorsed ELTE service. The owner reports the application at [AXIOM](https://axiom-orcin-xi.vercel.app/); current service availability was not checked for this handover.

## Access and accounts

Use **Sign in** if you already have an account. Public registration requires an exact `@inf.elte.hu` email address and a password of 12–128 characters. It creates a Student account only; there is no public staff-role selector. Follow the email link before signing in. **Check your email** offers **Resend verification email**; check spam too. Links expire after one hour, work once, and a newly issued link replaces the previous one. Resends have a 60-second cooldown.

A Lecturer account must be assigned by an Admin. Contact the agreed service owner for account access or password problems: there is no self-service password-reset feature. Never share passwords or verification links. **My account → Sign out** ends your session. Signing in again may be necessary after a role/status change or session expiry.

## Who can do what?

| Operation                                     | Student | Demonstrator             | Lecturer                                               | Admin                                        |
| --------------------------------------------- | ------- | ------------------------ | ------------------------------------------------------ | -------------------------------------------- |
| Take quizzes; view own results and Progress   | Yes     | No student-mode workflow | No student-mode workflow                               | No student-mode workflow                     |
| Question Bank, Add Question, Quiz management  | No      | Yes                      | Yes                                                    | Yes                                          |
| Manual Grading of submitted written responses | No      | Yes                      | Yes                                                    | Yes                                          |
| Assessment Documents                          | No      | No                       | Yes                                                    | Yes                                          |
| Staff Management                              | No      | No                       | Student/Demonstrator role changes; Demonstrator status | Also Lecturer role/status and Student status |

Staff Management searches existing accounts; it does not register accounts. Lecturers can change Student ↔ Demonstrator. Admins can also change accounts to/from Lecturer. **Deactivate Account** and **Reactivate Account** affect access; role/status changes revoke the affected sessions. Admin accounts, your own account, legacy accounts and protected system-managed accounts cannot be managed here. Protected/legacy accounts and Admins are excluded from the normal staff list.

## Question Bank

1. Open **Question Bank**. Use the topic, difficulty, response type, skill, problem-set, suitability, status and text filters; **Apply filters** updates the results and **Clear filters** resets filters.
2. Choose **Add Question**. Select course classification, then enter the question and answer information. Difficulty and academic skill are separate from response type. Problem sets and suitability can have multiple selections.
3. For single choice, identify one correct option; for multiple select, identify all correct options. True/false has a Boolean answer. Free response has a reference answer and optional explanation; it is not automatically graded.
4. Use **Create question**. For an existing question, open its edit action and use **Save changes**. Review validation messages if saving fails.

Deletion asks for confirmation. Referenced resources can be constrained by existing quizzes; resolve the reported conflict rather than assuming a delete succeeded. Deactivate questions when appropriate instead of destroying useful course content. Student attempts retain their original question/answer snapshots when the bank changes. Mathematical answer input is Unicode/plain text, not a symbolic algebra or proof checker.

## Quiz management

Open **Quiz management**, choose **New quiz** or an existing quiz, and enter its title and optional description. Search the Question Bank, add questions, arrange their display order and set their points. Choose **Availability**: Draft, Active or Inactive, then **Save quiz**. Active quizzes require active questions and a valid composition. Only available quizzes appear in the Student catalog. There is no quiz-delete workflow in this editor; use Inactive to withdraw availability.

Existing attempts keep their original snapshots and points. Changing a quiz does not rewrite submitted work. Written-question points are separate from the automatically graded total.

## Student workflow and progress

Students open **Quizzes → Start Quiz**, or **Resume quiz** under **Your quiz attempts**. Answers autosave; students should watch the saved/error indicator and can use **Save answer**. **Finish Quiz** requires confirmation and ends editing. Solutions are hidden during an active attempt; submitted results and review show reference answers/explanations and any saved manual feedback.

The Student **Dashboard** and **Progress** show completed quizzes/attempts, answers submitted, seven topic breakdowns, eight skill breakdowns and up to ten recent completed attempts. **Auto-graded practice accuracy** counts only automatically gradable answers. Written activity is tracked without treating ungraded responses as incorrect. No data is not 0%. These figures are not an examination grade or a mastery assessment. Staff do not have access to another user's Student Progress page; use Manual Grading for submitted written work.

## Manual Grading

Open **Manual Grading**. Filter by **Awaiting grading**, **Completed** or **All manual work**, then open an attempt. Compare the student's response with the historical question and reference solution. Enter awarded points within the displayed maximum and optional feedback, then **Save Grade** (or **Update Grade** for an existing grade). Check for a successful saved result before leaving.

Only submitted FREE_RESPONSE answers can be manually graded. Objective answers cannot be overridden here. An unanswered written response can receive only zero points. Re-grading updates the current grade; there is no full grade-revision audit trail or separate release/publish step. Saved feedback is available to the student through results/review. Staff access is role-wide, not assigned to particular teaching groups.

## Assessment Documents

Open **Assessment Documents**. Under **Create semester configuration**, enter the academic year, Fall/Spring term and display label, and use **Save semester**. Choose **Open / Edit** on an existing configuration to edit it. Deleting a configuration removes its assessment configuration data, including associated events and rooms; use the confirmation carefully.

Select one of the seven document tabs: **Dates of Assessments**, **Endterm Test Information**, **Rules of Assessment**, **Plus Points Rules**, **Midterm Test Information**, **Midterm/Endterm Retake Information**, or **Coursework Assignment Information**. The left side shows relevant forms; the right side shows **Draft Preview**. On smaller screens they stack. Switching tabs preserves edits; navigating away/reloading may discard unsaved work.

Save each changed section using its own **Save …** control. There is no global Save. Shared semester rules and component policies are reused across documents: changing a shared value can affect more than one document. Topics, equipment, scores, grade thresholds and policies must be entered from confirmed course rules; AXIOM does not invent them.

- **Scheduled time** is the official interval used in Dates of Assessments. Actual writing times are separate; detailed documents fall back to scheduled times when writing times are absent.
- **Latest arrival time** is independent and shared consistently across arrival instructions. Optional missing values use neutral wording in generated documents.
- Save an assessment before assigning its rooms. Under **Room assignments**, use **+ Add room**, fill **Room** and **Practice groups**, and use **Remove** for unwanted rows. Separate group identifiers with commas. **Save room assignments** saves the rows. Empty rows are ignored; partial rows, duplicate rooms and a group assigned to two rooms in the same event are invalid. Different events may assign a group to different rooms.
- Coursework supports general submission deadlines/venues and group-specific overrides. Retake settings include seating instructions. Review each relevant section and save it separately.

**Draft Preview** updates while typing, including unsaved edits. It is a structured preview of the LaTeX content, not a pixel-identical PDF. **Download PDF** requires the relevant fields to match successfully saved values. Otherwise it displays: “You have unsaved changes. Please save your changes before downloading the PDF.” Save the indicated sections and retry. Downloading neither saves nor modifies the configuration. The PDF uses the selected template; inspect the downloaded document before distributing it.

The general **LaTeX / PDF Tools** item under **TOOLS · IN DEVELOPMENT** is still a placeholder. Use **Assessment Documents** for the implemented seven-document workflow; there is no general Exam Builder or arbitrary LaTeX editor.

## Common problems

| Problem                                           | Action                                                                                                                                                            |
| ------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Verification link fails                           | Request a new email, wait for the cooldown and use the newest link.                                                                                               |
| Staff page absent/access denied                   | Confirm your role with the service owner; signing in does not assign a staff role.                                                                                |
| Save fails                                        | Read validation errors and retain the page; a failed save is not confirmation that changes were stored.                                                           |
| PDF says another job is running                   | Wait and retry; compilation is deliberately limited to one job at a time.                                                                                         |
| PDF unavailable, timeout or unsupported character | Retry after the service wakes; report the generic message and document type to the maintainer, without credentials. Do not repeatedly submit duplicate downloads. |
| Preview and PDF differ                            | Pagination/fonts can differ. Use the PDF for final visual approval.                                                                                               |
| A tool says Coming soon                           | It is not implemented; do not plan teaching activities around it.                                                                                                 |

Before publishing academic documents, resolve the source-document ambiguities listed in [the template notes](milestone-9c-latex-rendering.md), including conflicting historical arrival times and coursework deadlines. The lecturer must confirm the intended current policy; historical source values are not authoritative defaults.
