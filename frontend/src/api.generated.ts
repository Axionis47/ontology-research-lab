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
     * AcquisitionBinding
     * @description Frozen source binding for a pure callable, separate from its implementation.
     *
     *     The expression language only binds declared function inputs to a catalogued
     *     tool's native arguments. It cannot select a tool dynamically, execute code,
     *     or interpret the question. Authorization remains the executor's catalog.
     */
    AcquisitionBinding: {
      /**
       * Format Version
       * @default 1
       * @constant
       */
      format_version: 1;
      /** Function Name */
      function_name: string;
      /** Schema Sha256 */
      schema_sha256: string;
      /** Function Sha256 */
      function_sha256: string;
      /** Capability Id */
      capability_id: string;
      /** Native Arguments */
      native_arguments: {
        [key: string]: components["schemas"]["JsonValue"];
      };
      /** Contract Id */
      contract_id: string;
    };
    /**
     * AdapterEdge
     * @description One shared M/A/B package bound to the actual parent-child revision edge.
     */
    AdapterEdge: {
      /** Parent Id */
      parent_id: string;
      /** Child Id */
      child_id: string;
      migration?: components["schemas"]["MigrationSpec"];
      call_adapter: components["schemas"]["AdapterSpec"];
      /** Step Mappings */
      step_mappings?: {
        [key: string]: {
          [key: string]: string;
        };
      };
      /** Proposal Ref */
      proposal_ref?: string | null;
    };
    /**
     * AdapterSpec
     * @description A version-bound, inspectable set of bijective interface renames.
     */
    AdapterSpec: {
      /** Old Revision */
      old_revision: string;
      /** New Revision */
      new_revision: string;
      /** Mappings */
      mappings?: components["schemas"]["FunctionMapping"][];
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
        | components["schemas"]["EvaluationPlan"]
        | components["schemas"]["EvaluationReceipt"]
        | components["schemas"]["CaseEvaluationReceipt"]
        | components["schemas"]["BehaviorBank"]
        | components["schemas"]["CompilationResult"]
        | components["schemas"]["ComparisonContract"]
        | components["schemas"]["ReplayCase"]
        | components["schemas"]["ReplayBank"]
        | components["schemas"]["ReplayReport"]
        | components["schemas"]["ReplayBankReport"]
        | components["schemas"]["AdapterEdge"]
        | components["schemas"]["DiscoveryResult"]
        | components["schemas"]["DiscoveryState"]
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
     * BehaviorBank
     * @description Frozen check meanings and denominators, independent of candidate code.
     */
    BehaviorBank: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /**
       * Flow
       * @default learning
       * @constant
       */
      flow: "learning";
      /** Task Ir Sha256 */
      task_ir_sha256: string;
      /** Behaviors */
      behaviors: components["schemas"]["BehaviorTemplate"][];
      /**
       * Max Mutants Per Behavior
       * @default 8
       */
      max_mutants_per_behavior: number;
      /**
       * Max Mutants Campaign
       * @default 64
       */
      max_mutants_campaign: number;
      /**
       * Parameter Strata
       * @default 2
       */
      parameter_strata: number;
      /**
       * Interpretation Status
       * @default proposed
       * @constant
       */
      interpretation_status: "proposed";
      /** Gaps */
      gaps?: string[];
    };
    /**
     * BehaviorCheckView
     * @description A bounded readable check, with its actual callable and evidence dimension.
     */
    BehaviorCheckView: {
      /** Id */
      id?: string | null;
      /** Function Name */
      function_name?: string | null;
      /** Dimension */
      dimension: string;
      /** Status */
      status: string;
      /** Summary */
      summary: string;
      /** Evidence Refs */
      evidence_refs?: string[];
    };
    /**
     * BehaviorTemplate
     * @description A semantic computation or callable getter, not a trajectory prefix.
     */
    BehaviorTemplate: {
      /** Behavior Id */
      behavior_id: string;
      program: components["schemas"]["TaskProgram"] | null;
      /**
       * Kind
       * @default computation
       * @enum {string}
       */
      kind: "computation" | "projection" | "point" | "uninterpreted";
      /** Projection Fields */
      projection_fields?: string[];
      /** Selector Fields */
      selector_fields?: string[];
      /** Obligation Ids */
      obligation_ids: string[];
      /** Mandatory */
      mandatory: boolean;
      /**
       * Group
       * @enum {string}
       */
      group: "retrieval" | "subtask" | "composition";
      /** Description */
      description: string;
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
    /** CaseDecision */
    CaseDecision: {
      case: components["schemas"]["EvaluationCase"];
      manifest: components["schemas"]["DependencyManifest"];
      /**
       * Local Action
       * @enum {string}
       */
      local_action: "reuse" | "proof" | "replay" | "rematerialize" | "defer";
      /** Reasons */
      reasons: string[];
      /** Previous Receipt Ref */
      previous_receipt_ref?: string | null;
      /**
       * Planner Action
       * @default defer
       * @enum {string}
       */
      planner_action: "fresh" | "defer" | "reuse" | "not_required";
      /**
       * Planner Reason
       * @default No fresh execution selected
       */
      planner_reason: string;
      /**
       * Planner Sentinel
       * @default false
       */
      planner_sentinel: boolean;
    };
    /**
     * CaseEvaluationReceipt
     * @description Actual local evidence and independently attributed fresh agent evidence.
     */
    CaseEvaluationReceipt: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Candidate Id */
      candidate_id: string;
      /** Case Id */
      case_id: string;
      /** Bank Version */
      bank_version: string;
      manifest: components["schemas"]["DependencyManifest"];
      /**
       * Action
       * @enum {string}
       */
      action: "reuse" | "proof" | "replay" | "rematerialize" | "defer";
      /**
       * Status
       * @enum {string}
       */
      status: "passed" | "failed" | "unknown";
      /** Summary */
      summary: string;
      /** Evidence Refs */
      evidence_refs?: string[];
      /** Evaluated Case Ref */
      evaluated_case_ref?: string | null;
      /** Source Candidate Id */
      source_candidate_id?: string | null;
      /** Previous Receipt Ref */
      previous_receipt_ref?: string | null;
      /** Results */
      results?: {
        [key: string]: unknown;
      }[];
      /** Fresh Episode Ref */
      fresh_episode_ref?: string | null;
      /** Fresh Candidate Id */
      fresh_candidate_id?: string | null;
      historical_agent_evidence?:
        components["schemas"]["HistoricalAgentEvidence"] | null;
      /** Agent Outcome */
      agent_outcome?: string | null;
      /**
       * Task Assessment
       * @default not_checked
       */
      task_assessment: string;
      /**
       * Planner Exposure
       * @default deferred
       * @enum {string}
       */
      planner_exposure: "checked" | "unchanged" | "deferred" | "not_applicable";
      /**
       * Independent
       * @default false
       */
      independent: boolean;
    };
    /**
     * ComparisonContract
     * @description Exact typed equality; unordered collections require an original declaration.
     */
    ComparisonContract: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /**
       * Collection
       * @default ordered
       * @enum {string}
       */
      collection: "ordered" | "multiset";
    };
    /**
     * CompilationResult
     * @description Compilation may report unsupported behaviors without discarding them.
     */
    CompilationResult: {
      /** Functions */
      functions: {
        [key: string]: unknown;
      }[];
      /** Entries */
      entries: components["schemas"]["CompiledEntry"][];
      /** Acquisition Bindings */
      acquisition_bindings: {
        [key: string]: unknown;
      }[];
      /** Diagnostics */
      diagnostics: {
        [key: string]: unknown;
      }[];
    };
    /**
     * CompiledEntry
     * @description An actual pure callable and the behavior whose meaning it binds.
     */
    CompiledEntry: {
      /** Behavior Id */
      behavior_id: string;
      /** Function Name */
      function_name: string;
      /** Function Sha256 */
      function_sha256: string;
      /** Generated */
      generated: boolean;
      /** Required Inputs */
      required_inputs: {
        [key: string]: unknown;
      };
      /** Domain Issues */
      domain_issues?: string[];
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
     * DependencyManifest
     * @description Separate computation, materialization and full planner-visible exposure.
     */
    DependencyManifest: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Candidate Id */
      candidate_id: string;
      /** Case Id */
      case_id: string;
      /** Bank Version */
      bank_version: string;
      computation: components["schemas"]["DependencyScope"];
      materialization: components["schemas"]["DependencyScope"];
      planner: components["schemas"]["DependencyScope"];
      /** Function Names */
      function_names: string[];
      /** Cache Key */
      cache_key: string;
    };
    /**
     * DependencyScope
     * @description Complete means conservative static scope, never just observed node IDs.
     */
    DependencyScope: {
      /**
       * Completeness
       * @enum {string}
       */
      completeness: "complete" | "unknown";
      /** Fingerprints */
      fingerprints?: {
        [key: string]: string;
      };
      /** Reasons */
      reasons?: string[];
    };
    /**
     * DerivedRelation
     * @description Connect two outputs derived from the same actual source record.
     */
    DerivedRelation: {
      /** Source Type */
      source_type: string;
      /** Source Target Type */
      source_target_type: string;
      /** Target Target Type */
      target_target_type: string;
      /** Relation */
      relation: string;
    };
    /** DiscoveryContextSummary */
    DiscoveryContextSummary: {
      /** Catalog Id */
      catalog_id: string;
      /** Kernel Id */
      kernel_id: string;
      /**
       * Context Bytes
       * @default 0
       */
      context_bytes: number;
      /**
       * Max Context Bytes
       * @default 36000
       */
      max_context_bytes: number;
      /** Loaded Function Ids */
      loaded_function_ids?: string[];
      /** View Definition Ids */
      view_definition_ids?: string[];
      /** Evicted Definition Ids */
      evicted_definition_ids?: string[];
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
     * DiscoveryResult
     * @description One actual read-only lookup, distinct from domain execution evidence.
     */
    DiscoveryResult: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Catalog Id */
      catalog_id: string;
      /** Kernel Id */
      kernel_id: string;
      /** Tool */
      tool: string;
      /**
       * Status
       * @default ok
       * @enum {string}
       */
      status: "ok" | "error";
      /**
       * Query
       * @default
       */
      query: string;
      /**
       * Kind
       * @default all
       */
      kind: string;
      /** Definition Id */
      definition_id?: string | null;
      /**
       * Pointer
       * @default
       */
      pointer: string;
      /** Items */
      items?: {
        [key: string]: components["schemas"]["JsonValue"];
      }[];
      /**
       * Total Count
       * @default 0
       */
      total_count: number;
      /**
       * Offset
       * @default 0
       */
      offset: number;
      /** Next Cursor */
      next_cursor?: string | null;
      /**
       * Has More
       * @default false
       */
      has_more: boolean;
      /**
       * Complete
       * @default true
       */
      complete: boolean;
      definition?: components["schemas"]["JsonValue"];
      /** Dependencies */
      dependencies?: string[];
      /**
       * Dependency Count
       * @default 0
       */
      dependency_count: number;
      /** Loaded Tool Name */
      loaded_tool_name?: string | null;
      /** Error */
      error?: string | null;
      context?: components["schemas"]["DiscoveryContextSummary"] | null;
    };
    /**
     * DiscoveryState
     * @description Small checkpoint state; canonical definitions stay in the frozen kernel.
     */
    DiscoveryState: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Catalog Id */
      catalog_id: string;
      /** Loaded Function Ids */
      loaded_function_ids?: string[];
      /** Views */
      views?: {
        [key: string]: components["schemas"]["JsonValue"];
      }[];
      /** Evicted Definition Ids */
      evicted_definition_ids?: string[];
    };
    /**
     * EndpointTypes
     * @description Select one mapped type per endpoint when a split creates alternatives.
     */
    EndpointTypes: {
      /** Source */
      source?: string | null;
      /** Target */
      target?: string | null;
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
     * EvaluationActionView
     * @description One recorded local evaluation decision, separately from planner exposure.
     */
    EvaluationActionView: {
      /** Case Id */
      case_id: string;
      /** Local Action */
      local_action: string;
      /** Planner Action */
      planner_action?: string | null;
      /** Status */
      status?: string | null;
      /** Reasons */
      reasons?: string[];
      /** Planner Reason */
      planner_reason?: string | null;
      /** Source Candidate Id */
      source_candidate_id?: string | null;
      /** Fresh Candidate Id */
      fresh_candidate_id?: string | null;
      /** Task Assessment */
      task_assessment?: string | null;
      /** Evidence Refs */
      evidence_refs?: string[];
    };
    /**
     * EvaluationCase
     * @description One versioned construction/development evaluation unit, never held out.
     */
    EvaluationCase: {
      /** Case Id */
      case_id: string;
      /** Question */
      question?: string | null;
      /**
       * Split
       * @default construction
       * @enum {string}
       */
      split: "construction" | "development" | "development-regression";
      /** Bank Version */
      bank_version: string;
      /** Calls */
      calls?: components["schemas"]["ReplayCall"][];
      /** Graph Ref */
      graph_ref?: string | null;
      /** Source Refs */
      source_refs?: string[];
      /** Demand Ref */
      demand_ref?: string | null;
      /** Extractor Version */
      extractor_version?: string | null;
      /** Episode Ref */
      episode_ref?: string | null;
      /** Generated Check Refs */
      generated_check_refs?: string[];
      /** Behavior Input Ref */
      behavior_input_ref?: string | null;
      /**
       * Is New
       * @default false
       */
      is_new: boolean;
      /**
       * Counterexample
       * @default false
       */
      counterexample: boolean;
      /**
       * Last Fresh Round
       * @default -1
       */
      last_fresh_round: number;
      /** Estimated Fresh Cost */
      estimated_fresh_cost?: number | null;
      /**
       * Planner Required
       * @default true
       */
      planner_required: boolean;
    };
    /** EvaluationPlan */
    EvaluationPlan: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Candidate Id */
      candidate_id: string;
      /** Bank Version */
      bank_version: string;
      /** Decisions */
      decisions: components["schemas"]["CaseDecision"][];
      /**
       * Max Fresh Cases
       * @default 3
       */
      max_fresh_cases: number;
      /**
       * Max Planner Sentinels
       * @default 1
       */
      max_planner_sentinels: number;
      /**
       * Estimated Fresh Cost
       * @default 0
       */
      estimated_fresh_cost: number;
      /** Fresh Budget */
      fresh_budget?: number | null;
      /**
       * Bank Comparable
       * @default true
       */
      bank_comparable: boolean;
      /**
       * Plan Sha256
       * @default
       */
      plan_sha256: string;
    };
    /** EvaluationReceipt */
    EvaluationReceipt: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Candidate Id */
      candidate_id: string;
      /** Plan Sha256 */
      plan_sha256: string;
      /** Case Receipt Refs */
      case_receipt_refs: {
        [key: string]: string;
      };
      /** Deferred Case Ids */
      deferred_case_ids: string[];
      /** Known Regression Case Ids */
      known_regression_case_ids: string[];
      /** Preservation Difference Case Ids */
      preservation_difference_case_ids?: string[];
      /** Bank Comparable */
      bank_comparable: boolean;
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
      flow_evidence?: components["schemas"]["FlowEvidence"] | null;
      inference_discovery?:
        components["schemas"]["InferenceDiscoveryView"] | null;
      inference_context?: components["schemas"]["InferenceContextView"] | null;
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
       * @default demand-v2
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
    /** FirstDifference */
    FirstDifference: {
      /** Phase */
      phase: string;
      /** Call Index */
      call_index?: number | null;
      /**
       * Path
       * @default $
       */
      path: string;
      /** Reason */
      reason: string;
      /** Expected */
      expected?: unknown;
      /** Actual */
      actual?: unknown;
      /** Original Function */
      original_function?: string | null;
      /** Current Function */
      current_function?: string | null;
      /**
       * Repair Target
       * @enum {string}
       */
      repair_target:
        | "migration"
        | "schema"
        | "call_adapter"
        | "function"
        | "verification_gap"
        | "baseline";
    };
    /**
     * FlowEvidence
     * @description Typed, bounded observation of recorded decisions, checks, and expansion.
     *
     *     Counts describe recorded evidence only. Missing measurements remain absent.
     *     Source artifacts retain complete details when lists are bounded for display.
     */
    FlowEvidence: {
      /** Kind */
      kind: string;
      /** Artifact Id */
      artifact_id?: string | null;
      /** Action Counts */
      action_counts?: {
        [key: string]: number;
      };
      /** Planner Counts */
      planner_counts?: {
        [key: string]: number;
      };
      /** Actions */
      actions?: components["schemas"]["EvaluationActionView"][];
      /**
       * Omitted Actions
       * @default 0
       */
      omitted_actions: number;
      /** Checks */
      checks?: components["schemas"]["BehaviorCheckView"][];
      /** Check Counts */
      check_counts?: {
        [key: string]: number;
      };
      /**
       * Omitted Checks
       * @default 0
       */
      omitted_checks: number;
      /** Group Results */
      group_results?: {
        [key: string]: {
          [key: string]: number;
        };
      };
      /** Penalties */
      penalties?: string[];
      /** Remaining Unknowns */
      remaining_unknowns?: string[];
      /** Metrics */
      metrics?: {
        [key: string]: number | string | boolean;
      };
      scope?: components["schemas"]["SufficiencyResult"] | null;
      /** Demand Id */
      demand_id?: string | null;
      /** Expansion Reason */
      expansion_reason?: string | null;
      /** Receipt Refs */
      receipt_refs?: string[];
      historical_replay?: components["schemas"]["HistoricalReplayView"] | null;
    };
    /**
     * FunctionMapping
     * @description One interface rename; omitted argument/output names retain their names.
     */
    FunctionMapping: {
      /** Old Function */
      old_function: string;
      /** New Function */
      new_function: string;
      /** Arguments */
      arguments?: {
        [key: string]: string;
      };
      /** Output Fields */
      output_fields?: {
        [key: string]: string;
      };
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
     * HistoricalAgentEvidence
     * @description A previous observed outcome, never a fresh assessment of this candidate.
     */
    HistoricalAgentEvidence: {
      /** Episode Ref */
      episode_ref: string;
      /** Candidate Id */
      candidate_id: string;
      /** Agent Outcome */
      agent_outcome?: string | null;
      /**
       * Task Assessment
       * @default not_checked
       */
      task_assessment: string;
      /** Evidence Refs */
      evidence_refs?: string[];
    };
    /**
     * HistoricalReplayView
     * @description Recorded bank outcome, distinct from eligibility and task correctness.
     */
    HistoricalReplayView: {
      /**
       * Status
       * @enum {string}
       */
      status: "preserved" | "regressed" | "unable_to_check" | "interrupted";
      /** Allowed */
      allowed: boolean;
      /** Candidate Kernel Id */
      candidate_kernel_id?: string | null;
      /** Report Id */
      report_id?: string | null;
      /** Bank Id */
      bank_id?: string | null;
      /** Case Count */
      case_count: number;
      /** Cases */
      cases?: components["schemas"]["ReplayCaseView"][];
      /**
       * Omitted Cases
       * @default 0
       */
      omitted_cases: number;
      /** Feedback */
      feedback?: {
        [key: string]: unknown;
      }[];
      /** Model Calls */
      model_calls?: number | null;
      /** Live Mcp Calls */
      live_mcp_calls?: number | null;
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
    /**
     * InferenceContextView
     * @description Attribution and size of one exact model-facing discovery snapshot.
     */
    InferenceContextView: {
      /** Artifact Id */
      artifact_id?: string | null;
      /** Catalog Id */
      catalog_id: string;
      /** Kernel Id */
      kernel_id: string;
      /** Step */
      step?: number | null;
      /** View Ref */
      view_ref?: string | null;
      context: components["schemas"]["DiscoveryContextSummary"];
      /** Catalog Ref */
      catalog_ref?: string | null;
    };
    /**
     * InferenceDiscoveryView
     * @description Bounded navigation receipt; exact definitions remain in source artifacts.
     */
    InferenceDiscoveryView: {
      /** Artifact Id */
      artifact_id?: string | null;
      /** Catalog Id */
      catalog_id: string;
      /** Kernel Id */
      kernel_id: string;
      /** Step */
      step?: number | null;
      /** Tool */
      tool: string;
      /** Status */
      status: string;
      /**
       * Query
       * @default
       */
      query: string;
      /**
       * Kind
       * @default all
       */
      kind: string;
      /** Definition Id */
      definition_id?: string | null;
      /**
       * Pointer
       * @default
       */
      pointer: string;
      /**
       * Result Count
       * @default 0
       */
      result_count: number;
      /** Result Ids */
      result_ids?: string[];
      /**
       * Omitted Results
       * @default 0
       */
      omitted_results: number;
      /**
       * Total Count
       * @default 0
       */
      total_count: number;
      /**
       * Offset
       * @default 0
       */
      offset: number;
      /** Next Cursor */
      next_cursor?: string | null;
      /**
       * Has More
       * @default false
       */
      has_more: boolean;
      /**
       * Complete
       * @default true
       */
      complete: boolean;
      /** Dependencies */
      dependencies?: string[];
      /**
       * Dependency Count
       * @default 0
       */
      dependency_count: number;
      /**
       * Omitted Dependencies
       * @default 0
       */
      omitted_dependencies: number;
      /** Loaded Tool Name */
      loaded_tool_name?: string | null;
      /** Error */
      error?: string | null;
      /** Truncated Fields */
      truncated_fields?: string[];
      context?: components["schemas"]["DiscoveryContextSummary"] | null;
      /** State Ref */
      state_ref?: string | null;
      /** Result Ref */
      result_ref?: string | null;
      /** Catalog Ref */
      catalog_ref?: string | null;
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
      /** Acquisition Bindings */
      acquisition_bindings?: components["schemas"]["AcquisitionBinding"][];
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
       * @default demand-v2
       */
      extractor_version: string;
      /** Expansion Reason */
      expansion_reason?: string | null;
    };
    /**
     * MigrationSpec
     * @description One shared graph transformation, independent of tasks and expected answers.
     *
     *     Renames and identity remaps address original types and original properties.
     *     Explicit record projections replace all records of their source types and
     *     cannot overlap rename/remap rules for those types. Relations retain their
     *     order, multiplicity, and provenance. An explicitly contracted relation may
     *     disappear only when a keyed join maps both endpoints to the same record.
     */
    MigrationSpec: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Type Renames */
      type_renames?: {
        [key: string]: string;
      };
      /** Property Renames */
      property_renames?: {
        [key: string]: {
          [key: string]: string;
        };
      };
      /** Relation Renames */
      relation_renames?: {
        [key: string]: string;
      };
      /** Identity Remaps */
      identity_remaps?: {
        [key: string]: string[];
      };
      /** Records */
      records?: components["schemas"]["RecordProjection"][];
      /** Endpoint Types */
      endpoint_types?: {
        [key: string]: components["schemas"]["EndpointTypes"];
      };
      /** Derived Relations */
      derived_relations?: components["schemas"]["DerivedRelation"][];
      /** Contracted Relations */
      contracted_relations?: string[];
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
     * PropertySource
     * @description Copy a property from one declared source alias, retaining missingness.
     */
    PropertySource: {
      /** Source */
      source: string;
      /** Property */
      property: string;
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
     * RecordIdentity
     * @description Preserve one source ID or derive an ID from named target key properties.
     */
    RecordIdentity: {
      /** Source */
      source?: string | null;
      /** Keys */
      keys?: string[];
    };
    /**
     * RecordProjection
     * @description Replace source records with copied fields under one target type.
     *
     *     A single source requires no join. Multiple source types require one-to-one
     *     joins over equal nonempty key lists and an explicit ordering anchor. Every
     *     source row must match exactly once. Multiple projections of one source type
     *     form a split. All facts of replaced source records must remain represented
     *     across those projections; deliberate information deletion is unsupported.
     */
    RecordProjection: {
      /** Sources */
      sources: {
        [key: string]: string;
      };
      /** Join Keys */
      join_keys?: {
        [key: string]: string[];
      };
      /** Anchor */
      anchor?: string | null;
      /** Target Type */
      target_type: string;
      /** Properties */
      properties: {
        [key: string]: components["schemas"]["PropertySource"];
      };
      identity: components["schemas"]["RecordIdentity"];
    };
    /** RecordedCall */
    RecordedCall: {
      /** Capture Id */
      capture_id: string;
      /** Bindings */
      bindings?: components["schemas"]["ResultBinding"][];
    };
    /**
     * ReplayBank
     * @description Append-only case bank tied to an exact kernel and inherited bank.
     */
    ReplayBank: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Kernel Id */
      kernel_id: string;
      /** Parent Bank Id */
      parent_bank_id?: string | null;
      /** Previous Bank Id */
      previous_bank_id?: string | null;
      /** Case Ids */
      case_ids?: string[];
    };
    /** ReplayBankReport */
    ReplayBankReport: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Kernel Id */
      kernel_id: string;
      /** Bank Id */
      bank_id: string;
      /**
       * Status
       * @enum {string}
       */
      status: "preserved" | "regressed" | "unable_to_check" | "interrupted";
      /** Allowed */
      allowed: boolean;
      /** Case Count */
      case_count: number;
      /** Reports */
      reports?: components["schemas"]["ReplayReport"][];
      /** Report Refs */
      report_refs?: string[];
      /** Feedback */
      feedback?: {
        [key: string]: unknown;
      }[];
      /** Repair Context */
      repair_context?: {
        [key: string]: unknown;
      };
      /** Runtime Dependencies */
      runtime_dependencies?: {
        [key: string]: string;
      };
      /**
       * Model Calls
       * @default 0
       * @constant
       */
      model_calls: 0;
      /**
       * Live Mcp Calls
       * @default 0
       * @constant
       */
      live_mcp_calls: 0;
    };
    /**
     * ReplayCall
     * @description An actual invocation, optionally rebound through a stable behavior ID.
     */
    ReplayCall: {
      /** Function */
      function: string;
      /** Args */
      args?: {
        [key: string]: unknown;
      };
      /** Graph Ref */
      graph_ref?: string | null;
      /** Execution Ref */
      execution_ref?: string | null;
      /** Behavior Id */
      behavior_id?: string | null;
      /**
       * Input Graph Known
       * @default true
       */
      input_graph_known: boolean;
      /** Source Refs */
      source_refs?: string[];
    };
    /**
     * ReplayCase
     * @description Original computations and assessment, never rewritten for a new kernel.
     */
    ReplayCase: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Origin Kernel Id */
      origin_kernel_id: string;
      /** Run Id */
      run_id: string;
      /**
       * Question
       * @default
       */
      question: string;
      /**
       * Requirement Version
       * @default recorded_execution_v1
       */
      requirement_version: string;
      /**
       * Split
       * @default construction
       * @enum {string}
       */
      split: "construction" | "development";
      /**
       * Scope
       * @default component
       * @enum {string}
       */
      scope: "component" | "trajectory";
      /**
       * Assessment Category
       * @default execution_succeeded
       * @enum {string}
       */
      assessment_category:
        | "execution_succeeded"
        | "generated_consistency_check"
        | "independent_task_check";
      /** Assessment Refs */
      assessment_refs?: string[];
      /** Source Refs */
      source_refs?: string[];
      /** Calls */
      calls: components["schemas"]["RecordedCall"][];
      /** Comparison Id */
      comparison_id: string;
    };
    /**
     * ReplayCaseView
     * @description Bounded presentation of one immutable case's actual replay evidence.
     */
    ReplayCaseView: {
      /** Original Case Id */
      original_case_id: string;
      /** Origin Kernel Id */
      origin_kernel_id?: string | null;
      /** Candidate Kernel Id */
      candidate_kernel_id?: string | null;
      /** Adapter Path */
      adapter_path?: string[];
      /**
       * Status
       * @enum {string}
       */
      status: "preserved" | "regressed" | "unable_to_check" | "interrupted";
      /**
       * Scope
       * @enum {string}
       */
      scope: "component" | "trajectory" | "unknown";
      /** Assessment Category */
      assessment_category: string;
      /** Baseline Execution Id */
      baseline_execution_id?: string | null;
      /** Candidate Execution Id */
      candidate_execution_id?: string | null;
      /** Original Graph Ids */
      original_graph_ids?: string[];
      /** Migrated Graph Ids */
      migrated_graph_ids?: string[];
      /** First Difference */
      first_difference?: {
        [key: string]: unknown;
      } | null;
      /** Reason */
      reason?: string | null;
    };
    /**
     * ReplayReport
     * @description Attributable evidence for original observations on a terminal candidate.
     */
    ReplayReport: {
      /**
       * Version
       * @default 1
       * @constant
       */
      version: 1;
      /** Original Case Id */
      original_case_id: string;
      /** Origin Kernel Id */
      origin_kernel_id: string | null;
      /** Candidate Kernel Id */
      candidate_kernel_id: string;
      /**
       * Status
       * @enum {string}
       */
      status: "preserved" | "regressed" | "unable_to_check" | "interrupted";
      /**
       * Scope
       * @enum {string}
       */
      scope: "component" | "trajectory" | "unknown";
      /** Assessment Category */
      assessment_category: string;
      /** Adapter Path */
      adapter_path?: string[];
      /** Original Graph Ids */
      original_graph_ids?: string[];
      /** Migrated Graph Ids */
      migrated_graph_ids?: string[];
      /** Baseline Execution Id */
      baseline_execution_id?: string | null;
      /** Candidate Execution Id */
      candidate_execution_id?: string | null;
      first_difference?: components["schemas"]["FirstDifference"] | null;
      /** Runtime Dependencies */
      runtime_dependencies?: {
        [key: string]: string;
      };
      /**
       * Reason
       * @default
       */
      reason: string;
      /**
       * Model Calls
       * @default 0
       * @constant
       */
      model_calls: 0;
      /**
       * Live Mcp Calls
       * @default 0
       * @constant
       */
      live_mcp_calls: 0;
    };
    /**
     * ResultBinding
     * @description An explicit argument path fed by an earlier replayed call's result.
     */
    ResultBinding: {
      /** Argument Path */
      argument_path: (string | number)[];
      /** Prior Call */
      prior_call: number;
      /** Output Path */
      output_path?: (string | number)[];
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
       * Max Discovery Steps
       * @default 12
       */
      max_discovery_steps: number;
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
      /**
       * Role
       * @default value
       * @enum {string}
       */
      role: "value" | "identity" | "selector" | "context";
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
      /** Parameter Fields */
      parameter_fields?: {
        [key: string]: string;
      };
      /** Source Parameters */
      source_parameters?: string[];
      /**
       * Ordering
       * @default unordered
       * @enum {string}
       */
      ordering: "unordered" | "ordered";
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
        | "behavior"
        | "coverage"
        | "task"
        | "preservation"
        | "historical_replay";
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
      /** Behavior Evaluation */
      behavior_evaluation?: {
        [key: string]: components["schemas"]["JsonValue"];
      };
      /**
       * Known Regressions
       * @default 0
       */
      known_regressions: number;
      preservation?: components["schemas"]["PreservationCertificate"] | null;
      /** Historical Replay */
      historical_replay?: {
        [key: string]: components["schemas"]["JsonValue"];
      } | null;
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
