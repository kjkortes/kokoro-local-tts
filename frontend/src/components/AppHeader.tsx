import type {StatusResponse} from "../types";


export function AppHeader({status, page = "studio"}: {status: StatusResponse | null; page?: "studio" | "voices"}) {
  const label = status?.state === "ready"
    ? "Model ready"
    : status?.state === "loading"
      ? "Loading model"
      : status?.state === "error"
        ? "Needs attention"
        : "Model on demand";
  return (
    <header className="app-header">
      <a className="wordmark" href="#workspace" aria-label="Kokoro local voice studio">
        <span className="wordmark-mark" aria-hidden="true">K</span>
        <span>Kokoro <i>/ local</i></span>
      </a>
      <nav className="app-navigation" aria-label="Main navigation">
        <a href="#workspace" aria-current={page === "studio" ? "page" : undefined}>Studio</a>
        <a href="#voices" aria-current={page === "voices" ? "page" : undefined}>Voices</a>
      </nav>
      <div className={`model-status status-${status?.state ?? "unloaded"}`}>
        <span className="status-dot" aria-hidden="true" />
        <span>{label}</span>
        <span className="status-device">{status?.device?.toUpperCase() ?? "CPU"}</span>
      </div>
    </header>
  );
}

