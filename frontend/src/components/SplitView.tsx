import { useRef, useState, type ReactNode } from "react";
import { GripVertical } from "lucide-react";
export function SplitView({
  left,
  right,
}: {
  left: ReactNode;
  right: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(39);
  function resize(clientX: number) {
    const bounds = ref.current?.getBoundingClientRect();
    if (bounds)
      setWidth(
        Math.max(
          27,
          Math.min(65, (100 * (clientX - bounds.left)) / bounds.width),
        ),
      );
  }
  return (
    <div
      className="split-view"
      ref={ref}
      style={{ "--split": `${width}%` } as React.CSSProperties}
    >
      <section className="split-left">{left}</section>
      <div
        role="separator"
        aria-label="Resize evidence panels"
        aria-orientation="vertical"
        aria-valuenow={Math.round(width)}
        aria-valuemin={27}
        aria-valuemax={65}
        tabIndex={0}
        className="split-handle"
        onKeyDown={(e) => {
          if (e.key === "ArrowLeft") setWidth((v) => Math.max(27, v - 3));
          if (e.key === "ArrowRight") setWidth((v) => Math.min(65, v + 3));
        }}
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => {
          if (e.currentTarget.hasPointerCapture(e.pointerId)) resize(e.clientX);
        }}
        onPointerUp={(e) => e.currentTarget.releasePointerCapture(e.pointerId)}
      >
        <GripVertical size={14} />
      </div>
      <section className="split-right">{right}</section>
    </div>
  );
}
