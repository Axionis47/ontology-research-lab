import type { Event } from "../lib/api";
import { label, object } from "../lib/utils";
import { Badge, Status } from "./common";
import type { Inspection } from "./EvidenceDrawer";

type Props = {
  events: Event[];
  onInspect: (selection: Inspection) => void;
};

/** Keep candidate proposals and independent checks visibly separate. */
export function ConstructionFlows({ events, onInspect }: Props) {
  return (
    <section className="flow-evidence-grid" aria-label="Construction flows">
      {(["learning", "verification"] as const).map((flow) => {
        const recorded = events.filter((event) => event.flow === flow);
        const last = recorded.at(-1);
        return (
          <div className="flow-evidence" key={flow}>
            <div className="inline">
              <h3>
                {flow === "learning"
                  ? "Learning reusable capabilities"
                  : "Independent verification"}
              </h3>
              <Badge>
                {recorded.length
                  ? `${recorded.length} records`
                  : "Not recorded"}
              </Badge>
            </div>
            <p className="muted small">
              {flow === "learning"
                ? "Requirements, derived subtasks, evidence demands, and candidate selection."
                : "Checks and counterexamples for the candidate and its protected behavior."}
            </p>
            {flow === "verification" && (
              <p className="muted small">
                Generated checks measure consistency. Independent task
                assessment and preservation proofs remain separate evidence.
              </p>
            )}
            {last && (
              <button
                className="text-button"
                onClick={() =>
                  onInspect({
                    title: label(flow),
                    data: last.payload,
                    artifactId: last.artifact_refs?.[0]?.id,
                  })
                }
              >
                {last.summary}
              </button>
            )}
          </div>
        );
      })}
    </section>
  );
}

/** Show observed evidence scope at the playhead, independently of display limits. */
export function MaterializationEvidence({ events, onInspect }: Props) {
  const last = events.filter((event) => event.flow === "instantiation").at(-1);
  const detail = object(last?.payload);
  const sufficiency = object(detail.sufficiency);
  const status =
    sufficiency.status ??
    detail.sufficiency_status ??
    (detail.nonblocking === true ? detail.status : undefined);
  return (
    <div className="flow-evidence" aria-label="Materialization scope">
      <div className="inline">
        <strong>Evidence for this question</strong>
        <Status value={status ? String(status) : null} />
      </div>
      <p className="muted small">
        {last?.summary ??
          "No demand or evidence-scope observation recorded at this step."}
      </p>
      <p className="muted small">
        Materialized evidence and the displayed graph projection have separate
        scopes.
      </p>
      {last && (
        <button
          className="text-button"
          onClick={() =>
            onInspect({
              title: "Materialization evidence",
              data: last.payload,
              artifactId: last.artifact_refs?.[0]?.id,
            })
          }
        >
          Inspect demand and observed scope
        </button>
      )}
    </div>
  );
}
