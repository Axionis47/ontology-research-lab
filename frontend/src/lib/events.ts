import { useEffect, useRef, useState } from "react";
import { id, request, type Event, type EventPage } from "./api";
import { cursorCompare } from "./utils";
export function useEvents(runId: string, live: boolean) {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [through, setThrough] = useState("0");
  const [connected, setConnected] = useState(false);
  const last = useRef("0");
  useEffect(() => {
    let disposed = false;
    let stream: EventSource | undefined;
    let retry: ReturnType<typeof setTimeout> | undefined;
    setEvents([]);
    setError(null);
    setLoading(!!runId);
    setThrough("0");
    last.current = "0";
    setConnected(false);
    if (!runId) return;
    function append(items: Event[]) {
      if (disposed) return;
      setEvents((current) => {
        const map = new Map(current.map((e) => [String(e.cursor), e]));
        for (const event of items) {
          map.set(String(event.cursor), event);
          if (cursorCompare(String(event.cursor), last.current) > 0)
            last.current = String(event.cursor);
        }
        return [...map.values()].sort((a, b) =>
          cursorCompare(String(a.cursor), String(b.cursor)),
        );
      });
    }
    async function history() {
      let after = "0";
      let upper: string | undefined;
      let more = true;
      while (more && !disposed) {
        const page = await request<EventPage>(
          `/runs/${id(runId)}/events?after=${after}${upper ? `&through=${upper}` : ""}&limit=250`,
        );
        upper = String(page.through);
        append(page.items);
        after = String(page.next_cursor);
        more = page.has_more;
        setThrough(upper);
      }
      setLoading(false);
    }
    function connect() {
      if (disposed || !live) return;
      stream = new EventSource(
        `/api/v1/runs/${id(runId)}/stream?after=${last.current}`,
      );
      stream.onopen = () => {
        if (!disposed) setConnected(true);
      };
      const receive = (message: MessageEvent) => {
        try {
          const event = JSON.parse(message.data) as Event;
          if (!event.cursor) return;
          append([event]);
          setThrough(String(event.cursor));
          setError(null);
        } catch {
          setError(
            new Error(
              "An event could not be read. Saved evidence remains available.",
            ),
          );
        }
      };
      stream.onmessage = receive;
      stream.addEventListener("oak.event", receive as EventListener);
      stream.addEventListener("event", receive as EventListener);
      stream.onerror = () => {
        setConnected(false);
        stream?.close();
        retry = setTimeout(connect, 1500);
      };
    }
    void history()
      .then(connect)
      .catch((e) => {
        if (!disposed) {
          setLoading(false);
          setError(e);
        }
      });
    return () => {
      disposed = true;
      stream?.close();
      if (retry) clearTimeout(retry);
    };
  }, [runId, live]);
  return { events, loading, error, through, connected };
}
