import {
  Braces,
  CheckCheck,
  Circle,
  Eye,
  FileText,
  GitBranch,
  Layers,
  Play,
  RotateCcw,
  Pause,
  ChevronRight,
} from "lucide-react";
import type { Event } from "../lib/api";
import { useEffect, useRef } from "react";
import { label, object, array, display } from "../lib/utils";
import { Badge, Empty, Json } from "./common";
import { Button } from "./ui/button";
import type { Inspection } from "./EvidenceDrawer";
const icons: Record<string, typeof Circle> = {
  "run.lifecycle": Circle,
  "stage.status": Layers,
  "decision.recorded": GitBranch,
  "observation.recorded": Eye,
  "graph.snapshot": Braces,
  "kernel.candidate": Layers,
  "validation.recorded": CheckCheck,
  "assessment.recorded": CheckCheck,
  "usage.recorded": Circle,
  "evidence.recorded": FileText,
};
export function Playback({
  count,
  index,
  playing,
  onPlay,
  onReset,
  onSelect,
  mode,
  live,
  onLive,
}: {
  count: number;
  index: number;
  playing: boolean;
  onPlay: () => void;
  onReset: () => void;
  onSelect: (i: number) => void;
  mode: string;
  live: boolean;
  onLive?: () => void;
}) {
  return (
    <div className="playback">
      <div className="inline">
        <Button variant="outline" size="sm" onClick={onPlay} disabled={!count}>
          {playing ? <Pause size={14} /> : <Play size={14} />}Replay
        </Button>
        <Button variant="ghost" size="sm" onClick={onReset} disabled={!count}>
          <RotateCcw size={14} />
          Reset
        </Button>
        {live && onLive && (
          <Button size="sm" variant="ghost" onClick={onLive}>
            Follow live
          </Button>
        )}
        <span
          className="playback-mode"
          title="Viewer pace: one saved event every 1.1 seconds. This is not recorded execution timing."
        >
          {mode} · viewer pace
        </span>
      </div>
      <label className="playhead">
        <span>
          Step {count ? index + 1 : 0} of {count}
        </span>
        <input
          aria-label="Replay step"
          type="range"
          min={0}
          max={Math.max(0, count - 1)}
          value={Math.max(0, index)}
          disabled={!count}
          onChange={(e) => onSelect(Number(e.target.value))}
        />
      </label>
    </div>
  );
}
export function Trajectory({
  events,
  index,
  onSelect,
  onInspect,
  autoScroll = false,
}: {
  events: Event[];
  index: number;
  onSelect: (index: number) => void;
  onInspect: (selection: Inspection) => void;
  autoScroll?: boolean;
}) {
  const list = useRef<HTMLOListElement>(null);
  useEffect(() => {
    if (!autoScroll) return;
    const selected =
      list.current?.querySelector<HTMLElement>(".event-selected");
    const panel = list.current?.closest<HTMLElement>(".split-left");
    if (selected && panel) {
      const box = selected.getBoundingClientRect(),
        bounds = panel.getBoundingClientRect();
      if (box.bottom > bounds.bottom || box.top < bounds.top)
        panel.scrollTop += box.top - bounds.top - 155;
    }
  }, [index, autoScroll]);
  if (!events.length)
    return (
      <Empty title="No steps recorded">
        Execution evidence will appear here when it is persisted.
      </Empty>
    );
  return (
    <ol className="trajectory" ref={list}>
      {events.map((event, i) => {
        const Icon = icons[event.type] ?? FileText;
        const detail = object(event.payload);
        const operatorSteps = array(
          detail.operator_steps ?? object(detail.detail).steps ?? detail.steps,
        );
        return (
          <li
            key={event.cursor}
            data-event-cursor={event.cursor}
            className={`event ${i === index ? "event-selected" : ""} ${i > index ? "event-future" : ""}`}
          >
            <button
              className="event-select"
              aria-current={i === index ? "step" : undefined}
              onClick={() => onSelect(i)}
            >
              <span className="event-icon">
                <Icon size={16} />
              </span>
              <span className="event-copy">
                <span className="event-stage">
                  {event.stage
                    ? label(event.stage)
                    : label(event.type.split(".")[0])}
                  <span className="event-index">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                </span>
                <strong>{event.summary}</strong>
                <span className="event-type">
                  {event.type}
                  {event.parent_run_id ? " · Episode" : ""}
                </span>
              </span>
              <ChevronRight className="event-chevron" size={16} />
            </button>
            <div className="event-details">
              {operatorSteps.length > 0 && (
                <details>
                  <summary>{operatorSteps.length} recorded operators</summary>
                  {operatorSteps.map((step, j) => (
                    <div className="operator" key={j}>
                      <Badge>
                        {String(
                          step.op ??
                            step.operator ??
                            step.name ??
                            `Operator ${j + 1}`,
                        )}
                      </Badge>
                      <Json value={step} />
                    </div>
                  ))}
                </details>
              )}
              <details>
                <summary>Recorded details</summary>
                <Json value={detail} />
              </details>
              {(event.artifact_refs ?? []).length > 0 && (
                <div className="evidence-links">
                  {(event.artifact_refs ?? []).map((ref) => (
                    <button
                      key={`${ref.id}:${ref.role}`}
                      onClick={() =>
                        onInspect({
                          title: label(ref.role),
                          artifactId: ref.id,
                        })
                      }
                    >
                      <FileText size={12} />
                      {label(ref.role)}
                    </button>
                  ))}
                </div>
              )}
              {!icons[event.type] && (
                <span className="muted small">
                  Additional evidence category: {display(event.type)}
                </span>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
