import type { Event } from "../lib/api";
import { short } from "../lib/utils";
import { Badge } from "./common";
import type { Inspection } from "./EvidenceDrawer";

export function InferenceContext({
  events,
  onInspect,
}: {
  events: Event[];
  onInspect: (selection: Inspection) => void;
}) {
  const discovery = [...events]
    .reverse()
    .find((event) => event.inference_discovery)?.inference_discovery;
  const snapshot = [...events]
    .reverse()
    .find((event) => event.inference_context)?.inference_context;
  if (!discovery && !snapshot) return null;
  const catalogRef = snapshot?.catalog_ref ?? discovery?.catalog_ref;
  const loaded = snapshot?.context.loaded_function_ids ?? [];
  const definitions = snapshot?.context.view_definition_ids ?? [];
  const evicted = snapshot?.context.evicted_definition_ids ?? [];
  const lookupEvicted = discovery?.context?.evicted_definition_ids ?? [];
  const results = discovery?.result_ids ?? [];
  const inspect = (title: string, artifactId: string | null | undefined) => {
    if (artifactId) onInspect({ title, artifactId });
  };
  return (
    <section className="flow-evidence" aria-label="Inference discovery context">
      <div className="inline">
        <h3>Inference context</h3>
        <Badge>Context acquisition</Badge>
      </div>
      <p className="muted small">
        Kernel {short(snapshot?.kernel_id ?? discovery?.kernel_id)} · Catalog{" "}
        {short(snapshot?.catalog_id ?? discovery?.catalog_id)}
      </p>
      {snapshot && (
        <>
          <p className="small">
            Last exposed snapshot:{" "}
            {snapshot.context.context_bytes.toLocaleString()} /{" "}
            {snapshot.context.max_context_bytes.toLocaleString()} bytes. Loaded
            functions: {loaded.length}.
          </p>
          <details>
            <summary>Definitions in that snapshot</summary>
            <ul>
              {[...new Set([...loaded, ...definitions])].map((identity) => (
                <li key={identity}>
                  <code>{identity}</code>
                </li>
              ))}
            </ul>
            {!!evicted.length && (
              <p className="small">
                Evicted from context: {evicted.join(", ")}. Definitions remain
                available for inspection.
              </p>
            )}
          </details>
          {snapshot.view_ref && (
            <button
              className="text-button"
              onClick={() =>
                inspect("Exact exposed context snapshot", snapshot.view_ref)
              }
            >
              Inspect exposed snapshot
            </button>
          )}
        </>
      )}
      {discovery && (
        <details>
          <summary>Latest lookup: {discovery.tool}</summary>
          <p className="small">
            {discovery.query
              ? `Query: ${discovery.query}`
              : "Empty query or direct definition lookup"}
            {" · "}Kind: {discovery.kind}
          </p>
          {discovery.definition_id && (
            <p className="small">
              <code>
                {discovery.definition_id}
                {discovery.pointer}
              </code>
            </p>
          )}
          {discovery.status === "ok" && (
            <p className="small">
              {(!!discovery.result_count ||
                !!discovery.total_count ||
                !discovery.definition_id) && (
                <>
                  {discovery.result_count} entries returned from{" "}
                  {discovery.total_count}; offset {discovery.offset}.
                </>
              )}
              {discovery.has_more
                ? " A continuation is recorded."
                : " No further page in this lookup."}
              {!discovery.complete &&
                " Further pages or definition fragments remain available."}
            </p>
          )}
          {!!results.length && (
            <ul>
              {results.map((identity) => (
                <li key={identity}>
                  <code>{identity}</code>
                </li>
              ))}
            </ul>
          )}
          {!!discovery.dependency_count && (
            <p className="small">
              Dependencies ({discovery.dependency_count}):{" "}
              {(discovery.dependencies ?? []).join(", ")}
              {!!discovery.omitted_dependencies &&
                `; ${discovery.omitted_dependencies} further entries in the receipt`}
              .
            </p>
          )}
          {discovery.loaded_tool_name && (
            <p className="small">
              Loaded tool: <code>{discovery.loaded_tool_name}</code>
            </p>
          )}
          {discovery.error && <p className="error-box">{discovery.error}</p>}
          {!!discovery.truncated_fields?.length && (
            <p className="muted small">
              Full {discovery.truncated_fields.join(", ")} values are in the
              lookup artifact.
            </p>
          )}
          {!!lookupEvicted.length && (
            <p className="small">
              Evicted by this lookup: {lookupEvicted.join(", ")}.
            </p>
          )}
          <div className="inline">
            <button
              className="text-button"
              onClick={() =>
                inspect(
                  "Discovery receipt and continuation",
                  discovery.artifact_id,
                )
              }
            >
              Inspect lookup
            </button>
            {discovery.state_ref && (
              <button
                className="text-button"
                onClick={() =>
                  inspect("Discovery state after lookup", discovery.state_ref)
                }
              >
                Inspect saved state
              </button>
            )}
          </div>
        </details>
      )}
      {catalogRef && (
        <button
          className="text-button"
          onClick={() => inspect("Frozen inference catalog", catalogRef)}
        >
          Inspect catalog version
        </button>
      )}
      <p className="muted small">
        These lookups expose definitions. Task results and source citations come
        from function execution.
      </p>
    </section>
  );
}
