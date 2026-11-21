import { useEffect, useMemo, useState } from "react";

import { deepDivePageUrl, type InterviewQuestionListItem, listInterviewQuestions } from "./api";
import { repoLabel, WHOLE_REPO } from "./repoLabel";
import { shuffle } from "./shuffle";

const ALL_REPOS = "";

/** Stateless flashcards: nothing about your answers is stored. */
export function Practice() {
  const [questions, setQuestions] = useState<InterviewQuestionListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [repoUrl, setRepoUrl] = useState(ALL_REPOS);
  const [deck, setDeck] = useState<InterviewQuestionListItem[]>([]);
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    listInterviewQuestions().then(setQuestions, (e: Error) => setError(e.message));
  }, []);

  const repoUrls = useMemo(() => [...new Set(questions?.map((q) => q.repo_url))], [questions]);

  const deal = () => {
    setDeck(shuffle((questions ?? []).filter((q) => repoUrl === ALL_REPOS || q.repo_url === repoUrl)));
    setIndex(0);
    setRevealed(false);
  };
  // Re-deal when the bank loads or the filter changes.
  useEffect(deal, [questions, repoUrl]);

  if (error)
    return (
      <p role="alert" className="note note--error">
        Could not load questions: {error}
      </p>
    );
  if (questions === null) return <p className="note">Loading questions…</p>;
  if (questions.length === 0) return <p className="note">No questions yet. Each deep dive adds a few.</p>;

  const card = deck.at(index);
  const next = () => {
    setIndex(index + 1);
    setRevealed(false);
  };

  return (
    <div className="practice">
      <div className="practice__toolbar">
        <label className="practice__filter">
          Repo{" "}
          <select value={repoUrl} onChange={(e) => setRepoUrl(e.target.value)}>
            <option value={ALL_REPOS}>All repos</option>
            {repoUrls.map((url) => (
              <option key={url} value={url}>
                {repoLabel(url).name}
              </option>
            ))}
          </select>
        </label>
        <span className="note practice__count">{card ? `${index + 1} of ${deck.length}` : `${deck.length} done`}</span>
        <button onClick={deal} className="btn btn--secondary">
          Shuffle
        </button>
      </div>
      {card ? (
        <article className="practice__card">
          <p className="practice__area">
            {repoLabel(card.repo_url).name} ·{" "}
            <a href={deepDivePageUrl(card.deep_dive_id)} target="_blank" rel="noopener">
              {card.node_name ?? WHOLE_REPO}
            </a>
          </p>
          <h2 className="practice__question">{card.question}</h2>
          {revealed ? (
            <p className="practice__answer">{card.answer}</p>
          ) : (
            <p className="note">Answer out loud first, then check.</p>
          )}
          <div className="practice__actions">
            {!revealed && (
              <button onClick={() => setRevealed(true)} className="btn">
                Show answer
              </button>
            )}
            {/* One prominent button at a time: Show answer first, then Next. */}
            <button onClick={next} className={revealed ? "btn" : "btn btn--secondary"}>
              Next
            </button>
          </div>
        </article>
      ) : (
        <p className="note">You went through every question. Shuffle to start again.</p>
      )}
    </div>
  );
}
