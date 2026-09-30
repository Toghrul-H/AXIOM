"use client";
import Link from "next/link";
import { ArrowRight, BookOpen } from "lucide-react";
import { orderedTopics, useMetadata } from "@/lib/use-metadata";

export function CourseTopics({ outline = false }: { outline?: boolean }) {
  const { metadata, error } = useMetadata();
  if (error)
    return (
      <p className="error-message" role="alert">
        Course outline unavailable: {error}
      </p>
    );
  if (!metadata)
    return (
      <p className="empty-inline" role="status">
        Loading course topics…
      </p>
    );
  const topics = orderedTopics(metadata.topics);
  if (outline)
    return (
      <div className="learn-grid">
        {topics.map(({ topic, label }) => (
          <section className="panel learn-card" id={topic.slug} key={topic.id}>
            <span className="topic-symbol teal">
              <BookOpen size={19} />
            </span>
            <span className="eyebrow">
              {topic.parent ? "SUBTOPIC" : "COURSE AREA"}
            </span>
            <h2>{topic.name}</h2>
            <p>{label}</p>
            <span className="coming-label">
              Learning materials coming later
            </span>
          </section>
        ))}
      </div>
    );
  return (
    <div className="topic-grid">
      {topics
        .filter(
          ({ topic }) => !metadata.topics.some((t) => t.parent_id === topic.id),
        )
        .map(({ topic, label }, index) => (
          <Link
            href={`/student/learn#${topic.slug}`}
            className="topic-card"
            key={topic.id}
          >
            <div className="topic-card-top">
              <span className="topic-symbol teal">
                <BookOpen size={18} />
              </span>
              <span className="topic-number">
                {String(index + 1).padStart(2, "0")}
              </span>
            </div>
            <h3>{topic.name}</h3>
            <p>{label}</p>
            <div className="topic-card-footer">
              <span>Explore topic</span>
              <ArrowRight size={16} />
            </div>
          </Link>
        ))}
    </div>
  );
}
