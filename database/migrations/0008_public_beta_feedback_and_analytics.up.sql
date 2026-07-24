BEGIN;

CREATE TABLE core.public_beta_feedback (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  category text NOT NULL CHECK (category IN ('bug', 'idea', 'source', 'general')),
  message text NOT NULL CHECK (length(trim(message)) BETWEEN 1 AND 2000),
  contact_email citext CHECK (contact_email IS NULL OR length(contact_email::text) <= 320),
  page_path text NOT NULL CHECK (length(trim(page_path)) BETWEEN 1 AND 160),
  status text NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'reviewed', 'closed')),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE core.public_beta_analytics_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_name text NOT NULL CHECK (
    event_name IN (
      'beta_page_view',
      'demo_started',
      'example_notebook_opened',
      'feedback_opened',
      'feedback_submitted'
    )
  ),
  page_path text NOT NULL CHECK (length(trim(page_path)) BETWEEN 1 AND 160),
  surface text CHECK (surface IN ('landing', 'demo', 'notebook', 'feedback')),
  occurred_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX public_beta_feedback_status_created_idx
  ON core.public_beta_feedback (status, created_at DESC);
CREATE INDEX public_beta_analytics_event_created_idx
  ON core.public_beta_analytics_events (event_name, occurred_at DESC);

CREATE FUNCTION core.submit_public_beta_feedback(
  feedback_category text,
  feedback_message text,
  feedback_contact_email citext,
  feedback_page_path text
)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, core
AS $$
  INSERT INTO core.public_beta_feedback (category, message, contact_email, page_path)
  VALUES (feedback_category, feedback_message, feedback_contact_email, feedback_page_path);
$$;

CREATE FUNCTION core.record_public_beta_analytics_event(
  analytics_event_name text,
  analytics_page_path text,
  analytics_surface text
)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, core
AS $$
  INSERT INTO core.public_beta_analytics_events (event_name, page_path, surface)
  VALUES (analytics_event_name, analytics_page_path, analytics_surface);
$$;

REVOKE ALL ON TABLE core.public_beta_feedback FROM PUBLIC;
REVOKE ALL ON TABLE core.public_beta_analytics_events FROM PUBLIC;
REVOKE ALL ON FUNCTION core.submit_public_beta_feedback(text, text, citext, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION core.record_public_beta_analytics_event(text, text, text) FROM PUBLIC;

COMMENT ON TABLE core.public_beta_analytics_events
  IS 'Aggregate public-beta event records; intentionally contains no user identifier, query, or IP address.';
COMMENT ON TABLE core.public_beta_feedback
  IS 'Voluntary public-beta feedback, retained separately from civic research data.';

COMMIT;
