"""Offline interview practice with a small curated question bank. Local self-ratings only; no AI grading, no uploads."""
from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

NOTICE = "Offline practice from a small fixed question bank with your own self-ratings. This is not an interview guarantee, an AI assessment of your answer, or a complete syllabus; questions stay on this machine and nothing is uploaded. "
RATINGS = ("hard", "shaky", "ok", "confident")

# Curated starter bank: (topic, question, key points to self-check). Deliberately small and reviewable.
BANK = [
    ("aws", "Explain what happens when an EC2 instance in a private subnet needs to reach the internet.",
     "NAT gateway vs NAT instance, route tables, security groups vs NACLs, cost trade-offs."),
    ("aws", "How would you design an S3 + CloudFront setup for a static site with private content?",
     "Origin access control, signed URLs/cookies, bucket policy, TTLs, invalidation."),
    ("aws", "Difference between IAM roles, policies and instance profiles, and when you would use each.",
     "Trust policy vs permission policy, assume-role, least privilege, no long-lived keys."),
    ("ci-cd", "Walk through a CI/CD pipeline you would set up for a Python service from commit to production.",
     "Stages (lint, test, build, scan, deploy), artifacts, environment promotion, rollback."),
    ("ci-cd", "Blue-green vs canary vs rolling deployments: when would you pick each?",
     "Traffic shift mechanics, blast radius, database compatibility, rollback speed."),
    ("docker", "A container keeps restarting in production. How do you debug it?",
     "docker logs/events, exit codes, health checks, resource limits, entrypoint vs cmd."),
    ("docker", "Explain image layers and three concrete ways to shrink an image.",
     "Multi-stage builds, smaller base images, layer caching, .dockerignore."),
    ("kubernetes", "A pod is stuck in CrashLoopBackOff. What is your debugging sequence?",
     "kubectl describe/logs --previous, probes, resource limits, config/secrets, image pull."),
    ("kubernetes", "Requests vs limits, and what happens to a pod that exceeds each.",
     "CPU throttling vs memory OOMKill, QoS classes, scheduling."),
    ("linux", "A disk is full but df and du disagree. What do you check?",
     "Deleted open files (lsof), mounts shadowing data, inodes, reserved blocks."),
    ("linux", "Explain the boot troubleshooting steps when a Linux box does not come up after a change.",
     "Logs (journalctl), single-user/rescue mode, fstab errors, recent package/config changes."),
    ("terraform", "How does Terraform state work and how do you keep it safe in a team?",
     "Remote backend, locking, state vs reality drift, import, no manual edits."),
    ("terraform", "Plan shows a resource being destroyed that must not be. What do you do?",
     "Stop, read the plan, lifecycle prevent_destroy, moved blocks, targeted apply as last resort."),
    ("monitoring", "What is the difference between an SLI, an SLO and an SLA, with one example each?",
     "Indicator vs target vs contract, error budgets, alerting on burn rate."),
    ("monitoring", "You get paged for high latency. What do you look at in the first five minutes?",
     "Dashboards first, recent deploys, saturation vs errors, correlate traces/logs, communicate."),
    ("behavioral", "Tell me about a production incident you handled end to end.",
     "STAR structure, your specific role, detection to postmortem, what changed after."),
]

TOPICS = sorted({topic for topic, _, _ in BANK})


def _topic(value):
    if value not in TOPICS:
        raise ValueError("topic must be one of: " + ", ".join(TOPICS))
    return value


def _rating(value):
    if value not in RATINGS:
        raise ValueError("rating must be one of: " + ", ".join(RATINGS))
    return value


def _notes(value):
    if type(value) is not str or len(value.strip()) > 500 or any(ord(c) < 32 for c in value):
        raise ValueError("notes must be bounded plain text without control characters.")
    return value.strip()


