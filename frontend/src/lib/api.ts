import { useQuery } from "@tanstack/react-query";
import { useRef } from "react";
import type { components } from "../api.generated";
type Models = components["schemas"];
export type Task = Models["TaskResponse"];
export type TaskSummary = Models["TaskSummary"];
export type Run = Models["RunResponse"];
export type History = Models["HistoryResponse"];
export type Event = Models["EventEnvelope"];
export type EventPage = Models["EventsResponse"];
export type Kernel = Models["KernelResponse"];
export type Graph = Models["GraphResponse"];
export type Artifact = Models["ArtifactResponse"];
export type Workspace = Models["WorkspaceResponse"];
export class ApiError extends Error {
  constructor(
    message: string,
    public code: string,
    public retryable: boolean,
  ) {
    super(message);
  }
}
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    credentials: "same-origin",
    ...init,
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ message: `Request failed (${response.status})` }));
    const body = error.error ?? error;
    throw new ApiError(
      body.message ?? body.detail ?? "Request failed",
      body.code ?? "request_failed",
      Boolean(body.retryable),
    );
  }
  return response.json();
}
export async function mutate<T>(
  path: string,
  body: unknown,
  session: string,
  key = crypto.randomUUID(),
): Promise<T> {
  return request(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Oak-Session": session,
      "Idempotency-Key": key,
    },
    body: JSON.stringify(body),
  });
}
export const id = encodeURIComponent;
/** Keep retries for the same request attached to one accepted operation. */
export function useSubmissionKey() {
  const current = useRef({ body: "", key: crypto.randomUUID() });
  return {
    forBody(body: unknown) {
      const serialized = JSON.stringify(body);
      if (serialized !== current.current.body)
        current.current = { body: serialized, key: crypto.randomUUID() };
      return current.current.key;
    },
    clear() {
      current.current = { body: "", key: crypto.randomUUID() };
    },
  };
}
export function useWorkspace() {
  return useQuery({
    queryKey: ["workspace"],
    queryFn: () => request<Workspace>("/workspace"),
    refetchInterval: 15000,
  });
}
export function useTasks() {
  return useQuery({
    queryKey: ["tasks"],
    queryFn: () => request<Models["TaskListResponse"]>("/tasks"),
    refetchInterval: 15000,
  });
}
export function useTask(taskId: string) {
  return useQuery({
    queryKey: ["task", taskId],
    queryFn: () => request<Task>(`/tasks/${id(taskId)}`),
    enabled: !!taskId,
  });
}
export function useHistory(taskId: string) {
  return useQuery({
    queryKey: ["history", taskId],
    queryFn: () => request<History>(`/tasks/${id(taskId)}/history`),
    enabled: !!taskId,
    refetchInterval: 5000,
  });
}
export function useRun(runId: string) {
  return useQuery({
    queryKey: ["run", runId],
    queryFn: () => request<Run>(`/runs/${id(runId)}`),
    enabled: !!runId,
    refetchInterval: (query) =>
      ["running", "queued"].includes(query.state.data?.status ?? "")
        ? 2000
        : false,
  });
}
export function useKernel(kernelId?: string | null) {
  return useQuery({
    queryKey: ["kernel", kernelId],
    queryFn: () => request<Kernel>(`/kernels/${id(kernelId!)}`),
    enabled: !!kernelId,
    // Definitions are immutable, but later checks add evidence references.
    staleTime: 5000,
    refetchInterval: 10000,
  });
}
export function useGraph(graphId?: string | null, focus?: string) {
  return useQuery({
    queryKey: ["graph", graphId, focus],
    queryFn: () =>
      request<Graph>(
        `/graphs/${id(graphId!)}${focus ? `?focus=${id(focus)}` : ""}`,
      ),
    enabled: !!graphId,
    staleTime: Infinity,
  });
}
