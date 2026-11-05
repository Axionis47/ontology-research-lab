import type { Event } from "../lib/api";
import type { components } from "../api.generated";
import { label, object, short } from "../lib/utils";
import { Badge, Status } from "./common";
import type { Inspection } from "./EvidenceDrawer";

type Props = {
  events: Event[];
  onInspect: (selection: Inspection) => void;
};
type Evidence = components["schemas"]["FlowEvidence"];

const actions: Record<string, string> = {
  reuse: "Reuse recorded evidence",
  proof: "Preservation proof",
  replay: "Execute frozen function",
  rematerialize: "Materialize retained sources",
  defer: "Deferred",
};

function EvaluationActions({
  evidence,
  onInspect,
}: {
  evidence: Evidence;
  onInspect: Props["onInspect"];
}) {
  if (!evidence.actions?.length) return null;
  return (
    <details>
      <summary>
        Recorded evaluation decisions (
        {Object.values(evidence.action_counts ?? {}).reduce((a, b) => a + b, 0)}
        )
      </summary>
      <div className="case-list">
        {evidence.actions.map((action, index) => (
          <div className="case-card" key={`${action.case_id}-${index}`}>
            <div className="inline">
              <strong>{action.case_id}</strong>
              <Badge>
                {actions[action.local_action] ?? label(action.local_action)}
              </Badge>
              {action.status && (
                <span className="inline">
                  Local check <Status value={action.status} />
                </span>
              )}
            </div>
            <p className="small">
              Planner: {label(action.planner_action ?? "not recorded")}
            </p>
            {(action.reasons ?? []).map((reason, i) => (
              <p className="muted small" key={i}>
                {reason}
              </p>
            ))}
            {action.planner_reason && (
              <p className="muted small">{action.planner_reason}</p>
            )}
            {action.source_candidate_id && (
              <p className="muted small">
                Evidence retained from candidate{" "}
                {short(action.source_candidate_id)}.
              </p>
            )}
            {action.fresh_candidate_id && (
              <p className="muted small">
                Fresh agent execution on candidate{" "}
                {short(action.fresh_candidate_id)}.
              </p>
            )}
            {action.task_assessment && (
              <p className="small">
                Task assessment: {label(action.task_assessment)}
              </p>
            )}
            <button
              className="text-button"
              onClick={() =>
                onInspect({
                  title: `Evaluation: ${action.case_id}`,
                  data: action,
                  artifactId:
                    action.evidence_refs?.[0] ??
                    evidence.artifact_id ??
                    undefined,
                })
              }
            >
              Inspect evidence and dependencies
            </button>
          </div>
        ))}
      </div>
      {!!evidence.omitted_actions && (
        <p className="muted small">
          {evidence.omitted_actions} further decisions in the source artifact.
        </p>
      )}
    </details>
  );
}

function CallableChecks({
  evidence,
  onInspect,
}: {
  evidence: Evidence;
  onInspect: Props["onInspect"];
}) {
  if (!evidence.checks?.length) return null;
  return (
    <details>
      <summary>Callable and verification checks</summary>
      <div className="case-list">
        {evidence.checks.map((check, index) => (
          <div className="case-card" key={`${check.id}-${index}`}>
            <div className="inline">
              <Badge>{label(check.dimension)}</Badge>
              <Status value={check.status} />
            </div>
            <strong>
              {check.function_name ?? check.id ?? "Recorded check"}
            </strong>
            <p className="small">{check.summary}</p>
            <button
              className="text-button"
              onClick={() =>
                onInspect({
                  title: "Callable check",
                  data: check,
                  artifactId:
                    check.evidence_refs?.[0] ??
                    evidence.artifact_id ??
                    undefined,
                })
              }
            >
              Inspect check
            </button>
          </div>
        ))}
      </div>
      {!!evidence.omitted_checks && (
        <p className="muted small">
          {evidence.omitted_checks} further checks in the source artifact.
        </p>
      )}
    </details>
  );
}

