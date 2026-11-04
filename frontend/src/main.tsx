import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  BrowserRouter,
  NavLink,
  Navigate,
  Route,
  Routes,
  useLocation,
  useSearchParams,
} from "react-router-dom";
import {
  Cable,
  CircleHelp,
  GitBranch,
  Leaf,
  Radio,
  Settings2,
} from "lucide-react";
import { Setup } from "./screens/Setup";
import { Construction } from "./screens/Construction";
import { Inference } from "./screens/Inference";
import { id, useTasks, useWorkspace } from "./lib/api";
import { money } from "./lib/utils";
import { ErrorBox } from "./components/common";
import "@xyflow/react/dist/style.css";
import "./style.css";
const client = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
    mutations: { retry: false },
  },
});
function App() {
  const tasks = useTasks();
  const workspace = useWorkspace();
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const taskId =
    params.get("task") ??
    tasks.data?.items.find((task) => task.latest_kernel_id)?.id ??
    tasks.data?.items[0]?.id ??
    "";
  const suffix = taskId ? `?task=${id(taskId)}` : "";
  return (
    <div className="app">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside className="sidebar">
        <NavLink to="/setup" className="brand">
          <div className="brand-mark">
            <Leaf size={21} />
          </div>
          <span>
            OaK<span className="brand-caption">Observation workspace</span>
          </span>
        </NavLink>
        <div className="workspace-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          <NavLink to="/setup">
            <Settings2 size={17} />
            <span>Setup</span>
          </NavLink>
          <NavLink to={`/construction${suffix}`}>
            <GitBranch size={17} />
            <span>Construction</span>
          </NavLink>
          <NavLink to={`/inference${suffix}`}>
            <Radio size={17} />
            <span>Inference</span>
          </NavLink>
        </nav>
        <div className="sidebar-note">
          <CircleHelp size={16} />
          <p>
            See what happened.
            <br />
            Follow the evidence.
          </p>
        </div>
        <div className="local-indicator">
          <span />
          Local workspace
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="task-switcher">
            <Cable size={16} />
            <label htmlFor="task-select">Task</label>
            <select
              id="task-select"
              value={taskId}
              onChange={(e) => setParams({ task: e.target.value })}
            >
              {tasks.data?.items.length ? (
                tasks.data.items.map((task) => (
                  <option value={task.id} key={task.id}>
                    {task.name}
                    {task.legacy ? " · historical" : ""}
                  </option>
                ))
              ) : (
                <option value="">No tasks configured</option>
              )}
            </select>
          </div>
          <div className="topbar-budget">
            {workspace.data && (
              <>
                <span className="status-dot" />
                <span>
                  {money(workspace.data.budget.remaining_usd)} available
                </span>
                <span className="muted">
                  of {money(workspace.data.budget.limit_usd)}
                </span>
              </>
            )}
          </div>
        </header>
        <main id="main" key={location.pathname}>
          {tasks.error && <ErrorBox error={tasks.error} />}
          <Routes>
            <Route path="/setup" element={<Setup />} />
            <Route
              path="/construction"
              element={<Construction taskId={taskId} />}
            />
            <Route path="/inference" element={<Inference taskId={taskId} />} />
            <Route
              path="*"
              element={
                <Navigate
                  to={
                    tasks.data?.items.length
                      ? `/construction${suffix}`
                      : "/setup"
                  }
                  replace
                />
              }
            />
          </Routes>
        </main>
        <footer className="app-footer">
          <span>OaK · Schema, knowledge, functions</span>
          <span>API v1 · Evidence stays local</span>
        </footer>
      </div>
    </div>
  );
}
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