class InterviewPractice:
    def __init__(self, path=None):
        self.path = Path(path or os.getenv("AETHER_PRACTICE_DB") or Path.home() / ".aether" / "practice.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_CREAT | os.O_WRONLY, 0o600); os.close(fd)
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS practice(
                question_id INTEGER PRIMARY KEY, shown_count INTEGER NOT NULL DEFAULT 0,
                last_shown TEXT, last_rating TEXT, rating_count INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '', updated TEXT);''')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10); db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def topics():
        counts = {}
        for topic, _, _ in BANK:
            counts[topic] = counts.get(topic, 0) + 1
        return {"topics": [{"topic": t, "questions": counts[t]} for t in TOPICS],
                "total": len(BANK), "ratings": list(RATINGS), "notice": NOTICE}

    def next_question(self, topic):
        topic = _topic(topic)
        candidates = [(i, q) for i, (t, q, _) in enumerate(BANK) if t == topic]
        with self.connect() as db:
            rows = {r["question_id"]: r for r in db.execute(
                "SELECT * FROM practice WHERE question_id IN (%s)" % ",".join(str(i) for i, _ in candidates))}
        # Least shown first, then least recently shown, then lowest id: deterministic, no randomness.
        def sort_key(item):
            i, _ = item
            row = rows.get(i)
            return (row["shown_count"] if row else 0, (row["last_shown"] or "") if row else "", i)
        pick_id, pick_q = sorted(candidates, key=sort_key)[0]
        now = datetime.now(UTC).isoformat()
        with self.connect() as db:
            db.execute('''INSERT INTO practice(question_id, shown_count, last_shown, updated) VALUES(?,1,?,?)
                          ON CONFLICT(question_id) DO UPDATE SET shown_count=shown_count+1, last_shown=?, updated=?''',
                       (pick_id, now, now, now, now))
        key_points = next(k for i, (t, q, k) in enumerate(BANK) if i == pick_id)
        return {"question_id": pick_id, "topic": topic, "question": pick_q,
                "self_check_points": key_points,
                "notice": NOTICE + "Answer aloud or in writing first, then compare against the self-check points and rate yourself with interview_record."}

    def record(self, question_id, rating, notes=""):
        if type(question_id) is not int or not 0 <= question_id < len(BANK):
            raise ValueError(f"question_id must be an integer 0-{len(BANK) - 1} from interview_question.")
        rating = _rating(rating); notes = _notes(notes) if notes else ""
        now = datetime.now(UTC).isoformat()
        with self.connect() as db:
            db.execute('''INSERT INTO practice(question_id, shown_count, last_rating, rating_count, notes, updated)
                          VALUES(?,0,?,1,?,?)
                          ON CONFLICT(question_id) DO UPDATE SET last_rating=?, rating_count=rating_count+1, notes=?, updated=?''',
                       (question_id, rating, notes, now, rating, notes, now))
        topic, question, _ = BANK[question_id]
        return {"question_id": question_id, "topic": topic, "rating": rating, "recorded": True,
                "notice": NOTICE + "A self-rating describes how the practice felt to you; it is not a measured skill score."}

    def progress(self):
        with self.connect() as db:
            rows = {r["question_id"]: r for r in db.execute("SELECT * FROM practice")}
        per_topic = {t: {"questions": 0, "practised": 0, "ratings": {r: 0 for r in RATINGS}} for t in TOPICS}
        for i, (topic, _, _) in enumerate(BANK):
            per_topic[topic]["questions"] += 1
            row = rows.get(i)
            if row and row["shown_count"] > 0:
                per_topic[topic]["practised"] += 1
            if row and row["last_rating"]:
                per_topic[topic]["ratings"][row["last_rating"]] += 1
        return {"per_topic": per_topic, "total_questions": len(BANK),
                "practised_at_least_once": sum(1 for i in range(len(BANK)) if rows.get(i) and rows[i]["shown_count"] > 0),
                "notice": NOTICE + "A self-rating breakdown is practice bookkeeping, not a skill score. Counts reflect only practice recorded here; 'hard' items are the ones to revisit first."}


def register_interview_practice(registry):
    from aether.tools.registry import Risk, Tool
    string = {"type": "string"}; integer = {"type": "integer"}
    definitions = [
        ("interview_topics", "List practice topics and question counts from the fixed local bank (aws, ci-cd, docker, kubernetes, linux, terraform, monitoring, behavioral).",
         {}, [], lambda **kw: InterviewPractice.topics(), Risk.SAFE),
        ("interview_question", "Draw the next practice question for one topic (least-shown first, deterministic). Includes self-check points; answer first, then self-rate.",
         {"topic": string}, ["topic"], lambda **kw: InterviewPractice().next_question(**kw), Risk.LOW),
        ("interview_record", "Record your self-rating (hard/shaky/ok/confident) and optional notes for one question id from interview_question.",
         {"question_id": integer, "rating": {"type": "string", "enum": list(RATINGS)}, "notes": string},
         ["question_id", "rating"], lambda **kw: InterviewPractice().record(**kw), Risk.LOW),
        ("interview_progress", "Per-topic practice counts and self-rating breakdown from the local store. Not a skill score.",
         {}, [], lambda **kw: InterviewPractice().progress(), Risk.SAFE),
    ]
    for name, description, props, required, handler, risk in definitions:
        registry.register(Tool(name=name, description=description,
                               parameters={"type": "object", "properties": props, "required": required, "additionalProperties": False},
                               handler=handler, risk=risk, category="practice",
                               requires_confirmation=risk >= Risk.MEDIUM, never_auto_approve=risk >= Risk.MEDIUM,
                               allow_auto_approve=risk < Risk.MEDIUM, allow_always=risk < Risk.MEDIUM))
