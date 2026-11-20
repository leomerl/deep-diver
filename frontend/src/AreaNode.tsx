import { Handle, type NodeProps, Position } from "@xyflow/react";
import { memo } from "react";

import type { AreaNode as AreaNodeType } from "./layout";

function AreaNodeView({ data }: NodeProps<AreaNodeType>) {
  const { node, selected, isScope } = data;
  const classes = [
    "area-card",
    node.grouping === "fallback" && "area-card--fallback",
    selected && "area-card--selected",
    isScope && "area-card--scope",
  ];
  return (
    <div className={classes.filter(Boolean).join(" ")} title={isScope ? "Back to the parent area" : undefined}>
      <Handle type="target" position={Position.Left} />
      <div className="area-card__title">
        <span className="area-card__name">
          {isScope && <span className="area-card__back">‹</span>}
          {node.name}
        </span>
        {node.childCount > 0 && (
          <span className="area-card__count" aria-label={`${node.childCount} sub-areas`}>
            {node.childCount}
            {!isScope && " ›"}
          </span>
        )}
      </div>
      {node.description && <p className="area-card__desc">{node.description}</p>}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

export const AreaNode = memo(AreaNodeView);