/** Display execution evidence, preserving original case and assessment identities. */
export function HistoricalReplayEvidence({ events, onInspect }: Props) {
  const event = events
    .filter((item) => item.flow_evidence?.historical_replay)
    .at(-1);
  const replay = event?.flow_evidence?.historical_replay;
  if (!replay) return null;
  const inspectArtifact = (title: string, artifactId?: string | null) =>
    artifactId ? (
      <button
        className="text-button"
        key={`${title}-${artifactId}`}
        onClick={() => onInspect({ title, artifactId })}
      >
        {title} <code>{short(artifactId)}</code>
      </button>
    ) : null;
  const tone = (status: string) =>
    status === "preserved"
      ? "success"
      : status === "regressed"
        ? "danger"
        : "warning";
  return (
    <section aria-label="Historical replay evidence">
      <div className="inline">
        <strong>Protected historical executions</strong>
        <Badge tone={tone(replay.status)}>{label(replay.status)}</Badge>
      </div>
      <p className="small">
        {replay.case_count} protected cases.{" "}
        {replay.allowed
          ? "Recorded check: candidate replacement permitted."
          : "Recorded check: candidate replacement blocked."}
      </p>
      <p className="muted small">
        Replay compares executed computations with their original observations.
        The original task assessment remains separate.
      </p>
      {replay.model_calls != null && replay.live_mcp_calls != null && (
        <p className="muted small">
          Replay dispatches: {replay.model_calls} model calls ·{" "}
          {replay.live_mcp_calls} live MCP calls.
        </p>
      )}
      <div className="case-tags">
        {inspectArtifact(
          "Replay report",
          replay.report_id ?? event?.artifact_refs?.[0]?.id,
        )}
        {inspectArtifact("Protected case bank", replay.bank_id)}
      </div>
      <div className="case-list">
        {(replay.cases ?? []).map((item, index) => (
          <details
            className="case-card"
            key={`${item.original_case_id}-${index}`}
          >
            <summary>
              Case {short(item.original_case_id)} ·{" "}
              <Badge tone={tone(item.status)}>{label(item.status)}</Badge>
            </summary>
            <p className="small">
              {item.scope === "trajectory"
                ? "Recorded trajectory"
                : item.scope === "component"
                  ? "Component computation"
                  : "Replay scope unavailable"}
              {" · "}Original assessment: {label(item.assessment_category)}.
            </p>
            {item.scope === "component" && (
              <p className="muted small">
                This case does not establish reproduction of the full planner
                trajectory.
              </p>
            )}
            <p className="small">
              Original kernel {short(item.origin_kernel_id ?? "")} → candidate{" "}
              {short(
                item.candidate_kernel_id ?? replay.candidate_kernel_id ?? "",
              )}
              .
            </p>
            <div className="case-tags" aria-label="Recorded adapter chain">
              {(item.adapter_path ?? []).map((edge, edgeIndex) =>
                inspectArtifact(`Adapter ${edgeIndex + 1}`, edge),
              )}
              {!item.adapter_path?.length && (
                <span className="muted small">No adapter edges recorded.</span>
              )}
            </div>
            {item.reason && <p className="small">{item.reason}</p>}
            {item.first_difference && (
              <div className="error-box">
                <div>
                  <strong>First difference</strong>
                  <p className="small">
                    {String(
                      item.first_difference.reason ??
                        "Inspect the recorded divergence.",
                    )}
                  </p>
                  {!!item.first_difference.repair_target && (
                    <p className="small">
                      Repair target:{" "}
                      {label(String(item.first_difference.repair_target))}
                    </p>
                  )}
                  <button
                    className="text-button"
                    onClick={() =>
                      onInspect({
                        title: "First historical replay difference",
                        data: item.first_difference ?? {},
                      })
                    }
                  >
                    Inspect first difference
                  </button>
                </div>
              </div>
            )}
            <div className="case-tags">
              {inspectArtifact("Original case", item.original_case_id)}
              {inspectArtifact(
                "Baseline execution",
                item.baseline_execution_id,
              )}
              {inspectArtifact(
                "Candidate execution",
                item.candidate_execution_id,
              )}
              {(item.original_graph_ids ?? []).map((graph, graphIndex) =>
                inspectArtifact(`Original graph ${graphIndex + 1}`, graph),
              )}
              {(item.migrated_graph_ids ?? []).map((graph, graphIndex) =>
                inspectArtifact(`Migrated graph ${graphIndex + 1}`, graph),
              )}
            </div>
          </details>
        ))}
      </div>
      {!!replay.omitted_cases && (
        <p className="muted small">
          {replay.omitted_cases} further case reports are available in the
          replay report.
        </p>
      )}
      {!!replay.feedback?.length && (
        <details>
          <summary>Recorded repair feedback ({replay.feedback.length})</summary>
          {replay.feedback.map((feedback, index) => (
            <button
              className="text-button"
              key={index}
              onClick={() =>
                onInspect({
                  title: "Historical replay repair feedback",
                  data: feedback,
                })
              }
            >
              {String(
                feedback.reason ??
                  feedback.summary ??
                  `Inspect feedback ${index + 1}`,
              )}
            </button>
          ))}
        </details>
      )}
    </section>
  );
}

