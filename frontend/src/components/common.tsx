import { AlertCircle, LoaderCircle, SearchX } from "lucide-react";
import type { ReactNode } from "react";
import { label, display } from "../lib/utils";
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}
export function Status({
  value,
  kind = "lifecycle",
}: {
  value?: string | null;
  kind?: "lifecycle" | "assessment" | "outcome";
}) {
  const normalized = value?.toLowerCase() ?? "";
  const captions: Record<string, string> = {
    unchecked: "Not checked",
    unmeasured: "Not checked",
    unscored: "Unable to check",
    unable_to_check: "Unable to check",
    not_checked: "Not checked",
    clarify: "Needs input",
    needs_input: "Needs input",
  };
  const text =
    captions[normalized] ??
    (normalized
      ? label(normalized)
      : kind === "assessment"
        ? "Not checked"
        : "Not recorded");
  const tone =
    kind === "assessment" && normalized === "passed"
      ? "success"
      : ["failed", "error", "interrupted"].includes(normalized)
        ? "danger"
        : ["running", "queued"].includes(normalized)
          ? "active"
          : normalized === "unresolved"
            ? "warning"
            : "neutral";
  return <Badge tone={tone}>{text}</Badge>;
}
export function Loading({
  text = "Loading recorded evidence",
}: {
  text?: string;
}) {
  return (
    <div className="empty">
      <LoaderCircle className="spin" size={22} />
      <p>{text}</p>
    </div>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <SearchX size={26} />
      <h3>{title}</h3>
      {children && <p>{children}</p>}
    </div>
  );
}
export function ErrorBox({ error }: { error: unknown }) {
  return (
    <div className="error-box" role="alert">
      <AlertCircle size={18} />
      <div>{error instanceof Error ? error.message : String(error)}</div>
    </div>
  );
}
export function Json({ value }: { value: unknown }) {
  return <pre className="json">{display(value)}</pre>;
}
export function Properties({ value }: { value: Record<string, unknown> }) {
  return (
    <dl className="properties">
      {Object.entries(value).map(([key, val]) => (
        <div key={key}>
          <dt>{label(key)}</dt>
          <dd>
            {typeof val === "object" ? <Json value={val} /> : display(val)}
          </dd>
        </div>
      ))}
    </dl>
  );
}
export function Limitations({ items }: { items?: string[] }) {
  return items?.length ? (
    <details className="limitations">
      <summary>Evidence notes ({items.length})</summary>
      <ul>
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </details>
  ) : null;
}
