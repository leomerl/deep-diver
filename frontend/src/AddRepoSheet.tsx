import { useEffect, useRef } from "react";

import { AddRepo } from "./AddRepo";
import { GitHubRepos } from "./GitHubRepos";

type Props = { open: boolean; onClose: () => void; onAdded: (normalizedUrl: string) => void };

/** Modal sheet for adding a repo: paste a URL or pick one of your GitHub repos. Esc closes it (native <dialog>). */
export function AddRepoSheet({ open, onClose, onAdded }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (open) dialog.current?.showModal();
    else dialog.current?.close();
  }, [open]);

  const added = (url: string) => {
    onAdded(url);
    onClose();
  };

  return (
    <dialog ref={dialog} onClose={onClose} className="sheet" aria-labelledby="add-repo-title">
      {/* Children mount only while open, so the GitHub list is fetched when the sheet opens, not on page load. */}
      {open && (
        <>
          <header className="sheet__header">
            <h2 id="add-repo-title" className="sheet__title">
              Add Repository
            </h2>
            <button onClick={onClose} className="btn btn--secondary">
              Cancel
            </button>
          </header>
          <div className="sheet__body">
            <AddRepo onAdded={added} />
            <GitHubRepos onAdded={added} />
          </div>
        </>
      )}
    </dialog>
  );
}