/** Keep candidate proposals and independent checks visibly separate. */
export function ConstructionFlows({ events, onInspect }: Props) {
  return (
    <section className="flow-evidence-grid" aria-label="Construction flows">
      {(["learning", "verification"] as const).map((flow) => {
        const recorded = events.filter((event) => event.flow === flow);
        const last = recorded.at(-1);
        const evaluation = recorded
          .filter((event) => event.flow_evidence?.actions?.length)
          .at(-1)?.flow_evidence;
        const checks = recorded
          .filter((event) => event.flow_evidence?.checks?.length)
          .at(-1)?.flow_evidence;
        const details = recorded
          .filter((event) => event.flow_evidence)
          .at(-1)?.flow_evidence;
        const penalties = checks?.penalties ?? details?.penalties ?? [];
        const unknowns = [
          ...new Set([
            ...(checks?.remaining_unknowns ?? []),
            ...(details?.remaining_unknowns ?? []),
          ]),
        ];
        return (
          <div className="flow-evidence" key={flow}>
            <div className="inline">
              <h3>
                {flow === "learning"
                  ? "Learning reusable capabilities"
                  : "Verification and preservation"}
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
              <>
                <p className="muted small">
                  Generated checks measure consistency. Historical replay,
                  independent task assessment, and preservation proofs remain
                  separate evidence.
                </p>
                <HistoricalReplayEvidence
                  events={recorded}
                  onInspect={onInspect}
                />
              </>
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
            {details?.metrics?.stop_reason && (
              <p className="small">{String(details.metrics.stop_reason)}</p>
            )}
            {evaluation && (
              <>
                <div className="case-tags">
                  {Object.entries(evaluation.action_counts ?? {}).map(
                    ([action, count]) => (
                      <Badge key={action}>
                        {actions[action] ?? label(action)}: {count}
                      </Badge>
                    ),
                  )}
                </div>
                <EvaluationActions
                  evidence={evaluation}
                  onInspect={onInspect}
                />
              </>
            )}
            {checks && (
              <>
                {Object.entries(checks.group_results ?? {}).map(
                  ([group, counts]) => (
                    <p className="small" key={group}>
                      {label(group)}: {counts.passed} of {counts.total}{" "}
                      generated check cases agree, {counts.failed} failed,{" "}
                      {counts.unknown} unknown.
                    </p>
                  ),
                )}
                <CallableChecks evidence={checks} onInspect={onInspect} />
              </>
            )}
            {!!penalties.length && (
              <details>
                <summary>Recorded penalties ({penalties.length})</summary>
                <ul>
                  {penalties.map((reason, index) => (
                    <li key={index}>{reason}</li>
                  ))}
                </ul>
              </details>
            )}
            {!!unknowns.length && (
              <details>
                <summary>Remaining unknowns ({unknowns.length})</summary>
                <ul>
                  {unknowns.map((reason, index) => (
                    <li key={index}>{reason}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        );
      })}
    </section>
  );
}

/** Show observed evidence scope at the playhead, independently of display limits. */
export function MaterializationEvidence({ events, onInspect }: Props) {
  const recorded = events.filter((event) => event.flow === "instantiation");
  const last = recorded.at(-1);
  const scope = recorded.filter((event) => event.flow_evidence?.scope).at(-1)
    ?.flow_evidence?.scope;
  const expansion = recorded
    .filter((event) => event.flow_evidence?.expansion_reason)
    .at(-1)?.flow_evidence;
  const detail = object(last?.payload);
  const sufficiency = object(detail.sufficiency);
  const status =
    scope?.status ??
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
      {scope && (
        <p className="small">
          Materialized: {scope.node_count} nodes · {scope.edge_count}{" "}
          relationships. Required scope: {label(scope.coverage_mode)}.
        </p>
      )}
      {expansion?.expansion_reason && (
        <p className="small">Expansion: {expansion.expansion_reason}</p>
      )}
      {!!scope?.unmet_demands?.length && (
        <details>
          <summary>Evidence still unknown</summary>
          <ul>
            {scope.unmet_demands.map((gap, index) => (
              <li key={index}>{gap}</li>
            ))}
          </ul>
        </details>
      )}
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
