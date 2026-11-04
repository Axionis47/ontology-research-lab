import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  FileText,
  GitBranch,
  Layers,
  Shapes,
  ArrowUpRight,
  CheckCheck,
} from "lucide-react";
import { id, request, useHistory, useKernel } from "../lib/api";
import type { components } from "../api.generated";
import { useEvents } from "../lib/events";
import { array, label, object, short } from "../lib/utils";
import {
  Badge,
  Empty,
  ErrorBox,
  Json,
  Limitations,
  Loading,
  Status,
} from "../components/common";
import { EvidenceDrawer, type Inspection } from "../components/EvidenceDrawer";
import { GraphView } from "../components/GraphView";
import { SplitView } from "../components/SplitView";
import { Trajectory } from "../components/Trajectory";
export function Construction({ taskId }: { taskId: string }) {
  const history = useHistory(taskId);
  const [params, setParams] = useSearchParams();
  const attempts = history.data?.attempts ?? [];
  const requested = params.get("attempt");
  const attempt =
    attempts.find((a) => a.run_id === requested) ??
    attempts[0];
  const kernel = useKernel(attempt?.kernel_id);
  const stream = useEvents(
    attempt?.run_id ?? "",
    ["queued", "running"].includes(attempt?.status ?? ""),
  );
  const [tab, setTab] = useState("schema");
  const [inspection, setInspection] = useState<Inspection | null>(null);
  const [eventIndex, setEventIndex] = useState(0);
  useEffect(
    () => setEventIndex(Math.max(0, stream.events.length - 1)),
    [stream.events.length],
  );
  const parent = kernel.data?.parent_id ?? attempt?.parent_kernel_id;
  const diff = useQuery({
    queryKey: ["diff", attempt?.kernel_id, parent],
    queryFn: () =>
      request<components["schemas"]["KernelDiffResponse"]>(
        `/kernels/${id(attempt!.kernel_id!)}/diff?against=${id(parent!)}`,
      ),
    enabled: !!attempt?.kernel_id && !!parent,
    staleTime: Infinity,
  });
  const schema = kernel.data?.schema_view ?? attempt?.schema_view;
  const changes = diff.data?.changes ?? [];
  const changedIds = changes.flatMap((c) => {
    const change = object(c);
    const path = String(change.path ?? change.declaration ?? "");
    return array(schema?.nodes)
      .filter((node) => path.includes(String(node.id)))
      .map((node) => String(node.id));
  });
  const caseLinks = attempt?.case_links ?? [];
  return (
    <>
      <header className="page-header">
        <div>
          <span className="eyebrow">Understand construction</span>
          <h1>Schema, shaped by experience</h1>
          <p>
            Inspect the cases, checks, and declarations recorded by each
            attempt.
          </p>
        </div>
        <Badge>
          <Layers size={12} />
          {attempts.length} {attempts.length === 1 ? "attempt" : "attempts"}
        </Badge>
      </header>
      {!taskId ? (
        <Empty title="Select a task">
          Choose a configured task to inspect construction.
        </Empty>
      ) : history.isLoading ? (
        <Loading />
      ) : history.error ? (
        <ErrorBox error={history.error} />
      ) : !attempt ? (
        <Empty title="No construction attempts yet">
          Create a task in Setup and start its first construction.
        </Empty>
      ) : (
        <>
          <div className="construction-context">
            <div className="inline">
              <span className="symbol">S</span>
              <span>Schema</span>
              <span className="dot" />
              <span className="symbol">F</span>
              <span>Functions</span>
              <span className="muted small">
                Immutable candidate definitions
              </span>
            </div>
            <span className="muted small">
              One construction round per submitted job
            </span>
          </div>
          <SplitView
            left={
              <>
                <div className="panel-heading">
                  <h2>Construction history</h2>
                  <span className="muted small">Actual attempts</span>
                </div>
                <div className="attempt-list">
                  {attempts.map((item, i) => (
                    <button
                      key={item.run_id}
                      className={`attempt ${item.run_id === attempt.run_id ? "attempt-active" : ""}`}
                      onClick={() => {
                        setParams({ task: taskId, attempt: item.run_id });
                        setInspection(null);
                      }}
                    >
                      <span className="attempt-number">
                        {String(item.round_index ?? i).padStart(2, "0")}
                      </span>
                      <span>
                        <strong>
                          {item.round_index !== null
                            ? `Round ${item.round_index}`
                            : `Attempt ${i + 1}`}
                        </strong>
                        <span className="attempt-meta">
                          {item.kernel_id
                            ? `Kernel ${short(item.kernel_id)}`
                            : "No kernel produced"}
                        </span>
                        <span className="case-tags">
                          {(item.case_links ?? []).map((link, j) => (
                            <span key={j}>
                              {String(
                                link.query_id ?? link.id ?? "Recorded case",
                              )}
                            </span>
                          ))}
                        </span>
                      </span>
                      <Status value={item.status} />
                    </button>
                  ))}
                </div>
                <div className="panel-subheading">
                  <h3>Sampled cases</h3>
                  <span>{caseLinks.length} recorded</span>
                </div>
                <div className="case-list">
                  {caseLinks.length ? (
                    caseLinks.map((link, i) => {
                      const runId = link.run_id ?? link.episode_run_id;
                      return (
                        <div className="case-card" key={i}>
                          <div className="inline">
                            <Badge>
                              {String(link.query_id ?? link.id ?? "Case")}
                            </Badge>
                            <Badge>
                              {String(link.split ?? "construction")}
                            </Badge>
                          </div>
                          {!!link.query && <p>{String(link.query)}</p>}
                          {runId ? (
                            <Link
                              className="text-button"
                              to={`/inference?task=${id(taskId)}&run=${id(String(runId))}`}
                            >
                              Open trajectory <ArrowUpRight size={13} />
                            </Link>
                          ) : (
                            <span className="muted small">
                              No linked trajectory recorded
                            </span>
                          )}
                        </div>
                      );
                    })
                  ) : (
                    <p className="muted small">
                      Sample assignment was not recorded.
                    </p>
                  )}
                </div>
                <div className="panel-subheading">
                  <h3>Recorded stages</h3>
                  <span>{stream.events.length}</span>
                </div>
                {stream.loading ? (
                  <Loading />
                ) : stream.error ? (
                  <ErrorBox error={stream.error} />
                ) : (
                  <Trajectory
                    events={stream.events}
                    index={eventIndex}
                    onSelect={setEventIndex}
                    onInspect={setInspection}
                  />
                )}
              </>
            }
            right={
              <>
                <div className="panel-heading">
                  <h2>
                    {schema
                      ? String(schema.name ?? "Candidate schema")
                      : "Starter observations"}
                  </h2>
                  <div
                    className="tabs"
                    role="tablist"
                    aria-label="Candidate view"
                  >
                    {["schema", "functions", "checks"].map((name) => (
                      <button
                        key={name}
                        role="tab"
                        aria-selected={tab === name}
                        onClick={() => setTab(name)}
                      >
                        {label(name)}
                      </button>
                    ))}
                  </div>
                </div>
                {attempt.kernel_id && (
                  <div className="kernel-strip">
                    <LockLabel value={attempt.kernel_id} />
                    {parent ? (
                      <button
                        className="text-button"
                        onClick={() =>
                          setInspection({
                            title: "Recorded parent revision",
                            data: {
                              kernel_id: attempt.kernel_id,
                              parent_kernel_id: parent,
                            },
                          })
                        }
                      >
                        <GitBranch size={13} />
                        Parent {short(parent)}
                      </button>
                    ) : (
                      <span className="muted small">
                        No parent revision recorded
                      </span>
                    )}
                  </div>
                )}
                {kernel.isLoading && attempt.kernel_id ? (
                  <Loading />
                ) : kernel.error ? (
                  <ErrorBox error={kernel.error} />
                ) : tab === "schema" ? (
                  <>
                    {schema ? (
                      <GraphView
                        schema={schema}
                        changedIds={changedIds}
                        onInspect={setInspection}
                      />
                    ) : (
                      <Empty title="Schema not yet recorded">
                        Starter observations and execution evidence are shown in
                        the trajectory.
                      </Empty>
                    )}
                    {diff.data && (
                      <div className="diff-panel">
                        <div className="inline">
                          <GitBranch size={15} />
                          <h3>Changes from recorded parent</h3>
                          {!diff.data.schema_changed &&
                            !diff.data.functions_changed && (
                              <Badge>Schema and functions unchanged</Badge>
                            )}
                        </div>
                        {changes.length ? (
                          <div className="change-list">
                            {changes.map((change, i) => (
                              <button
                                key={i}
                                onClick={() =>
                                  setInspection({
                                    title: "Declaration difference",
                                    data: change,
                                  })
                                }
                              >
                                <Badge>
                                  {String(
                                    change.kind ??
                                      change.change ??
                                      change.operation ??
                                      "Changed",
                                  )}
                                </Badge>
                                <span>
                                  {String(
                                    change.path ??
                                      change.name ??
                                      change.summary ??
                                      "Recorded declaration",
                                  )}
                                </span>
                              </button>
                            ))}
                          </div>
                        ) : (
                          <p className="muted small">
                            No declaration differences.
                          </p>
                        )}
                      </div>
                    )}
                  </>
                ) : tab === "functions" ? (
                  <div className="function-list">
                    {kernel.data?.functions.length ? (
                      kernel.data.functions.map((fn, i) => (
                        <details
                          className="function-card"
                          key={String(fn.name ?? i)}
                        >
                          <summary>
                            <Shapes size={16} />
                            <span>
                              <strong>
                                {String(fn.name ?? `Function ${i + 1}`)}
                              </strong>
                              <small>
                                {String(
                                  fn.description ??
                                    "Saved function declaration",
                                )}
                              </small>
                            </span>
                          </summary>
                          <Json value={fn} />
                        </details>
                      ))
                    ) : (
                      <Empty title="No function catalog recorded">
                        A failed attempt can retain schema evidence without
                        producing an executable kernel.
                      </Empty>
                    )}
                  </div>
                ) : (
                  <div className="checks-panel">
                    <CheckCheck size={24} />
                    <h3>Separate checks, separate evidence</h3>
                    <div className="check-grid">
                      {["ontology", "functions", "task", "regression"].map(
                        (key) => {
                          const check = object(
                            attempt.validation?.[key] ??
                              attempt.validation?.[`${key}_validation`] ??
                              object(kernel.data?.assessment)[key],
                          );
                          return (
                            <button
                              key={key}
                              onClick={() =>
                                setInspection({
                                  title: `${label(key)} evidence`,
                                  data: Object.keys(check).length
                                    ? check
                                    : {
                                        status:
                                          key === "task"
                                            ? "Not checked"
                                            : "Not run",
                                      },
                                })
                              }
                            >
                              <span>
                                {key === "ontology"
                                  ? "Ontology / HermiT"
                                  : key === "functions"
                                    ? "Function probes"
                                    : key === "task"
                                      ? "Task evaluation"
                                      : "Regression evidence"}
                              </span>
                              <Status
                                kind="assessment"
                                value={String(
                                  check.status ??
                                    (Object.keys(check).length
                                      ? "recorded"
                                      : key === "task"
                                        ? "not_checked"
                                        : "not_run"),
                                )}
                              />
                            </button>
                          );
                        },
                      )}
                    </div>
                    <p className="muted small">
                      Passing ontology and function checks makes a candidate
                      eligible to execute. Task correctness requires independent
                      assessment.
                    </p>
                    <details>
                      <summary>All recorded validation details</summary>
                      <Json value={attempt.validation} />
                    </details>
                  </div>
                )}
                <div className="artifact-bar">
                  {(attempt.artifact_refs ?? []).map((ref) => (
                    <button
                      key={ref}
                      onClick={() =>
                        setInspection({
                          title: "Construction evidence",
                          artifactId: ref,
                        })
                      }
                    >
                      <FileText size={13} />
                      {short(ref)}
                    </button>
                  ))}
                </div>
              </>
            }
          />
          <Limitations
            items={[
              ...(attempt.limitations ?? []),
              ...(kernel.data?.limitations ?? []),
            ]}
          />
        </>
      )}
      <EvidenceDrawer
        selection={inspection}
        onClose={() => setInspection(null)}
      />
    </>
  );
}
function LockLabel({ value }: { value: string }) {
  return (
    <span className="muted small">
      Kernel <code>{short(value)}</code>
    </span>
  );
}
