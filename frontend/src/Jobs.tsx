import { useEffect, useState } from "react";

import { type JobRead, type JobState, listJobs, type StepStatus } from "./api";
import { POLL_MS } from "./polling";

const STREAMS: Record<string, string> = { "jobs:index": "Index", "jobs:deep_dive": "Deep dive", "jobs:notebook": "Notebook" };
const STATES: Record<JobState, string> = {
  queued: "Queued",
  running: "Running",
  retrying: "Waiting to retry",
  done: "Done",
  dead: "Failed",
};
const STEP_MARKS: Record<StepStatus, string> = { passed: "✓", running: "", failed: "✕", waiting: "·", skipped: "–" };

const time = (iso: string): string => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

/** Both queues, newest first, refreshed every few seconds while the page is open. */
export function Jobs() {
  const [jobs, setJobs] = useState<JobRead[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    const load = async () => {
      try {
        const loaded = await listJobs();
        if (!live) return;
        setJobs(loaded);
        setError(null);
      } catch (e) {
        if (live) setError((e as Error).message); // keep the last list; the next poll may recover
      }
    };
    load();
    const timer = setInterval(load, POLL_MS);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, []);

  if (jobs === null && error === null) return <p className="note">Loading jobs…</p>;
  const counts = (jobs ?? []).reduce<Partial<Record<JobState, number>>>((acc, j) => ({ ...acc, [j.state]: (acc[j.state] ?? 0) + 1 }), {});

  return (
    <>
      <h2 className="section-label">Jobs</h2>
      <p className="note">
        {(Object.keys(STATES) as JobState[]).map((s) => `${counts[s] ?? 0} ${STATES[s].toLowerCase()}`).join(" · ")}
      </p>
      {error && (
        <p role="alert" className="note note--error">
          Could not refresh jobs: {error}
        </p>
      )}
      {jobs?.length === 0 && <p className="note">No jobs yet. Add a repository or generate a deep dive.</p>}
      <ul className="jobs">
        {jobs?.map((job) => (
          <JobRow key={`${job.stream}/${job.entry_id}`} job={job} />
        ))}
      </ul>
    </>
  );
}

function JobRow({ job }: { job: JobRead }) {
  // A finished deep dive is still busy while its notebook job runs: the badge follows the chain's last job.
  const state = job.state === "done" && job.follow_up ? job.follow_up.state : job.state;
  return (
    <li className="jobs__job">
      <div className="jobs__head">
        <span className="jobs__label">{job.label}</span>
        <span className={`badge jobs__state jobs__state--${state}`}>
          {state === "running" && <span className="spinner" aria-hidden="true" />}
          {STATES[state]}
        </span>
      </div>
      <p className="note jobs__meta">
        {STREAMS[job.stream] ?? job.stream} · queued {time(job.queued_at)}
        {job.deliveries > 0 && ` · try ${job.deliveries}`}
        {job.consumer && ` · ${job.consumer}`}
      </p>
      {job.chain.length > 0 && (
        <ol className="jobs__chain" aria-label="Steps">
          {job.chain.map(({ name, status }) => (
            <li key={name} className={`jobs__step jobs__step--${status}`}>
              {status === "running" ? <span className="spinner" aria-hidden="true" /> : <span aria-hidden="true">{STEP_MARKS[status]}</span>}
              {name}
              <span className="visually-hidden"> ({status})</span>
            </li>
          ))}
        </ol>
      )}
      <JobHistory job={job} />
      {job.follow_up && <JobHistory job={job.follow_up} prefix={STREAMS[job.follow_up.stream] ?? job.follow_up.stream} />}
    </li>
  );
}

/** The job's last error and its events, folded away. `prefix` names a follow-up job shown under its parent. */
function JobHistory({ job, prefix }: { job: JobRead; prefix?: string }) {
  const failures = job.events.filter((e) => e.kind === "failed");
  const lastError = failures.at(-1);
  return (
    <>
      {lastError && (
        <details className="jobs__details">
          <summary className="note note--error">
            {prefix ? `${prefix} failed` : "Failed"} on try {lastError.delivery}
            {failures.length > 1 && ` (${failures.length} failures)`}
          </summary>
          <pre className="jobs__error">{lastError.detail}</pre>
        </details>
      )}
      {job.events.length > 0 && (
        <details className="jobs__details">
          <summary className="note">
            {prefix ? `${prefix} history` : "History"} ({job.events.length} events)
          </summary>
          <ol className="jobs__events">
            {job.events.map((e) => (
              <li key={e.id}>
                <time dateTime={e.created_at}>{time(e.created_at)}</time> try {e.delivery} · {e.kind}
                {e.kind === "step" && ` ${e.detail}`}
              </li>
            ))}
          </ol>
        </details>
      )}
    </>
  );
}
