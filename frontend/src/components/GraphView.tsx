import { useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  MarkerType,
  type NodeProps,
  type Node,
  type Edge,
  type ReactFlowInstance,
} from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import { Search, Shapes } from "lucide-react";
import { display, label, object, array } from "../lib/utils";
import type { Graph } from "../lib/api";
import { Empty, Badge } from "./common";
import type { Inspection } from "./EvidenceDrawer";
type Data = {
  title: string;
  subtitle: string;
  fields: { key: string; value: string }[];
  highlighted: boolean;
  changed: boolean;
  source: Record<string, unknown>;
};
function RecordNode({ data }: NodeProps<Node<Data>>) {
  return (
    <div
      className={`record-node ${data.highlighted ? "node-highlight" : ""} ${data.changed ? "node-changed" : ""}`}
    >
      <Handle type="target" position={Position.Top} />
      <div className="node-type">
        <Shapes size={12} />
        {data.subtitle}
      </div>
      <strong>{data.title}</strong>
      {data.fields.map((field) => (
        <div className="node-property" key={field.key}>
          <span>{field.key}</span>
          <b>{field.value}</b>
        </div>
      ))}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
const nodeTypes = { record: RecordNode };
export function GraphView({
  graph,
  schema,
  highlightIds = [],
  changedIds = [],
  onInspect,
}: {
  graph?: Graph;
  schema?: Record<string, unknown>;
  highlightIds?: string[];
  changedIds?: string[];
  onInspect: (selection: Inspection) => void;
}) {
  const [filter, setFilter] = useState("");
  const canvas = useRef<HTMLDivElement>(null);
  const flow = useRef<ReactFlowInstance<Node<Data>, Edge> | null>(null);
  const positions = useRef(new Map<string, { x: number; y: number }>());
  const rawNodes = graph?.nodes ?? array(schema?.nodes);
  const rawEdges = graph?.edges ?? array(schema?.edges);
  const { nodes, edges, matches } = useMemo(() => {
    const layout = new dagre.graphlib.Graph();
    layout.setGraph({ rankdir: "TB", nodesep: 40, ranksep: 75 });
    layout.setDefaultEdgeLabel(() => ({}));
    rawNodes.forEach((n) =>
      layout.setNode(String(n.id), { width: 230, height: 150 }),
    );
    rawEdges.forEach((e) => layout.setEdge(String(e.source), String(e.target)));
    dagre.layout(layout);
    let count = 0;
    const nodes: Node<Data>[] = rawNodes.map((n) => {
      const nodeId = String(n.id);
      const hit =
        !!filter &&
        JSON.stringify({
          label: n.label,
          type: n.type,
          properties: n.properties,
        })
          .toLowerCase()
          .includes(filter.toLowerCase());
      if (hit) count++;
      let p = positions.current.get(nodeId);
      if (!p) {
        const d = layout.node(nodeId);
        p = { x: d.x - 115, y: d.y - 70 };
        positions.current.set(nodeId, p);
      }
      const fields = schema
        ? array(n.properties)
            .slice(0, 4)
            .map((p) => ({
              key: String(p.label ?? p.name),
              value: `${p.required ? "Required · " : ""}${p.datatype_label ?? p.type}`,
            }))
        : Object.entries(object(n.properties))
            .filter(([k]) => !k.endsWith("_id"))
            .slice(0, 3)
            .map(([key, value]) => ({
              key: label(key),
              value: display(value),
            }));
      return {
        id: nodeId,
        type: "record",
        position: p,
        data: {
          title: String(n.label ?? label(n.id)),
          subtitle: String(n.type ?? n.kind ?? "Entity"),
          fields,
          highlighted: filter ? hit : highlightIds.includes(nodeId),
          changed: changedIds.includes(nodeId),
          source: n,
        },
        ariaLabel: `${n.label ?? nodeId}, ${n.type ?? "declaration"}`,
      };
    });
    const edges: Edge[] = rawEdges.map((e, i) => ({
      id: String(e.id ?? `${e.source}:${e.target}:${i}`),
      source: String(e.source),
      target: String(e.target),
      label: String(e.label ?? e.relation ?? ""),
      type: "smoothstep",
      style: {
        stroke: e.kind === "disjoint" ? "#b6898c" : "#8793ab",
        strokeDasharray: e.kind === "disjoint" ? "4 4" : undefined,
      },
      markerEnd:
        e.kind === "disjoint"
          ? undefined
          : { type: MarkerType.ArrowClosed, color: "#8793ab" },
      data: e,
    }));
    return { nodes, edges, matches: count };
  }, [rawNodes, rawEdges, filter, highlightIds, changedIds, schema]);
  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    const observer = new ResizeObserver(() => {
      requestAnimationFrame(() => {
        void flow.current?.fitView({ padding: 0.18, maxZoom: 1 });
      });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [!!graph, !!schema]);
  if (!graph && !schema)
    return (
      <Empty title="No snapshot recorded">
        This step has no saved graph evidence.
      </Empty>
    );
  return (
    <div className="graph-view">
      <div className="graph-tools">
        <label className="search-input">
          <Search size={15} />
          <input
            aria-label="Highlight graph records"
            placeholder="Highlight records…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </label>
        <div className="inline">
          <Badge>
            {graph ? graph.total_nodes.toLocaleString() : nodes.length}{" "}
            {schema ? "types" : "nodes"}
          </Badge>
          <Badge>
            {graph ? graph.total_edges.toLocaleString() : edges.length}{" "}
            {schema ? "declarations" : "edges"}
          </Badge>
        </div>
      </div>
      {filter && (
        <div className="filter-note">
          {matches} matching {matches === 1 ? "record" : "records"}. All{" "}
          {nodes.length} displayed records remain visible.
        </div>
      )}
      <div
        ref={canvas}
        className="graph-canvas"
        data-testid="graph-canvas"
        data-node-count={nodes.length}
        data-edge-count={edges.length}
        data-highlight-count={
          nodes.filter((node) => node.data.highlighted).length
        }
      >
        {nodes.length ? (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            nodesDraggable={false}
            nodesConnectable={false}
            edgesReconnectable={false}
            deleteKeyCode={null}
            fitView
            fitViewOptions={{ padding: 0.18, maxZoom: 1 }}
            onInit={(instance) => {
              flow.current = instance;
            }}
            minZoom={0.15}
            maxZoom={1.6}
            colorMode="system"
            onNodeClick={(_, node) =>
              onInspect({ title: node.data.title, data: node.data.source })
            }
            onEdgeClick={(_, edge) =>
              onInspect({ title: String(edge.label), data: object(edge.data) })
            }
          >
            <Background gap={22} size={1} />
            <Controls showInteractive={false} />
          </ReactFlow>
        ) : (
          <Empty title={schema ? "No declarations recorded" : "Empty graph"}>
            This saved snapshot contains no records.
          </Empty>
        )}
      </div>
      {graph && (graph.omitted_nodes > 0 || graph.omitted_edges > 0) && (
        <div className="graph-footer">
          Showing {graph.shown_nodes.toLocaleString()} of{" "}
          {graph.total_nodes.toLocaleString()} nodes and{" "}
          {graph.shown_edges.toLocaleString()} of{" "}
          {graph.total_edges.toLocaleString()} edges.{" "}
          {graph.omitted_nodes.toLocaleString()} nodes and{" "}
          {graph.omitted_edges.toLocaleString()} edges omitted.
        </div>
      )}
    </div>
  );
}
