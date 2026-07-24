"use client";

import { FormEvent, useState } from "react";

import { trackBetaEvent } from "@/components/beta/analytics-tracker";
import { Button } from "@/components/ui/button";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export function FeedbackForm() {
  const [category, setCategory] = useState("general");
  const [message, setMessage] = useState("");
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "unavailable">("idle");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("sending");
    try {
      const response = await fetch(`${apiBaseUrl}/public/beta-feedback`, {
        body: JSON.stringify({
          category,
          contact_email: email || null,
          message,
          page_path: window.location.pathname,
        }),
        headers: { "Content-Type": "application/json" },
        method: "POST",
      });
      if (!response.ok) {
        throw new Error("Feedback endpoint unavailable");
      }
      trackBetaEvent("feedback_submitted", "feedback");
      setMessage("");
      setEmail("");
      setStatus("sent");
    } catch {
      setStatus("unavailable");
    }
  }

  return (
    <form className="grid gap-5" onSubmit={submit}>
      <div className="grid gap-2">
        <label className="text-sm font-medium" htmlFor="feedback-category">What would you like to share?</label>
        <select
          className="min-h-11 border border-rule-strong bg-canvas px-3 text-sm"
          id="feedback-category"
          onChange={(event) => setCategory(event.target.value)}
          value={category}
        >
          <option value="idea">Idea or request</option>
          <option value="source">Source coverage or correction</option>
          <option value="bug">Something did not work</option>
          <option value="general">General feedback</option>
        </select>
      </div>
      <div className="grid gap-2">
        <label className="text-sm font-medium" htmlFor="feedback-message">Feedback</label>
        <textarea
          className="min-h-32 border border-rule-strong bg-canvas p-3 text-sm leading-6"
          id="feedback-message"
          maxLength={2000}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="Tell us what would make this more useful for your community."
          required
          value={message}
        />
      </div>
      <div className="grid gap-2">
        <label className="text-sm font-medium" htmlFor="feedback-email">Email (optional)</label>
        <input
          className="min-h-11 border border-rule-strong bg-canvas px-3 text-sm"
          id="feedback-email"
          maxLength={320}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="Only if you would like a follow-up."
          type="email"
          value={email}
        />
      </div>
      <p className="text-xs leading-5 text-ink-muted">Do not include sensitive personal information. We use feedback to improve the public beta.</p>
      <div className="flex flex-wrap items-center gap-4">
        <Button disabled={status === "sending"} type="submit">
          {status === "sending" ? "Sending…" : "Send feedback"}
        </Button>
        {status === "sent" ? <p className="text-sm text-ink-muted">Thank you — your feedback was received.</p> : null}
        {status === "unavailable" ? <p className="text-sm text-ink-muted">Feedback is not available in this preview. Please try again later.</p> : null}
      </div>
    </form>
  );
}
