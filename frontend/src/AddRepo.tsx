import { type FormEvent, useState } from "react";

import { addRepo, ApiError } from "./api";

type Props = { onAdded: (normalizedUrl: string) => void };

export function AddRepo({ onAdded }: Props) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onAdded((await addRepo(url)).url);
      setUrl("");
    } catch (err) {
      setError(err instanceof ApiError && err.status === 503 ? "Queue unavailable, try again" : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit}>
      <div className="add-repo__field">
        <input
          type="url"
          required
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://github.com/owner/repo"
          aria-label="Repository URL"
          className="add-repo__input"
        />
        <button type="submit" disabled={busy} className="btn">
          Add
        </button>
      </div>
      {error && (
        <p role="alert" className="note note--error">
          {error}
        </p>
      )}
    </form>
  );
}
