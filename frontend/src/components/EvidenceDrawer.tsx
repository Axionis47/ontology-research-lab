import { useQuery } from "@tanstack/react-query";
import { request, id, type Artifact } from "../lib/api";
import { Sheet } from "./ui/sheet";
import {
  Badge,
  ErrorBox,
  Json,
  Limitations,
  Loading,
  Properties,
} from "./common";
import { array, short } from "../lib/utils";
export type Inspection = {
  title: string;
  data?: Record<string, unknown>;
  artifactId?: string;
};
export function EvidenceDrawer({
  selection,
  onClose,
}: {
  selection: Inspection | null;
  onClose: () => void;
}) {
  const artifact = useQuery({
    queryKey: ["artifact", selection?.artifactId],
    queryFn: () =>
      request<Artifact>(`/artifacts/${id(selection!.artifactId!)}`),
    enabled: !!selection?.artifactId,
    staleTime: Infinity,
  });
  return (
    <Sheet
      title={selection?.title ?? "Details"}
      description="Recorded properties, source references, and evidence"
      open={!!selection}
      onClose={onClose}
    >
      {selection?.artifactId ? (
        <>
          {artifact.isLoading ? (
            <Loading />
          ) : artifact.error ? (
            <ErrorBox error={artifact.error} />
          ) : (
            artifact.data && (
              <>
                <div className="inline">
                  <Badge>{artifact.data.kind}</Badge>
                  {artifact.data.redacted && (
                    <Badge tone="warning">Sanitized presentation</Badge>
                  )}
                </div>
                <p className="muted small">
                  Stored artifact <code>{short(artifact.data.id)}</code>
                </p>
                <Properties
                  value={{
                    stored_artifact_sha256: artifact.data.source_sha256,
                    presentation_sha256: artifact.data.projection_sha256,
                  }}
                />
                {artifact.data.provenance && (
                  <section className="provenance-panel">
                    <h3>Export provenance</h3>
                    <Badge
                      tone={
                        array(artifact.data.provenance.origins).some(
                          (origin) => origin.relationship !== "unchanged",
                        )
                          ? "warning"
                          : "neutral"
                      }
                    >
                      {array(artifact.data.provenance.origins).some(
                        (origin) => origin.relationship !== "unchanged",
                      )
                        ? "Sanitized derivative"
                        : "Unchanged source bytes"}
                    </Badge>
                    <p className="hint">
                      Source hashes below are declared by the export manifest.
                      Verification is identified for each source.
                    </p>
                    <Properties value={artifact.data.provenance} />
                  </section>
                )}
                <Limitations items={artifact.data.limitations} />
                <Json value={artifact.data.data} />
              </>
            )
          )}
        </>
      ) : (
        selection?.data && <Properties value={selection.data} />
      )}
    </Sheet>
  );
}
