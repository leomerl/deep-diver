import { Handle, type NodeProps, Position } from "@xyflow/react";
import { memo } from "react";

import type { RepoNode as RepoNodeType } from "./layout";
import { repoLabel } from "./repoLabel";

function RepoNodeView({ data }: NodeProps<RepoNodeType>) {
  const { name, host } = repoLabel(data.repo.url);
  return (
    <div className="area-card repo-card">
      <div className="area-card__title">
        <span className="area-card__name">{name}</span>
      </div>
      <p className="area-card__desc">
        {host} · {data.areaCount} areas · {data.repo.commit_sha?.slice(0, 7)}
      </p>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

export const RepoNode = memo(RepoNodeView);
