import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Cable,
  Check,
  ChevronDown,
  Cpu,
  FileUp,
  Globe,
  Plus,
  Terminal,
  Trash2,
} from "lucide-react";
import type { components } from "../api.generated";
import {
  id,
  mutate,
  request,
  useWorkspace,
  useSubmissionKey,
} from "../lib/api";
import { array, money, object } from "../lib/utils";
import {
  Badge,
  Empty,
  ErrorBox,
  Json,
  Loading,
  Status,
} from "../components/common";
import { Button } from "../components/ui/button";
type Models = components["schemas"];
type Query = Models["QuerySpec"];
const newCase = (): Query => ({
  id: `case-${crypto.randomUUID().slice(0, 8)}`,
  query: "",
  split: "construction",
  requirements: [],
  supplied_documents: [],
});
export function Setup() {
  const workspace = useWorkspace();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [prompt, setPrompt] = useState("");
  const [cases, setCases] = useState<Query[]>([newCase()]);
  const [connectorIds, setConnectorIds] = useState<string[]>([]);
  const [steps, setSteps] = useState(8);
  const [discoverySteps, setDiscoverySteps] = useState(12);
  const [calls, setCalls] = useState(6);
  const [spend, setSpend] = useState(1);
  const [fraction, setFraction] = useState(0.2);
  const [seed, setSeed] = useState(42);
  const [importError, setImportError] = useState<Error | null>(null);
  const [createdTask, setCreatedTask] = useState<string | null>(null);
  const submitKey = useSubmissionKey();
  const constructionKey = useSubmissionKey();
  const inputRef = useRef<HTMLInputElement>(null);
  const connectors = useQuery({
    queryKey: ["connectors"],
    queryFn: () => request<Models["ConnectorListResponse"]>("/connectors"),
  });
  const session = workspace.data?.session_token ?? "";
  const submission = useMutation({
    mutationFn: async () => {
      const taskBody = {
        name,
        description,
        base_prompt: prompt,
        queries: cases.map((entry) => ({
          ...entry,
          requirements: (entry.requirements ?? [])
            .map((value) => value.trim())
            .filter(Boolean),
        })),
        connector_ids: connectorIds,
        limits: {
          max_steps: steps,
          max_discovery_steps: discoverySteps,
          max_tool_calls: calls,
          max_new_spend_usd: spend,
        },
        seed,
        sampling_fraction: fraction,
      } satisfies Models["TaskCreateRequest"];
      const taskId =
        createdTask ??
        (
          await mutate<Models["TaskCreatedResponse"]>(
            "/tasks",
            taskBody,
            session,
            submitKey.forBody(taskBody),
          )
        ).task_id;
      setCreatedTask(taskId);
      return mutate<Models["AcceptedRun"]>(
        `/tasks/${id(taskId)}/runs`,
        { operation: "construct" },
        session,
        constructionKey.forBody({ taskId, operation: "construct" }),
      );
    },
    onSuccess: (accepted) => {
      void client.invalidateQueries({ queryKey: ["tasks"] });
      navigate(
        `/construction?task=${id(accepted.task_id ?? createdTask ?? "")}&attempt=${id(accepted.run_id)}`,
      );
    },
  });
  function patchCase(index: number, patch: Partial<Query>) {
    setCases((current) =>
      current.map((entry, i) => (i === index ? { ...entry, ...patch } : entry)),
    );
  }
  async function importFile(file: File | undefined) {
    if (!file) return;
    try {
      const input = JSON.parse(await file.text());
      if (!Array.isArray(input.queries) || !input.queries.length)
        throw new Error(
          "Import requires a queries array with declared split assignments.",
        );
      for (const query of input.queries)
        if (
          !query.id ||
          !query.query ||
          !["construction", "development", "heldout"].includes(query.split)
        )
          throw new Error(
            "Every case needs an id, query, and construction, development, or heldout split.",
          );
      setName(String(input.name ?? ""));
      setDescription(String(input.description ?? ""));
      setPrompt(String(input.base_prompt ?? ""));
      setCases(
        input.queries.map((query: Query) => ({
          ...query,
          requirements: query.requirements ?? [],
          supplied_documents: query.supplied_documents ?? [],
        })),
      );
      if (input.limits) {
        setSteps(input.limits.max_steps ?? 8);
        setDiscoverySteps(input.limits.max_discovery_steps ?? 12);
        setCalls(input.limits.max_tool_calls ?? 6);
        setSpend(input.limits.max_new_spend_usd ?? 1);
      }
      setSeed(input.seed ?? 42);
      setFraction(input.sampling_fraction ?? 0.2);
      setImportError(null);
    } catch (error) {
      setImportError(error as Error);
    }
  }
  const settings = workspace.data?.settings ?? {};
  const bound = (key: string, edge: "min" | "max", fallback: number) =>
    Number(object(settings[key])[edge] ?? fallback);
  return (
    <>
      <header className="page-header">
        <div>
          <span className="eyebrow">Create a task surface</span>
          <h1>Start with a clear task</h1>
          <p>
            Define what the agent should do and the tools it is allowed to use.
          </p>
        </div>
        <Button variant="outline" onClick={() => inputRef.current?.click()}>
          <FileUp size={16} />
          Import setup
        </Button>
        <input
          hidden
          ref={inputRef}
          type="file"
          accept="application/json,.json"
          aria-label="Import existing task configuration"
          onChange={(e) => void importFile(e.target.files?.[0])}
        />
      </header>
      {workspace.error && <ErrorBox error={workspace.error} />}{" "}
      {importError && <ErrorBox error={importError} />}
      <div className="setup-grid">
        <form
          className="setup-form"
          onSubmit={(e) => {
            e.preventDefault();
            submission.mutate();
          }}
        >
          <fieldset disabled={submission.isPending || !!createdTask}>
            <section className="setup-section">
              <div className="section-title">
                <span>01</span>
                <div>
                  <h2>Task and starting instructions</h2>
                  <p>
                    Your declared scope becomes the immutable setup for this
                    task.
                  </p>
                </div>
              </div>
              <label>
                Task name
                <input
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="A short, recognizable name"
                />
              </label>
              <label>
                What should the agent solve?
                <textarea
                  required
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Describe the task family and its boundaries."
                />
              </label>
              <label>
                Starting ReAct instructions
                <textarea
                  required
                  rows={4}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Describe how to approach the task, use observations, and decide when to finish."
                />
              </label>
              <div className="section-subtitle">
                <div>
                  <h3>Representative cases</h3>
                  <p>
                    Include at least one construction case. Requirements are
                    visible to the agent.
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setCases((current) => [...current, newCase()])}
                >
                  <Plus size={14} />
                  Add case
                </Button>
              </div>
              <div className="setup-cases">
                {cases.map((entry, index) => (
                  <article className="setup-case" key={index}>
                    <div className="case-topline">
                      <label>
                        Case ID
                        <input
                          required
                          value={entry.id}
                          onChange={(e) =>
                            patchCase(index, { id: e.target.value })
                          }
                        />
                      </label>
                      <label>
                        Assignment
                        <select
                          value={entry.split}
                          onChange={(e) =>
                            patchCase(index, {
                              split: e.target.value as Query["split"],
                            })
                          }
                        >
                          <option value="construction">Construction</option>
                          <option value="development">Development</option>
                          <option value="heldout">Held-out</option>
                        </select>
                      </label>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label={`Remove case ${index + 1}`}
                        disabled={cases.length === 1}
                        onClick={() =>
                          setCases((current) =>
                            current.filter((_, i) => i !== index),
                          )
                        }
                      >
                        <Trash2 size={15} />
                      </Button>
                    </div>
                    <label>
                      Case request
                      <textarea
                        required
                        rows={2}
                        value={entry.query}
                        onChange={(e) =>
                          patchCase(index, { query: e.target.value })
                        }
                        placeholder="A real request from this task family"
                      />
                    </label>
                    <label>
                      Public completion requirements
                      <textarea
                        rows={2}
                        value={entry.requirements?.join("\n") ?? ""}
                        onChange={(e) =>
                          patchCase(index, {
                            requirements: e.target.value.split("\n"),
                          })
                        }
                        placeholder="One requirement per line. Keep reference answers separate."
                      />
                    </label>
                    {!!entry.supplied_documents?.length && (
                      <Badge>
                        {entry.supplied_documents.length} imported documents
                        preserved
                      </Badge>
                    )}
                  </article>
                ))}
              </div>
            </section>
            <section className="setup-section">
              <div className="section-title">
                <span>02</span>
                <div>
                  <h2>Connections and capabilities</h2>
                  <p>
                    Select saved MCP connections or discover a custom server.
                  </p>
                </div>
              </div>
              {connectors.error ? (
                <ErrorBox error={connectors.error} />
              ) : connectors.isLoading ? (
                <Loading text="Loading connections" />
              ) : (
                <div className="saved-connectors">
                  {connectors.data?.items.map((connector) => (
                    <label
                      className="connector-choice"
                      key={connector.connector_id}
                    >
                      <input
                        type="checkbox"
                        checked={connectorIds.includes(connector.connector_id)}
                        onChange={(e) =>
                          setConnectorIds((current) =>
                            e.target.checked
                              ? [...current, connector.connector_id]
                              : current.filter(
                                  (value) => value !== connector.connector_id,
                                ),
                          )
                        }
                      />
                      <Cable size={19} />
                      <span>
                        <strong>{String(connector.configuration.name)}</strong>
                        <small>
                          {array(connector.catalog.tools).filter((tool) =>
                            (
                              (connector.configuration
                                .allowed_tools as string[]) ?? []
                            ).includes(String(tool.name)),
                          ).length ||
                            (
                              (connector.configuration
                                .allowed_tools as string[]) ?? []
                            ).length}{" "}
                          selected tools ·{" "}
                          {String(connector.configuration.transport)}
                        </small>
                      </span>
                      <Badge>Saved</Badge>
                    </label>
                  ))}
                </div>
              )}
              <ConnectorSetup
                session={session}
                onSaved={(connector) => {
                  void client.invalidateQueries({ queryKey: ["connectors"] });
                  setConnectorIds((current) => [
                    ...current,
                    connector.connector_id,
                  ]);
                }}
              />
            </section>
            <section className="setup-section">
              <div className="section-title">
                <span>03</span>
                <div>
                  <h2>Execution settings</h2>
                  <p>
                    Bounded construction rounds with generated checks and
                    independent verification.
                  </p>
                </div>
              </div>
              <div className="model-display">
                <Cpu size={19} />
                <div>
                  <span>Configured model</span>
                  <strong>
                    {workspace.data?.model || "Loading model configuration"}
                  </strong>
                </div>
              </div>
              <div className="settings-grid">
                <label>
                  Maximum steps
                  <input
                    type="number"
                    min={bound("max_steps", "min", 1)}
                    max={bound("max_steps", "max", 100)}
                    value={steps}
                    onChange={(e) => setSteps(Number(e.target.value))}
                  />
                </label>
                <label>
                  Maximum tool calls
                  <input
                    type="number"
                    min={bound("max_tool_calls", "min", 1)}
                    max={bound("max_tool_calls", "max", 100)}
                    value={calls}
                    onChange={(e) => setCalls(Number(e.target.value))}
                  />
                </label>
                <label>
                  New spending ceiling ($)
                  <input
                    type="number"
                    step="0.01"
                    min={bound("max_new_spend_usd", "min", 0.01)}
                    max={bound("max_new_spend_usd", "max", 40)}
                    value={spend}
                    onChange={(e) => setSpend(Number(e.target.value))}
                  />
                </label>
                <label>
                  Construction sample fraction
                  <input
                    type="number"
                    min={bound("sampling_fraction", "min", 0.01)}
                    max={bound("sampling_fraction", "max", 1)}
                    step="0.01"
                    value={fraction}
                    onChange={(e) => setFraction(Number(e.target.value))}
                  />
                </label>
                <label>
                  Sampling seed
                  <input
                    type="number"
                    min={0}
                    value={seed}
                    onChange={(e) => setSeed(Number(e.target.value))}
                  />
                </label>
              </div>
            </section>
          </fieldset>
          <div className="setup-submit">
            {submission.error && <ErrorBox error={submission.error} />}{" "}
            {!!createdTask && submission.isError && (
              <p className="hint">
                The setup was saved. Retrying submits construction for that same
                immutable task.
              </p>
            )}
            <Button
              type="submit"
              disabled={
                submission.isPending ||
                !session ||
                !connectorIds.length ||
                !cases.some((entry) => entry.split === "construction")
              }
            >
              {submission.isPending
                ? "Submitting construction…"
                : createdTask
                  ? "Retry construction submission"
                  : "Start construction"}
              <ArrowRight size={16} />
            </Button>
            <p>
              Submits one job. Real evidence will appear as the worker
              progresses.
            </p>
          </div>
        </form>
        <aside className="setup-aside">
          <div className="aside-note">
            <div className="brand-mark small-brand">
              <ShapesMark />
            </div>
            <h3>Build, then observe.</h3>
            <p>
              Construction turns real cases and observations into a reusable
              schema and function catalog.
            </p>
            <div className="aside-flow">
              <span>Task + MCP tools</span>
              <ChevronDown size={14} />
              <span>Construction cases</span>
              <ChevronDown size={14} />
              <span>Frozen schema + functions</span>
              <ChevronDown size={14} />
              <span>New questions</span>
            </div>
          </div>
          {workspace.data && (
            <div className="budget-card">
              <h3>Workspace budget</h3>
              <div>
                <strong>{money(workspace.data.budget.remaining_usd)}</strong>
                <span>remaining</span>
              </div>
              <dl>
                <dt>Estimated spend</dt>
                <dd>{money(workspace.data.budget.estimated_usd)}</dd>
                <dt>Reserved</dt>
                <dd>{money(workspace.data.budget.reserved_usd)}</dd>
                <dt>Total limit</dt>
                <dd>{money(workspace.data.budget.limit_usd)}</dd>
              </dl>
            </div>
          )}
        </aside>
      </div>
    </>
  );
}
function ShapesMark() {
  return <span>O</span>;
}
function ConnectorSetup({
  session,
  onSaved,
}: {
  session: string;
  onSaved: (connector: Models["ConnectorResponse"]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [transport, setTransport] = useState<"stdio" | "streamable_http">(
    "streamable_http",
  );
  const [url, setUrl] = useState("");
  const [command, setCommand] = useState("");
  const [args, setArgs] = useState("");
  const [env, setEnv] = useState("");
  const [discoveryId, setDiscoveryId] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [confirmed, setConfirmed] = useState(false);
  const [saved, setSaved] = useState(false);
  const key = useSubmissionKey();
  const saveKey = useSubmissionKey();
  const discover = useMutation({
    mutationFn: () => {
      const body = {
        connection: {
          name,
          transport,
          ...(transport === "stdio"
            ? {
                command,
                args: args.split("\n").filter(Boolean),
                env_refs: Object.fromEntries(
                  env
                    .split("\n")
                    .filter(Boolean)
                    .map((line) =>
                      line.split("=").map((value) => value.trim()),
                    ),
                ),
              }
            : { url }),
        },
      };
      return mutate<Models["AcceptedRun"]>(
        "/connector-discoveries",
        body,
        session,
        key.forBody(body),
      );
    },
    onSuccess: (run) => {
      setDiscoveryId(run.run_id);
      setSelected([]);
      setSaved(false);
    },
  });
  const discovery = useQuery({
    queryKey: ["discovery", discoveryId],
    queryFn: () =>
      request<Models["DiscoveryResponse"]>(
        `/connector-discoveries/${id(discoveryId)}`,
      ),
    enabled: !!discoveryId,
    refetchInterval: (query) =>
      ["queued", "running"].includes(query.state.data?.status ?? "queued")
        ? 1000
        : false,
  });
  const save = useMutation({
    mutationFn: () =>
      mutate<Models["ConnectorResponse"]>(
        "/connectors",
        { discovery_id: discoveryId, allowed_tools: selected },
        session,
        saveKey.forBody({ discovery_id: discoveryId, allowed_tools: selected }),
      ),
    onSuccess: (connector) => {
      setSaved(true);
      onSaved(connector);
    },
  });
  const tools = array(discovery.data?.catalog?.tools);
  return (
    <div className="connector-builder">
      <button
        className="connector-toggle"
        type="button"
        onClick={() => setOpen(!open)}
      >
        <Plus size={16} />
        <strong>Add custom MCP server</strong>
        <ChevronDown size={15} />
      </button>
      {open && (
        <div className="connector-form">
          <div className="inline">
            <Badge>
              <Globe size={12} />
              Public Streamable HTTP
            </Badge>
            <span className="muted small">
              OAuth and authenticated HTTP are not supported yet.
            </span>
          </div>
          <label>
            Connection name
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              pattern="[A-Za-z][A-Za-z0-9_-]{0,63}"
              placeholder="my-connector"
            />
          </label>
          {transport === "streamable_http" ? (
            <label>
              Server endpoint
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/mcp"
              />
            </label>
          ) : (
            <div className="advanced-fields">
              <label>
                Command
                <input
                  value={command}
                  onChange={(e) => setCommand(e.target.value)}
                  placeholder="python"
                />
              </label>
              <label>
                Arguments, one per line
                <textarea
                  value={args}
                  onChange={(e) => setArgs(e.target.value)}
                  rows={3}
                />
              </label>
              <label>
                Environment references, NAME=EXISTING_VARIABLE
                <textarea
                  value={env}
                  onChange={(e) => setEnv(e.target.value)}
                  rows={2}
                  placeholder="SERVICE_KEY=MY_EXISTING_SERVICE_KEY"
                />
              </label>
              <p className="hint">
                Enter environment variable names only. Values stay on the
                backend.
              </p>
            </div>
          )}
          <button
            className="text-button"
            type="button"
            onClick={() =>
              setTransport(transport === "stdio" ? "streamable_http" : "stdio")
            }
          >
            <Terminal size={13} />
            {transport === "stdio"
              ? "Use remote HTTP instead"
              : "Advanced: local process (stdio)"}
          </button>
          <Button
            type="button"
            variant="outline"
            disabled={
              !session ||
              !name ||
              !(transport === "stdio" ? command : url) ||
              discover.isPending ||
              ["queued", "running"].includes(discovery.data?.status ?? "")
            }
            onClick={() => {
              discover.mutate();
            }}
          >
            <Cable size={15} />
            {discover.isPending ? "Submitting…" : "Discover tools"}
          </Button>
          <p className="hint">
            Discovery initializes the connection and lists tools. No tool is
            called.
          </p>
          {discover.error && <ErrorBox error={discover.error} />}{" "}
          {discovery.error && <ErrorBox error={discovery.error} />}{" "}
          {discoveryId && (
            <div className="discovery-result">
              <div className="inline">
                <h3>Discovery</h3>
                <Status value={discovery.data?.status ?? "queued"} />
              </div>
              {discovery.data?.error && (
                <ErrorBox error={discovery.data.error} />
              )}{" "}
              {tools.length > 0 ? (
                <>
                  <p className="small muted">
                    Review contracts and select capabilities you authorize as
                    read-only.
                  </p>
                  <div className="tool-list">
                    {tools.map((tool, index) => {
                      const toolName = String(
                        tool.name ?? object(tool.contract).name ?? index,
                      );
                      return (
                        <div className="tool-choice" key={toolName}>
                          <label>
                            <input
                              type="checkbox"
                              checked={selected.includes(toolName)}
                              onChange={(e) => {
                                setSaved(false);
                                setSelected((current) =>
                                  e.target.checked
                                    ? [...current, toolName]
                                    : current.filter(
                                        (value) => value !== toolName,
                                      ),
                                );
                              }}
                              disabled={saved}
                            />
                            <strong>{toolName}</strong>
                          </label>
                          <p>
                            {String(
                              tool.description ??
                                object(tool.contract).description ??
                                "No description supplied by server.",
                            )}
                          </p>
                          <details>
                            <summary>Inspect tool contract</summary>
                            <Json value={tool} />
                          </details>
                        </div>
                      );
                    })}
                  </div>
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={confirmed}
                      onChange={(e) => setConfirmed(e.target.checked)}
                    />
                    I authorize these selected tools for read-only use.
                  </label>
                  <Button
                    type="button"
                    disabled={
                      !selected.length || !confirmed || save.isPending || saved
                    }
                    onClick={() => save.mutate()}
                  >
                    {saved ? (
                      <>
                        <Check size={15} />
                        Connection saved
                      </>
                    ) : save.isPending ? (
                      "Saving…"
                    ) : (
                      "Save selected capabilities"
                    )}
                  </Button>
                  {save.error && <ErrorBox error={save.error} />}
                </>
              ) : discovery.data?.status === "completed" ? (
                <Empty title="No tools discovered">
                  This server returned an empty catalog.
                </Empty>
              ) : null}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
