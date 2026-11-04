import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight,
  LockKeyhole,
  MessageSquare,
  Radio,
  History as HistoryIcon,
} from "lucide-react";
import {
  id,
  mutate,
  useGraph,
  useHistory,
  useRun,
  useTask,
  useWorkspace,
  useSubmissionKey,
  type Event,
} from "../lib/api";
import type { components } from "../api.generated";
import { useEvents } from "../lib/events";
import { array, object, short } from "../lib/utils";
import {
  Badge,
  Empty,
  ErrorBox,
  Limitations,
  Loading,
  Status,
} from "../components/common";
import { Button } from "../components/ui/button";
import { EvidenceDrawer, type Inspection } from "../components/EvidenceDrawer";
import { GraphView } from "../components/GraphView";
import { Playback, Trajectory } from "../components/Trajectory";
import { SplitView } from "../components/SplitView";
type Accepted = components["schemas"]["AcceptedRun"];
function snapshot(events: Event[], initial: string | null | undefined) {
  let current = initial;
  let highlights: string[] = [];
  for (const event of events) {
    const payload = object(event.payload);
    if (payload.graph_id) current = String(payload.graph_id);
    else if (event.type === "graph.snapshot") {
      const ref = (event.artifact_refs ?? []).find((ref) =>
        ["graph", "graph_snapshot", "snapshot"].includes(ref.role),
      );
      if (ref) current = ref.id;
    }
    if (Array.isArray(payload.highlight_node_ids))
      highlights = payload.highlight_node_ids.map(String);
    else if (event.type === "graph.snapshot") highlights = [];
  }
  return { id: current, highlights };
}
export function Inference({ taskId }: { taskId: string }) {
  const [params, setParams] = useSearchParams();
  const task = useTask(taskId);
  const history = useHistory(taskId);
  const workspace = useWorkspace();
  const queryClient = useQueryClient();
  const runId = params.get("run") ?? "";
  const [composerOpen, setComposerOpen] = useState(!runId);
  const run = useRun(runId);
  const live = !!run.data && ["queued", "running"].includes(run.data.status);
  const stream = useEvents(runId, live);
  const [inspection, setInspection] = useState<Inspection | null>(null);
  const [selected, setSelected] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [replay, setReplay] = useState<Event[] | null>(null);
  const [following, setFollowing] = useState(true);
  const [question, setQuestion] = useState("");
  const [requirements, setRequirements] = useState("");
  const [kernelId, setKernelId] = useState("");
  const pinnedTask = useRef("");
  const submittingKey = useSubmissionKey();
  const [viewerEpoch, setViewerEpoch] = useState(0);
  const kernels = history.data?.kernels ?? [];
  const eligible = kernels.filter((k) => k.eligible_for_inference);
  useEffect(() => {
    if (pinnedTask.current !== taskId) {
      pinnedTask.current = taskId;
      setKernelId("");
    }
    if (!kernelId && eligible.length) setKernelId(eligible[0].id);
  }, [taskId, eligible, kernelId]);
  useEffect(() => {
    setPlaying(false);
    setReplay(null);
    setSelected(0);
    setFollowing(true);
    setInspection(null);
  }, [runId]);
  const events = replay ?? stream.events;
  useEffect(() => {
    if (following && !replay && events.length) setSelected(events.length - 1);
  }, [events.length, following, replay]);
  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(
      () =>
        setSelected((index) => {
          if (index >= events.length - 1) {
            setPlaying(false);
            return index;
          }
          return index + 1;
        }),
      1100,
    );
    return () => clearInterval(timer);
  }, [playing, events.length]);
  const activeSnapshot = useMemo(
    () => snapshot(events.slice(0, selected + 1), run.data?.initial_graph_id),
    [events, selected, run.data?.initial_graph_id],
  );
  const graph = useGraph(activeSnapshot.id);
  const submit = useMutation({
    mutationFn: () => {
      const body = {
        operation: "infer",
        kernel_id: kernelId,
        query: question.trim(),
        requirements: requirements
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
      };
      return mutate<Accepted>(
        `/tasks/${id(taskId)}/runs`,
        body,
        workspace.data!.session_token,
        submittingKey.forBody({ taskId, ...body }),
      );
    },
    onSuccess: (accepted) => {
      submittingKey.clear();
      setParams({ task: taskId, run: accepted.run_id });
      setQuestion("");
      setComposerOpen(false);
      void queryClient.invalidateQueries({ queryKey: ["history", taskId] });
    },
  });
  function select(index: number) {
    setFollowing(false);
    setPlaying(false);
    setSelected(index);
  }
  function reset() {
    setReplay([...events]);
    setFollowing(false);
    setPlaying(false);
    setSelected(0);
    setInspection(null);
    setViewerEpoch((value) => value + 1);
  }
  function play() {
    if (playing) {
      setPlaying(false);
      return;
    }
    if (!replay) setReplay([...stream.events]);
    setFollowing(false);
    if (selected >= events.length - 1) setSelected(0);
    setPlaying(true);
  }
  const inferRuns = (history.data?.runs ?? []).filter(
    (r) =>
      ![
        "construct",
        "construction",
        "mcp_construct",
        "corpus_construct",
        "revise",
      ].includes(r.kind) && !!r.query,
  );
  return (
    <>
      <header className="page-header">
        <div>
          <span className="eyebrow">Observe execution</span>
          <h1>Inference</h1>
          <p>
            Follow a question through its saved actions and knowledge graph.
          </p>
        </div>
        <Badge>
          <LockKeyhole size={12} />
          Frozen kernel
        </Badge>
      </header>
      {!taskId ? (
        <Empty title="Select a task">
          Choose an existing task from the workspace selector.
        </Empty>
      ) : task.isLoading ? (
        <Loading />
      ) : task.error ? (
        <ErrorBox error={task.error} />
      ) : (
        <>
          <section className="question-panel">
            <div className="section-label">
              <MessageSquare size={16} />
              <h2>Ask a new question</h2>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="composer-toggle"
                aria-expanded={composerOpen}
                onClick={() => setComposerOpen(!composerOpen)}
              >
                {composerOpen ? "Collapse" : "New question"}
              </Button>
              {task.data?.kind === "corpus" && (
                <Badge>Inspect through UI · Execute through CLI</Badge>
              )}
            </div>
            <form
              hidden={!composerOpen}
              onSubmit={(e) => {
                e.preventDefault();
                submit.mutate();
              }}
            >
              <textarea
                aria-label="New inference question"
                placeholder={
                  task.data?.kind === "corpus"
                    ? "Historical corpus runs remain available below."
                    : "What would you like the agent to solve?"
                }
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                disabled={task.data?.kind === "corpus"}
                required
                rows={2}
              />
              <div className="question-options">
                <label>
                  Kernel
                  <select
                    aria-label="Inference kernel"
                    value={kernelId}
                    onChange={(e) => setKernelId(e.target.value)}
                    disabled={!eligible.length}
                  >
                    {eligible.length ? (
                      eligible.map((k) => (
                        <option value={k.id} key={k.id}>
                          {k.name} · {short(k.id)}
                        </option>
                      ))
                    ) : (
                      <option value="">No eligible kernel yet</option>
                    )}
                  </select>
                </label>
                <Button
                  disabled={
                    !question.trim() ||
                    !kernelId ||
                    submit.isPending ||
                    task.data?.kind !== "mcp" ||
                    !workspace.data?.session_token
                  }
                  type="submit"
                >
                  <ArrowUpRight size={16} />
                  {submit.isPending ? "Submitting…" : "Run inference"}
                </Button>
              </div>
              <details className="optional">
                <summary>Public completion requirements</summary>
                <textarea
                  aria-label="Inference requirements"
                  placeholder="One requirement per line"
                  value={requirements}
                  onChange={(e) => setRequirements(e.target.value)}
                  rows={2}
                />
              </details>
              <p className="hint">
                This question stays in this run. Construction and evaluation
                pools stay fixed.
              </p>
            </form>
            {submit.error && <ErrorBox error={submit.error} />}
          </section>
          <div className="run-selector">
            <label>
              <HistoryIcon size={15} />
              Saved run
              <select
                aria-label="Saved inference run"
                value={runId}
                onChange={(e) =>
                  setParams({ task: taskId, run: e.target.value })
                }
              >
                <option value="">Select recorded execution</option>
                {inferRuns.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.query_id ? `${r.query_id} · ` : ""}
                    {r.query?.slice(0, 90)} · {r.status}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {runId ? (
            <>
              {run.isLoading ? (
                <Loading />
              ) : run.error ? (
                <ErrorBox error={run.error} />
              ) : (
                run.data && (
                  <>
                    <div className="run-summary">
                      <div>
                        <h2>{run.data.query ?? "Recorded execution"}</h2>
                        <div className="inline">
                          <span className="muted small">Execution</span>
                          <Status value={run.data.status} />
                          <span className="muted small">Agent</span>
                          <Status value={run.data.outcome} kind="outcome" />
                          {live && (
                            <Badge tone="active">
                              <Radio size={12} />
                              {stream.connected ? "Live" : "Reconnecting"}
                            </Badge>
                          )}
                        </div>
                      </div>
                      <button
                        className="text-button"
                        onClick={() =>
                          setInspection({
                            title: "Immutable run request",
                            data: {
                              run_id: run.data!.id,
                              kernel_id: run.data!.kernel_id,
                              query: run.data!.query,
                              parent_run_id: run.data!.parent_run_id,
                            },
                          })
                        }
                      >
                        Kernel {short(run.data.kernel_id)}
                      </button>
                    </div>
                    <SplitView
                      left={
                        <>
                          <div className="panel-heading">
                            <h2>Trajectory</h2>
                            <span className="muted small">Recorded order</span>
                          </div>
                          <Playback
                            count={events.length}
                            index={selected}
                            playing={playing}
                            onPlay={play}
                            onReset={reset}
                            onSelect={select}
                            mode={
                              replay
                                ? "Saved replay"
                                : live && following
                                  ? "Live"
                                  : "Inspecting"
                            }
                            live={live}
                            onLive={() => {
                              setReplay(null);
                              setFollowing(true);
                              setPlaying(false);
                            }}
                          />
                          {stream.loading ? (
                            <Loading />
                          ) : stream.error ? (
                            <ErrorBox error={stream.error} />
                          ) : (
                            <Trajectory
                              autoScroll
                              events={events}
                              index={selected}
                              onSelect={select}
                              onInspect={setInspection}
                            />
                          )}
                        </>
                      }
                      right={
                        <>
                          <div className="panel-heading">
                            <h2>
                              Knowledge graph <span className="symbol">G</span>
                            </h2>
                            <Badge>
                              {activeSnapshot.id
                                ? "Recorded snapshot"
                                : "No snapshot"}
                            </Badge>
                          </div>
                          {graph.isFetching ? (
                            <Loading text="Loading graph snapshot" />
                          ) : graph.error ? (
                            <ErrorBox error={graph.error} />
                          ) : (
                            <GraphView
                              key={`${runId}:${viewerEpoch}`}
                              graph={graph.data}
                              highlightIds={activeSnapshot.highlights}
                              onInspect={setInspection}
                            />
                          )}
                        </>
                      }
                    />
                    {run.data.answer !== null &&
                      run.data.answer !== undefined && (
                        <section className="answer-panel">
                          <div>
                            <span className="eyebrow">Agent answer</span>
                            <p className="answer" data-testid="agent-answer">
                              {run.data.answer}
                            </p>
                          </div>
                          <div className="assessment">
                            <span className="eyebrow">
                              Independent assessment
                            </span>
                            <Status
                              kind="assessment"
                              value={String(
                                run.data.assessment?.status ?? "not_checked",
                              )}
                            />
                            {array(run.data.assessment?.evidence_refs).length >
                              0 && <span>Supporting evidence recorded</span>}
                            <button
                              className="text-button"
                              onClick={() =>
                                setInspection({
                                  title: "Task assessment",
                                  data: object(run.data!.assessment),
                                })
                              }
                            >
                              View assessment
                            </button>
                          </div>
                        </section>
                      )}
                    {run.data.error && <ErrorBox error={run.data.error} />}
                    <Limitations items={run.data.limitations} />
                  </>
                )
              )}
            </>
          ) : (
            <Empty title="Choose a run or ask a question">
              Saved trajectories and graphs will appear side by side.
            </Empty>
          )}
        </>
      )}
      <EvidenceDrawer
        selection={inspection}
        onClose={() => setInspection(null)}
      />
    </>
  );
}
