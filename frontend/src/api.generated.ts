export interface paths {
  "/api/v1/workspace": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Workspace */
    get: operations["workspace_api_v1_workspace_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/connector-discoveries": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Discover */
    post: operations["discover_api_v1_connector_discoveries_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/connector-discoveries/{identity}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Discovery */
    get: operations["discovery_api_v1_connector_discoveries__identity__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/connectors": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Connectors */
    get: operations["connectors_api_v1_connectors_get"];
    put?: never;
    /** Save Connector */
    post: operations["save_connector_api_v1_connectors_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/tasks": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Tasks */
    get: operations["tasks_api_v1_tasks_get"];
    put?: never;
    /** Create Task */
    post: operations["create_task_api_v1_tasks_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/tasks/{identity}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Task */
    get: operations["task_api_v1_tasks__identity__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/tasks/{identity}/history": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** History */
    get: operations["history_api_v1_tasks__identity__history_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/tasks/{identity}/runs": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Submit */
    post: operations["submit_api_v1_tasks__identity__runs_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/runs/{identity}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Run */
    get: operations["run_api_v1_runs__identity__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/runs/{identity}/events": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Events */
    get: operations["events_api_v1_runs__identity__events_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/runs/{identity}/stream": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Stream */
    get: operations["stream_api_v1_runs__identity__stream_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/kernels/{identity}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Kernel */
    get: operations["kernel_api_v1_kernels__identity__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/kernels/{identity}/diff": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Diff */
    get: operations["diff_api_v1_kernels__identity__diff_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/graphs/{identity}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Graph */
    get: operations["graph_api_v1_graphs__identity__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/artifacts/{identity}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Artifact */
    get: operations["artifact_api_v1_artifacts__identity__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
}
export type webhooks = Record<string, never>;
export interface components {
  schemas: {
    /**
     * AcceptedRun
     * @description An admitted background job, distinct from its eventual result.
     */
    AcceptedRun: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Run Id */
      run_id: string;
      /** Status */
      status: string;
      /** Operation */
      operation: string;
      /** Task Id */
      task_id?: string | null;
      /**
       * Reused
       * @default false
       */
      reused: boolean;
    };
    /**
     * ArtifactReference
     * @description An immutable evidence reference and its role in an event.
     */
    ArtifactReference: {
      /** Id */
      id: string;
      /** Role */
      role: string;
    };
    /**
     * ArtifactResponse
     * @description Sanitized projection with distinct source and projection hashes.
     */
    ArtifactResponse: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Id */
      id: string;
      /** Kind */
      kind: string;
      /** Source Sha256 */
      source_sha256: string;
      /** Projection Sha256 */
      projection_sha256: string;
      /** Redacted */
      redacted: boolean;
      /** Redacted Fields */
      redacted_fields: string[];
      /** Data */
      data: unknown;
      /** Provenance */
      provenance?: {
        [key: string]: unknown;
      } | null;
      /** Limitations */
      limitations?: string[];
    };
    /**
     * Assessment
     * @description Independent evaluation identity, scope, result, and evidence.
     */
    Assessment: {
      /**
       * Status
       * @default not_checked
       * @enum {string}
       */
      status: "not_checked" | "passed" | "failed" | "unable_to_check";
      /** Evaluator */
      evaluator?: string | null;
      /** Evaluator Version */
      evaluator_version?: string | null;
      /** Result */
      result?: unknown;
      /** Scope */
      scope?: string | null;
      /** Evidence Refs */
      evidence_refs?: string[];
      /** Details */
      details?: {
        [key: string]: unknown;
      };
    };
    /**
     * BudgetView
     * @description Reported estimates and outstanding reservations, never invoice claims.
     */
    BudgetView: {
      /** Limit Usd */
      limit_usd: number;
      /** Estimated Usd */
      estimated_usd: number;
      /** Reserved Usd */
      reserved_usd: number;
      /** Remaining Usd */
      remaining_usd: number;
      /** Calls */
      calls: number;
    };
    /**
     * ConnectionConfig
     * @description A user-supplied connection, sufficient for discovery without tool permission.
     *
     *     ``env_refs`` maps subprocess variable names to names in the host environment.
     *     It contains references, not values. HTTP authentication and model-selected
     *     subprocesses are outside this initial bridge's contract.
     */
    ConnectionConfig: {
      /** Name */
      name: string;
      /**
       * Transport
       * @enum {string}
       */
      transport: "stdio" | "streamable_http";
      /** Command */
      command?: string | null;
      /** Args */
      args?: string[];
      /** Url */
      url?: string | null;
      /** Env Refs */
      env_refs?: {
        [key: string]: string;
      };
      /**
       * Timeout Seconds
       * @default 30
       */
      timeout_seconds: number;
    };
    /**
     * ConnectorListResponse
     * @description Saved connections available during task setup.
     */
    ConnectorListResponse: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Items */
      items: components["schemas"]["ConnectorResponse"][];
    };
    /**
     * ConnectorRequest
     * @description Select permitted tools from a completed discovery.
     */
    ConnectorRequest: {
      /** Discovery Id */
      discovery_id: string;
      /** Allowed Tools */
      allowed_tools: string[];
    };
    /**
     * ConnectorResponse
     * @description A saved connector bound to its genuine discovery receipt.
     */
    ConnectorResponse: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Connector Id */
      connector_id: string;
      /** Discovery Id */
      discovery_id: string;
      /** Configuration */
      configuration: {
        [key: string]: unknown;
      };
      /** Catalog */
      catalog: {
        [key: string]: unknown;
      };
    };
    /**
     * ConstructionAttempt
     * @description An attempt can retain schema evidence without producing a kernel.
     */
    ConstructionAttempt: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Run Id */
      run_id: string;
      /** Status */
      status: string;
      /** Created At */
      created_at: string;
      /** Round Index */
      round_index?: number | null;
      /** Kernel Id */
      kernel_id?: string | null;
      /** Parent Kernel Id */
      parent_kernel_id?: string | null;
      /** Case Links */
      case_links?: {
        [key: string]: unknown;
      }[];
      /** Schema Id */
      schema_id?: string | null;
      /** Schema Artifact Ref */
      schema_artifact_ref?: string | null;
      /** Schema View */
      schema_view?: {
        [key: string]: unknown;
      } | null;
      /** Validation */
      validation?: {
        [key: string]: unknown;
      };
      /** Artifact Refs */
      artifact_refs?: string[];
      /** Limitations */
      limitations?: string[];
    };
    /**
     * DiscoveryRequest
     * @description Explicit connection configuration for one real discovery job.
     */
    DiscoveryRequest: {
      connection: components["schemas"]["ConnectionConfig"];
    };
    /**
     * DiscoveryResponse
     * @description Observed connector capabilities and discovery failure evidence.
     */
    DiscoveryResponse: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Id */
      id: string;
      /** Run Id */
      run_id: string;
      /** Status */
      status: string;
      /** Connection */
      connection: {
        [key: string]: unknown;
      };
      /** Catalog */
      catalog?: {
        [key: string]: unknown;
      } | null;
      /** Artifact Refs */
      artifact_refs?: string[];
      /** Error */
      error?: string | null;
    };
    /**
     * ErrorResponse
     * @description Actionable failure without raw diagnostic or credential material.
     */
    ErrorResponse: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Code */
      code: string;
      /** Message */
      message: string;
      /** Retryable */
      retryable: boolean;
      /** Evidence Refs */
      evidence_refs?: string[];
    };
    /**
     * EventEnvelope
     * @description Durable event cursor plus a bounded, sanitized evidence projection.
     */
    EventEnvelope: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Cursor */
      cursor: string;
      /** Occurred At */
      occurred_at: string;
      /** Task Id */
      task_id: string;
      /** Run Id */
      run_id: string;
      /** Root Run Id */
      root_run_id?: string | null;
      /** Parent Run Id */
      parent_run_id?: string | null;
      /** Step Id */
      step_id?: string | null;
      /** Parent Step Id */
      parent_step_id?: string | null;
      /**
       * Type
       * @enum {string}
       */
      type:
        | "run.lifecycle"
        | "stage.status"
        | "decision.recorded"
        | "observation.recorded"
        | "graph.snapshot"
        | "kernel.candidate"
        | "validation.recorded"
        | "assessment.recorded"
        | "usage.recorded"
        | "evidence.recorded";
      /** Stage */
      stage: string;
      /** Summary */
      summary: string;
      /** Artifact Refs */
      artifact_refs?: components["schemas"]["ArtifactReference"][];
      /** Payload */
      payload?: {
        [key: string]: unknown;
      };
    };
    /**
     * EventsResponse
     * @description A bounded event page pinned to a replay watermark.
     */
    EventsResponse: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Run Id */
      run_id: string;
      /** Items */
      items: components["schemas"]["EventEnvelope"][];
      /** Next Cursor */
      next_cursor: string;
      /** Through */
      through: string;
      /** Has More */
      has_more: boolean;
    };
    /**
     * GraphResponse
     * @description A bounded view of actual graph records, with explicit omission counts.
     */
    GraphResponse: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Id */
      id: string;
      /** Source Artifact Id */
      source_artifact_id: string;
      /** Nodes */
      nodes: {
        [key: string]: unknown;
      }[];
      /** Edges */
      edges: {
        [key: string]: unknown;
      }[];
      /** Total Nodes */
      total_nodes: number;
      /** Total Edges */
      total_edges: number;
      /** Shown Nodes */
      shown_nodes: number;
      /** Shown Edges */
      shown_edges: number;
      /** Omitted Nodes */
      omitted_nodes: number;
      /** Omitted Edges */
      omitted_edges: number;
      /** Scope */
      scope: string;
      /** Limitations */
      limitations?: string[];
    };
    /**
     * HistoryResponse
     * @description Recorded runs, kernel revisions, and failed construction attempts.
     */
    HistoryResponse: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Task Id */
      task_id: string;
      /** Runs */
      runs: components["schemas"]["RunSummary"][];
      /** Kernels */
      kernels: components["schemas"]["KernelSummary"][];
      /** Attempts */
      attempts: components["schemas"]["ConstructionAttempt"][];
    };
    JsonValue: unknown;
    /**
     * KernelDiffResponse
     * @description Structural comparison of recorded definitions, without equivalence claims.
     */
    KernelDiffResponse: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Id */
      id: string;
      /** Against */
      against: string;
      /** Changes */
      changes: {
        [key: string]: unknown;
      }[];
      /** Schema Changed */
      schema_changed: boolean;
      /** Functions Changed */
      functions_changed: boolean;
      /** Same Task */
      same_task: boolean;
      /** Is Parent */
      is_parent: boolean;
      /** Limitations */
      limitations?: string[];
    };
    /**
     * KernelResponse
     * @description Canonical definitions and readable presentation of one frozen kernel.
     */
    KernelResponse: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Id */
      id: string;
      /** Task Id */
      task_id: string;
      /** Parent Id */
      parent_id?: string | null;
      /** Created At */
      created_at?: string | null;
      /** Run Id */
      run_id?: string | null;
      /** Name */
      name: string;
      assessment?: components["schemas"]["Assessment"];
      /**
       * Eligible For Inference
       * @default false
       */
      eligible_for_inference: boolean;
      /** Validation */
      validation?: {
        [key: string]: unknown;
      };
      /** Case Links */
      case_links?: {
        [key: string]: unknown;
      }[];
      /** Schema Id */
      schema_id?: string | null;
      /** Graph Id */
      graph_id?: string | null;
      /** Schema */
      schema: {
        [key: string]: unknown;
      };
      /** Functions */
      functions: {
        [key: string]: unknown;
      }[];
      /** Schema View */
      schema_view: {
        [key: string]: unknown;
      };
      /** Artifact Refs */
      artifact_refs?: string[];
      /** Limitations */
      limitations?: string[];
    };
    /**
     * KernelSummary
     * @description An immutable kernel with its actual parent and construction case links.
     */
    KernelSummary: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Id */
      id: string;
      /** Task Id */
      task_id: string;
      /** Parent Id */
      parent_id?: string | null;
      /** Created At */
      created_at?: string | null;
      /** Run Id */
      run_id?: string | null;
      /** Name */
      name: string;
      assessment?: components["schemas"]["Assessment"];
      /**
       * Eligible For Inference
       * @default false
       */
      eligible_for_inference: boolean;
      /** Validation */
      validation?: {
        [key: string]: unknown;
      };
      /** Case Links */
      case_links?: {
        [key: string]: unknown;
      }[];
      /** Schema Id */
      schema_id?: string | null;
      /** Graph Id */
      graph_id?: string | null;
    };
    /**
     * QuerySpec
     * @description One immutable pool request and split, without reference answers.
     */
    QuerySpec: {
      /** Id */
      id: string;
      /** Query */
      query: string;
      /** Requirements */
      requirements?: string[];
      /** Supplied Documents */
      supplied_documents?: {
        [key: string]: components["schemas"]["JsonValue"];
      }[];
      /**
       * Split
       * @enum {string}
       */
      split: "construction" | "development" | "heldout";
    };
    /**
     * RunCreateRequest
     * @description Start one construction attempt or inference against a chosen kernel.
     */
    RunCreateRequest: {
      /**
       * Operation
       * @enum {string}
       */
      operation: "construct" | "infer";
      /** Kernel Id */
      kernel_id?: string | null;
      /** Query */
      query?: string | null;
      /** Requirements */
      requirements?: string[];
      /** Query Id */
      query_id?: string | null;
    };
    /**
     * RunLimits
     * @description Per-episode execution bounds and a ceiling on new model spending.
     */
    RunLimits: {
      /**
       * Max Steps
       * @default 8
       */
      max_steps: number;
      /**
       * Max Tool Calls
       * @default 6
       */
      max_tool_calls: number;
      /**
       * Max New Spend Usd
       * @default 5
       */
      max_new_spend_usd: number;
    };
    /**
     * RunResponse
     * @description Run header and stable cursor information for replay or live observation.
     */
    RunResponse: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Id */
      id: string;
      /** Task Id */
      task_id: string;
      /** Kind */
      kind: string;
      /**
       * Status
       * @enum {string}
       */
      status: "queued" | "running" | "completed" | "failed" | "interrupted";
      /** Created At */
      created_at: string;
      /** Query */
      query?: string | null;
      /** Query Id */
      query_id?: string | null;
      /** Split */
      split?: string | null;
      /** Kernel Id */
      kernel_id?: string | null;
      /** Root Run Id */
      root_run_id?: string | null;
      /** Parent Run Id */
      parent_run_id?: string | null;
      /** Answer */
      answer?: string | null;
      /** Outcome */
      outcome?: ("complete" | "needs_input" | "unresolved") | null;
      assessment?: components["schemas"]["Assessment"];
      /**
       * Event Count
       * @default 0
       */
      event_count: number;
      /**
       * Last Cursor
       * @default 0
       */
      last_cursor: string;
      /** Artifact Refs */
      artifact_refs?: string[];
      /** Limitations */
      limitations?: string[];
      /** Graph Id */
      graph_id?: string | null;
      /** Initial Graph Id */
      initial_graph_id?: string | null;
      /** Error */
      error?: string | null;
      /** Usage */
      usage?: {
        [key: string]: unknown;
      };
    };
    /**
     * RunSummary
     * @description Execution lifecycle, agent outcome, and assessment are separate fields.
     */
    RunSummary: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Id */
      id: string;
      /** Task Id */
      task_id: string;
      /** Kind */
      kind: string;
      /**
       * Status
       * @enum {string}
       */
      status: "queued" | "running" | "completed" | "failed" | "interrupted";
      /** Created At */
      created_at: string;
      /** Query */
      query?: string | null;
      /** Query Id */
      query_id?: string | null;
      /** Split */
      split?: string | null;
      /** Kernel Id */
      kernel_id?: string | null;
      /** Root Run Id */
      root_run_id?: string | null;
      /** Parent Run Id */
      parent_run_id?: string | null;
      /** Answer */
      answer?: string | null;
      /** Outcome */
      outcome?: ("complete" | "needs_input" | "unresolved") | null;
      assessment?: components["schemas"]["Assessment"];
    };
    /**
     * TaskCreateRequest
     * @description Curator-owned task inputs reusing the authoritative task contracts.
     */
    TaskCreateRequest: {
      /** Name */
      name: string;
      /** Description */
      description: string;
      /** Base Prompt */
      base_prompt: string;
      /** Queries */
      queries: components["schemas"]["QuerySpec"][];
      /** Connector Ids */
      connector_ids: string[];
      limits?: components["schemas"]["RunLimits"];
      /**
       * Seed
       * @default 42
       */
      seed: number;
      /**
       * Sampling Fraction
       * @default 0.2
       */
      sampling_fraction: number;
    };
    /**
     * TaskCreatedResponse
     * @description Identifiers of a persisted MCP task surface.
     */
    TaskCreatedResponse: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Task Id */
      task_id: string;
      /** Surface Id */
      surface_id: string;
      /**
       * Kind
       * @default mcp
       * @constant
       */
      kind: "mcp";
    };
    /**
     * TaskListResponse
     * @description Configured tasks, newest first when dates were recorded.
     */
    TaskListResponse: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Items */
      items: components["schemas"]["TaskSummary"][];
    };
    /**
     * TaskResponse
     * @description Setup and public requests associated with a task.
     */
    TaskResponse: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Id */
      id: string;
      /**
       * Kind
       * @enum {string}
       */
      kind: "mcp" | "corpus";
      /** Name */
      name: string;
      /** Description */
      description: string;
      /** Status */
      status: string;
      /** Created At */
      created_at?: string | null;
      /** Active Kernel Id */
      active_kernel_id?: string | null;
      /** Latest Kernel Id */
      latest_kernel_id?: string | null;
      /**
       * Run Count
       * @default 0
       */
      run_count: number;
      /**
       * Query Count
       * @default 0
       */
      query_count: number;
      /**
       * Legacy
       * @default false
       */
      legacy: boolean;
      /**
       * Base Prompt
       * @default
       */
      base_prompt: string;
      /** Queries */
      queries?: {
        [key: string]: unknown;
      }[];
      /** Connections */
      connections?: {
        [key: string]: unknown;
      }[];
      /** Limits */
      limits?: {
        [key: string]: unknown;
      };
      /** Capabilities */
      capabilities?: {
        [key: string]: unknown;
      }[];
      /** Limitations */
      limitations?: string[];
    };
    /**
     * TaskSummary
     * @description One configured MCP surface or historical corpus task.
     */
    TaskSummary: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Id */
      id: string;
      /**
       * Kind
       * @enum {string}
       */
      kind: "mcp" | "corpus";
      /** Name */
      name: string;
      /** Description */
      description: string;
      /** Status */
      status: string;
      /** Created At */
      created_at?: string | null;
      /** Active Kernel Id */
      active_kernel_id?: string | null;
      /** Latest Kernel Id */
      latest_kernel_id?: string | null;
      /**
       * Run Count
       * @default 0
       */
      run_count: number;
      /**
       * Query Count
       * @default 0
       */
      query_count: number;
      /**
       * Legacy
       * @default false
       */
      legacy: boolean;
    };
    /**
     * WorkspaceResponse
     * @description Small workspace overview without machine paths or credential material.
     */
    WorkspaceResponse: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      budget: components["schemas"]["BudgetView"];
      /** Task Count */
      task_count: number;
      /** Run Count */
      run_count: number;
      /**
       * Session Token
       * @default
       */
      session_token: string;
      /**
       * Model
       * @default
       */
      model: string;
      /** Readiness */
      readiness?: {
        [key: string]: unknown;
      };
      /** Settings */
      settings?: {
        [key: string]: unknown;
      };
      /** Supported Actions */
      supported_actions?: string[];
    };
  };
  responses: never;
  parameters: never;
  requestBodies: never;
  headers: never;
  pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
  workspace_api_v1_workspace_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["WorkspaceResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  discover_api_v1_connector_discoveries_post: {
    parameters: {
      query?: never;
      header?: {
        "idempotency-key"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["DiscoveryRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AcceptedRun"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  discovery_api_v1_connector_discoveries__identity__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        identity: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["DiscoveryResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  connectors_api_v1_connectors_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ConnectorListResponse"];
        };
      };
    };
  };
  save_connector_api_v1_connectors_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ConnectorRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ConnectorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  tasks_api_v1_tasks_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["TaskListResponse"];
        };
      };
    };
  };
  create_task_api_v1_tasks_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["TaskCreateRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["TaskCreatedResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  task_api_v1_tasks__identity__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        identity: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["TaskResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  history_api_v1_tasks__identity__history_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        identity: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HistoryResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  submit_api_v1_tasks__identity__runs_post: {
    parameters: {
      query?: never;
      header?: {
        "idempotency-key"?: string | null;
      };
      path: {
        identity: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RunCreateRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AcceptedRun"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  run_api_v1_runs__identity__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        identity: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RunResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  events_api_v1_runs__identity__events_get: {
    parameters: {
      query?: {
        after?: string;
        through?: string | null;
        limit?: number;
      };
      header?: never;
      path: {
        identity: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EventsResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  stream_api_v1_runs__identity__stream_get: {
    parameters: {
      query?: {
        after?: string;
      };
      header?: {
        "last-event-id"?: string | null;
      };
      path: {
        identity: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  kernel_api_v1_kernels__identity__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        identity: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["KernelResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  diff_api_v1_kernels__identity__diff_get: {
    parameters: {
      query: {
        against: string;
      };
      header?: never;
      path: {
        identity: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["KernelDiffResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  graph_api_v1_graphs__identity__get: {
    parameters: {
      query?: {
        focus?: string | null;
        limit?: number;
      };
      header?: never;
      path: {
        identity: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["GraphResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  artifact_api_v1_artifacts__identity__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        identity: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ArtifactResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
}
