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
      /** Typed Data */
      typed_data?:
        | components["schemas"]["TaskIR"]
        | components["schemas"]["CandidateSelection"]
        | components["schemas"]["EvidenceDemand"]
        | components["schemas"]["MaterializationPlan"]
        | components["schemas"]["CoverageReceipt"]
        | components["schemas"]["SufficiencyResult"]
        | components["schemas"]["VerificationReport"]
        | components["schemas"]["PreservationCertificate"]
        | null;
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
     * CandidateSelection
     * @description Selection records independent verifier evidence and explicit cost ties.
     */
    CandidateSelection: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Task Ir Id */
      task_ir_id: string;
      /** Candidate Ids */
      candidate_ids: string[];
      /** Selected Kernel Id */
      selected_kernel_id: string | null;
      /** Verification Ids */
      verification_ids: string[];
      /**
       * Disposition
       * @enum {string}
       */
      disposition: "target_met" | "incomplete" | "rejected";
      /** Stop Reason */
      stop_reason: string;
      /** Ranks */
      ranks?: {
        [key: string]: number[];
      };
    };
    /**
     * CanonicalInstruction
     * @description A deterministic primitive call with de Bruijn-like positional step references.
     */
    CanonicalInstruction: {
      /** Operator */
      operator: string;
      /** Arguments */
      arguments: {
        [key: string]: components["schemas"]["JsonValue"];
      };
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
     * CoverageReceipt
     * @description Independent coverage evidence supplied by trusted executor-side adapters.
     *
     *     This DTO is not an authorization token. Only checker-produced artifacts,
     *     resolved by the owning executor, may enter ``assess_sufficiency``. A candidate
     *     cannot turn its declaration into a trusted receipt. Snapshot completeness
     *     deliberately cannot establish source-population completeness.
     */
    CoverageReceipt: {
      /**
       * Format Version
       * @default 1
       * @constant
       */
      format_version: 1;
      /** Demand Id */
      demand_id: string;
      /** Schema Sha256 */
      schema_sha256: string;
      /** Graph Sha256 */
      graph_sha256: string;
      /** Source Receipt Ids */
      source_receipt_ids?: string[];
      /** Evidence Refs */
      evidence_refs?: string[];
      /** Checker Id */
      checker_id?: string | null;
      /** Checker Version */
      checker_version?: string | null;
      /**
       * Basis
       * @default observed_only
       * @enum {string}
       */
      basis:
        | "adapter_verified"
        | "deterministic_source_mapping"
        | "observed_only"
        | "model_claim"
        | "generated_check";
      /**
       * Scope
       * @default materialized_snapshot
       * @enum {string}
       */
      scope: "source_population" | "materialized_snapshot";
      /**
       * Population Complete
       * @default false
       */
      population_complete: boolean;
      /**
       * Adjacency Complete
       * @default false
       */
      adjacency_complete: boolean;
      /** Fields Checked */
      fields_checked?: {
        [key: string]: string[];
      };
      /** Pagination Exhausted */
      pagination_exhausted?: boolean | null;
      /** Frontier Exhausted */
      frontier_exhausted?: boolean | null;
      /** Missing */
      missing?: components["schemas"]["MissingFact"][];
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
     * EntitySelector
     * @description Exact lookup conditions, using the runtime's existing lookup semantics.
     */
    EntitySelector: {
      /** Entity Types */
      entity_types?: string[];
      /** Entity Ids */
      entity_ids?: string[] | null;
      /** Primary Key */
      primary_key?: {
        [key: string]: components["schemas"]["JsonValue"];
      };
      /** Property Filters */
      property_filters?: {
        [key: string]: components["schemas"]["JsonValue"];
      };
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
      /** Flow */
      flow?: ("learning" | "verification" | "instantiation") | null;
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
     * EvidenceDemand
     * @description Frozen-computation evidence needs after binding one invocation's arguments.
     */
    EvidenceDemand: {
      /**
       * Format Version
       * @default 1
       * @constant
       */
      format_version: 1;
      /**
       * Derivation Version
       * @default demand-v1
       */
      derivation_version: string;
      /** Function Name */
      function_name: string;
      /** Schema Sha256 */
      schema_sha256: string;
      /** Function Sha256 */
      function_sha256: string;
      /** Arguments Sha256 */
      arguments_sha256: string;
      /** Entity Types */
      entity_types: string[];
      /** Required Fields */
      required_fields: {
        [key: string]: string[];
      };
      /** Relation Types */
      relation_types?: string[];
      /** Selectors */
      selectors?: components["schemas"]["EntitySelector"][];
      /** Traversals */
      traversals?: components["schemas"]["TraversalDemand"][];
      /** Acquisitions */
      acquisitions?: {
        [key: string]: components["schemas"]["JsonValue"];
      }[];
      /**
       * Coverage Mode
       * @default complete_scope
       * @enum {string}
       */
      coverage_mode: "witness" | "complete_scope" | "complete_adjacency";
      /** Unknowns */
      unknowns?: string[];
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
      /** Construction Profile */
      construction_profile?: string | null;
      /** Flow Evidence */
      flow_evidence?: {
        [key: string]: string[];
      };
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
      /** Construction Profile */
      construction_profile?: string | null;
      /** Flow Evidence */
      flow_evidence?: {
        [key: string]: string[];
      };
    };
    /**
     * MaterializationPlan
     * @description Executor-owned plan; native capability arguments are never invented here.
     */
    MaterializationPlan: {
      /**
       * Format Version
       * @default 1
       * @constant
       */
      format_version: 1;
      /** Demand Id */
      demand_id: string;
      /** Kernel Id */
      kernel_id: string;
      /** Receipt Ids */
      receipt_ids?: string[];
      /** Acquisition Requests */
      acquisition_requests?: {
        [key: string]: components["schemas"]["JsonValue"];
      }[];
      /**
       * Extractor Version
       * @default demand-v1
       */
      extractor_version: string;
      /** Expansion Reason */
      expansion_reason?: string | null;
    };
    /**
     * MissingFact
     * @description Absence is attributed rather than silently converted to a null value.
     */
    MissingFact: {
      /** Entity Id */
      entity_id: string;
      /** Property */
      property: string;
      /**
       * State
       * @enum {string}
       */
      state:
        | "unmaterialized"
        | "source_absent"
        | "explicit_null"
        | "extraction_failure";
      /** Evidence Refs */
      evidence_refs?: string[];
    };
    /**
     * PlanIR
     * @description Finite eager pure plan; external JSON validation contracts remain exact.
     */
    PlanIR: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Inputs */
      inputs: {
        [key: string]: components["schemas"]["JsonValue"];
      };
      /** Output Schema */
      output_schema: {
        [key: string]: components["schemas"]["JsonValue"];
      };
      /** Steps */
      steps: components["schemas"]["CanonicalInstruction"][];
      result: components["schemas"]["JsonValue"];
    };
    /**
     * PreservationCertificate
     * @description Evidence for one adjacent revision pair, conditional on the runtime bridge.
     */
    PreservationCertificate: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /**
       * Status
       * @enum {string}
       */
      status: "certified" | "unknown" | "counterexample" | "invalid_evidence";
      /** Parent Id */
      parent_id: string;
      /** Candidate Id */
      candidate_id: string;
      /** Parent Sha256 */
      parent_sha256: string;
      /** Candidate Sha256 */
      candidate_sha256: string;
      /** Schema Sha256 */
      schema_sha256: string;
      /** Protected Functions */
      protected_functions: string[];
      /** Rules */
      rules?: string[];
      /** Plans */
      plans?: {
        [key: string]: {
          [key: string]: components["schemas"]["PlanIR"];
        };
      };
      /** Dependencies */
      dependencies?: {
        [key: string]: string;
      };
      /** Assumptions */
      assumptions?: string[];
      /** Summary */
      summary: string;
      /** Proof Receipt */
      proof_receipt?: {
        [key: string]: components["schemas"]["JsonValue"];
      } | null;
      /**
       * Certificate Sha256
       * @default
       */
      certificate_sha256: string;
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
     * @description Start bounded construction or inference against a chosen kernel.
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
     * SemanticField
     * @description A semantic role independent of the ontology a candidate later proposes.
     */
    SemanticField: {
      /** Id */
      id: string;
      /** Description */
      description: string;
      /**
       * Value Type
       * @enum {string}
       */
      value_type:
        "string" | "number" | "boolean" | "date" | "entity" | "unknown";
      /** Unit */
      unit?: string | null;
      /** Grain */
      grain: string;
      /** Source Capability Ids */
      source_capability_ids?: string[];
    };
    /**
     * SufficiencyResult
     * @description Nonblocking evidence-scope assessment, separate from execution and task success.
     */
    SufficiencyResult: {
      /**
       * Format Version
       * @default 1
       * @constant
       */
      format_version: 1;
      /** Demand Id */
      demand_id: string;
      /**
       * Status
       * @enum {string}
       */
      status: "satisfied" | "needs_evidence" | "unknown" | "incompatible";
      /**
       * Coverage Mode
       * @enum {string}
       */
      coverage_mode: "witness" | "complete_scope" | "complete_adjacency";
      /** Unmet Demands */
      unmet_demands?: string[];
      /** Missing */
      missing?: components["schemas"]["MissingFact"][];
      /** Evidence Refs */
      evidence_refs?: string[];
      /** Node Count */
      node_count: number;
      /** Edge Count */
      edge_count: number;
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
     * TaskIR
     * @description Frozen campaign bank derived from construction inputs only.
     */
    TaskIR: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /**
       * Profile
       * @default demand-driven-v1
       * @constant
       */
      profile: "demand-driven-v1";
      /** Source Sha256 */
      source_sha256: string;
      /** Analysis Sha256 */
      analysis_sha256: string;
      /** Analysis Id */
      analysis_id?: string | null;
      /** Scope */
      scope: string;
      /** Obligations */
      obligations: components["schemas"]["TaskObligation"][];
      /**
       * Exploration Limit
       * @default 128
       */
      exploration_limit: number;
      /**
       * Exploration Extra Operators
       * @default 2
       */
      exploration_extra_operators: number;
      /**
       * Exploration Omitted
       * @default 0
       */
      exploration_omitted: number;
      /** Interpretation Gaps */
      interpretation_gaps?: string[];
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
     * TaskObligation
     * @description Literal or mechanically derived behavior with no candidate-produced score.
     */
    TaskObligation: {
      /** Obligation Id */
      obligation_id: string;
      /** Case Id */
      case_id: string;
      /** Text */
      text: string;
      /** Parent Requirement Ids */
      parent_requirement_ids: string[];
      /** Derivation Rule */
      derivation_rule: string;
      program?: components["schemas"]["TaskProgram"] | null;
      /**
       * Group
       * @enum {string}
       */
      group: "retrieval" | "subtask" | "composition";
      /**
       * Mandatory
       * @default true
       */
      mandatory: boolean;
      /**
       * Semantic Status
       * @default proposed
       * @enum {string}
       */
      semantic_status: "proposed" | "grounded";
      /** Oracle Ref */
      oracle_ref?: string | null;
    };
    /**
     * TaskOperation
     * @description One typed task operation, with explicit dependencies and semantic fields.
     *
     *     This is a task interpretation, not an executable function body. Source
     *     acquisition and candidate ontology names do not enter the operation graph.
     */
    TaskOperation: {
      /** Id */
      id: string;
      /**
       * Operator
       * @enum {string}
       */
      operator:
        "read" | "filter" | "project" | "traverse" | "aggregate" | "arithmetic";
      /** Inputs */
      inputs?: string[];
      /** Fields */
      fields?: string[];
      /**
       * Result Kind
       * @enum {string}
       */
      result_kind: "records" | "scalar" | "path";
      /** Parameters */
      parameters?: {
        [key: string]: components["schemas"]["JsonValue"];
      };
    };
    /**
     * TaskProgram
     * @description Finite interpretation whose references are checked before S/F exists.
     */
    TaskProgram: {
      /** Fields */
      fields?: components["schemas"]["SemanticField"][];
      /** Operations */
      operations: components["schemas"]["TaskOperation"][];
      /** Result */
      result: string;
      /** Input Domain */
      input_domain?: {
        [key: string]: components["schemas"]["JsonValue"];
      };
      /** Observation Contract */
      observation_contract: string;
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
      /** Selected Kernel Id */
      selected_kernel_id?: string | null;
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
      /** Selected Kernel Id */
      selected_kernel_id?: string | null;
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
     * TraversalDemand
     * @description A bounded adjacency request whose seeds are already resolved identities.
     */
    TraversalDemand: {
      /** Start Entity Ids */
      start_entity_ids: string[];
      /** Relation Types */
      relation_types: string[];
      /**
       * Direction
       * @default outgoing
       * @enum {string}
       */
      direction: "outgoing" | "incoming" | "both";
      /**
       * Max Hops
       * @default 1
       */
      max_hops: number;
    };
    /**
     * VerificationCheck
     * @description One checked evidence dimension, never a composite success score.
     */
    VerificationCheck: {
      /** Obligation Id */
      obligation_id?: string | null;
      /**
       * Dimension
       * @enum {string}
       */
      dimension:
        | "structure"
        | "ontology"
        | "graph"
        | "execution"
        | "generated"
        | "coverage"
        | "task"
        | "preservation";
      /**
       * Status
       * @enum {string}
       */
      status: "passed" | "failed" | "unknown";
      /** Summary */
      summary: string;
      /** Evidence Refs */
      evidence_refs?: string[];
      /** Details */
      details?: {
        [key: string]: components["schemas"]["JsonValue"];
      };
    };
    /**
     * VerificationReport
     * @description Decision and provenance for one candidate, independent of learner utility.
     */
    VerificationReport: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Candidate Id */
      candidate_id: string;
      /** Parent Id */
      parent_id?: string | null;
      /**
       * Disposition
       * @enum {string}
       */
      disposition:
        "execution_eligible" | "target_met" | "incomplete" | "rejected";
      /** Execution Eligible */
      execution_eligible: boolean;
      /** Target Met */
      target_met: boolean;
      /** Checks */
      checks: components["schemas"]["VerificationCheck"][];
      /** Counterexamples */
      counterexamples?: {
        [key: string]: components["schemas"]["JsonValue"];
      }[];
      /** Unresolved Obligation Ids */
      unresolved_obligation_ids?: string[];
      /** Coverage By Group */
      coverage_by_group?: {
        [key: string]: {
          [key: string]: number;
        };
      };
      /** Generated Coverage By Group */
      generated_coverage_by_group?: {
        [key: string]: {
          [key: string]: number;
        };
      };
      /**
       * Known Regressions
       * @default 0
       */
      known_regressions: number;
      preservation?: components["schemas"]["PreservationCertificate"] | null;
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
