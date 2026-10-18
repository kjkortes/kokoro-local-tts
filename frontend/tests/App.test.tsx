import {act, fireEvent, render, screen, waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {App} from "../src/App";
import type {AppConfig} from "../src/types";


const config: AppConfig = {
  languages: [
    {code: "a", name: "American English", locale: "en-US"},
    {code: "b", name: "British English", locale: "en-GB"},
  ],
  voices: [
    {id: "af_heart", name: "Heart", language: "a", gender: "female"},
    {id: "af_bella", name: "Bella", language: "a", gender: "female"},
    {id: "am_adam", name: "Adam", language: "a", gender: "male"},
    {id: "bf_emma", name: "Emma", language: "b", gender: "female"},
    {id: "bm_george", name: "George", language: "b", gender: "male"},
  ],
  presets: [
    {id: "neutral", name: "Neutral", description: "Natural timing.", speed: 1, pitch: 0, tempo: 1, pause_scale: 1},
    {id: "calm", name: "Calm", description: "Measured and spacious.", speed: .9, pitch: -.7, tempo: .94, pause_scale: 1.25},
  ],
  formats: ["wav", "mp3", "flac", "ogg"],
  defaults: {
    engine: "kokoro",
    fish_voice: "b0204e37cbc94a16954c78697b844af2",
    language: "a",
    voice: "af_heart",
    preset: "neutral",
    format: "wav",
  },
  limits: {
    speed: {min: .5, max: 2}, pitch: {min: -4, max: 4}, tempo: {min: .75, max: 1.25},
    pause_scale: {min: .5, max: 2}, volume: {min: 0, max: 1.5},
    pause_ms: {min: 0, max: 5000},
  },
};

function stubApi(appConfig: AppConfig = config) {
  const calls: Array<{url: string; init?: RequestInit}> = [];
  vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    calls.push({url, init});
    if (url.endsWith("/api/config")) return Response.json(appConfig);
    if (url.endsWith("/api/status")) return Response.json({state: "ready", device: "cpu", version: "0.1.0", detail: null});
    if (url.startsWith("/api/fish-voices/page")) return Response.json({
      items: [{id: "saved-two", name: "Documentary narrator", description: "Warm documentary delivery", reference_id: "saved-documentary-ref"}],
      total: 1, page: 1, page_size: 10,
    });
    if (url.endsWith("/api/fish-voices")) return Response.json([
      {id: "original", name: "Original Fish voice", description: "", reference_id: "b0204e37cbc94a16954c78697b844af2"},
      {id: "saved-two", name: "Documentary narrator", description: "Warm documentary delivery", reference_id: "saved-documentary-ref"},
    ]);
    return Response.json({
      id: "one", state: "complete", phase: "Audio ready", progress: 1, error: null,
      audio_url: "/api/jobs/one/audio", download_url: "/api/jobs/one/download",
      filename: "script.wav", duration: 1,
      segments: [{text: "A calm local voice.", start: 0, end: 1}],
      transcript: "A calm local voice.",
    }, {status: init?.method === "POST" ? 202 : 200});
  }));
  return calls;
}

it("filters voices by language and gender", async () => {
  stubApi();
  const user = userEvent.setup();
  render(<App />);
  await screen.findByLabelText("Language");
  await user.selectOptions(screen.getByLabelText("Language"), "b");
  await user.selectOptions(screen.getByLabelText("Gender"), "female");
  expect(screen.getByLabelText("Primary voice")).toHaveValue("bf_emma");
  expect(screen.queryByRole("option", {name: "George"})).not.toBeInTheDocument();
});

it("plays the bundled preview for the selected primary voice", async () => {
  const calls = stubApi();
  const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
  const user = userEvent.setup();
  render(<App />);

  await screen.findByLabelText("Primary voice");
  await user.click(screen.getByRole("button", {name: "Preview Heart voice"}));

  expect(screen.getByLabelText("Voice preview")).toHaveAttribute(
    "src",
    "/voice-samples/af_heart.mp3",
  );
  expect(screen.getByRole("button", {name: "Stop Heart preview"})).toBeVisible();
  expect(play).toHaveBeenCalledOnce();
  expect(calls.some(({init}) => init?.method === "POST")).toBe(false);
});

it("starts preview playback directly from the button activation", async () => {
  stubApi();
  let buttonLabelWhenPlaybackStarted = "";
  vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(() => {
    buttonLabelWhenPlaybackStarted = screen.getByRole("button", {name: /Heart/}).getAttribute("aria-label") ?? "";
    return Promise.resolve();
  });
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
  const user = userEvent.setup();
  render(<App />);

  await screen.findByLabelText("Primary voice");
  await user.click(screen.getByRole("button", {name: "Preview Heart voice"}));

  expect(buttonLabelWhenPlaybackStarted).toBe("Preview Heart voice");
});

it("previews the selected second voice when blending", async () => {
  stubApi();
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
  const user = userEvent.setup();
  render(<App />);

  await screen.findByLabelText("Primary voice");
  await user.click(screen.getByRole("checkbox", {name: /Blend a second voice/}));
  await user.click(screen.getByRole("button", {name: "Preview Bella voice"}));

  expect(screen.getByLabelText("Voice preview")).toHaveAttribute(
    "src",
    "/voice-samples/af_bella.mp3",
  );
  expect(screen.getByRole("button", {name: "Stop Bella preview"})).toBeVisible();
});

it("stops a preview when its selected voice changes", async () => {
  stubApi();
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
  const user = userEvent.setup();
  render(<App />);

  await screen.findByLabelText("Primary voice");
  await user.click(screen.getByRole("button", {name: "Preview Heart voice"}));
  await user.selectOptions(screen.getByLabelText("Primary voice"), "am_adam");

  expect(screen.getByLabelText("Voice preview")).not.toHaveAttribute("src");
  expect(screen.getByRole("button", {name: "Preview Adam voice"})).toBeVisible();
});

it("reports an unavailable voice preview and resets its control", async () => {
  stubApi();
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
  const user = userEvent.setup();
  render(<App />);

  await screen.findByLabelText("Primary voice");
  await user.click(screen.getByRole("button", {name: "Preview Heart voice"}));
  fireEvent.error(screen.getByLabelText("Voice preview"));

  expect(screen.getByRole("alert")).toHaveTextContent("Heart preview could not be played.");
  expect(screen.getByRole("button", {name: "Preview Heart voice"})).toBeVisible();
});

it("clears a preview error when the selected voice changes", async () => {
  stubApi();
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
  const user = userEvent.setup();
  render(<App />);

  await screen.findByLabelText("Primary voice");
  await user.click(screen.getByRole("button", {name: "Preview Heart voice"}));
  fireEvent.error(screen.getByLabelText("Voice preview"));
  await user.selectOptions(screen.getByLabelText("Primary voice"), "am_adam");

  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("ignores a stale playback rejection after another preview starts", async () => {
  stubApi();
  let rejectFirstPlay!: (reason: Error) => void;
  const firstPlay = new Promise<void>((_, reject) => { rejectFirstPlay = reject; });
  vi.spyOn(HTMLMediaElement.prototype, "play")
    .mockReturnValueOnce(firstPlay)
    .mockResolvedValue(undefined);
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
  const user = userEvent.setup();
  render(<App />);

  await screen.findByLabelText("Primary voice");
  await user.click(screen.getByRole("checkbox", {name: /Blend a second voice/}));
  await user.click(screen.getByRole("button", {name: "Preview Heart voice"}));
  await user.click(screen.getByRole("button", {name: "Preview Bella voice"}));
  await act(async () => rejectFirstPlay(new Error("The first playback was interrupted.")));

  expect(screen.getByRole("button", {name: "Stop Bella preview"})).toBeVisible();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("applies a preset and submits the visible delivery values", async () => {
  const calls = stubApi();
  const user = userEvent.setup();
  render(<App />);
  await screen.findByLabelText("Script");
  await user.type(screen.getByLabelText("Script"), "A calm local voice.");
  await user.click(screen.getByRole("button", {name: "Calm"}));
  expect(screen.getByText("Measured and spacious.")).toBeVisible();
  await user.click(screen.getByRole("button", {name: "Generate speech"}));
  await waitFor(() => expect(calls.some(({init}) => init?.method === "POST")).toBe(true));
  const body = JSON.parse(String(calls.find(({init}) => init?.method === "POST")?.init?.body));
  expect(body.preset).toBe("calm");
  expect(body.expression.speed).toBe(.9);
});

it("submits an exact pause duration entered in milliseconds", async () => {
  const calls = stubApi();
  const user = userEvent.setup();
  render(<App />);
  await screen.findByLabelText("Script");
  await user.type(screen.getByLabelText("Script"), "One. Two.");
  await user.click(screen.getByText("Fine-tune delivery"));
  await user.type(screen.getByLabelText("Pause duration (ms)"), "750");
  await user.click(screen.getByRole("button", {name: "Generate speech"}));
  await waitFor(() => expect(calls.some(({init}) => init?.method === "POST")).toBe(true));

  const body = JSON.parse(String(calls.find(({init}) => init?.method === "POST")?.init?.body));
  expect(body.pause_ms).toBe(750);
});

it("does not expose a row pause override for continuously synthesized storyboards", async () => {
  const calls = stubApi();
  const user = userEvent.setup();
  render(<App />);
  await screen.findByLabelText("Script");
  await user.click(screen.getByRole("button", {name: "Upload storyboard"}));
  await user.type(screen.getByLabelText("Paste Markdown storyboard"), `
| Beat | VO script |
| --- | --- |
| 1 | First clause, |
| 2 | continuing naturally. |
`);
  await user.click(screen.getByRole("button", {name: "Use pasted table"}));
  await user.selectOptions(screen.getByLabelText("Speech column"), "1");
  await user.click(screen.getByText("Fine-tune delivery"));
  expect(screen.queryByLabelText("Comma continuation (ms)")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", {name: "Generate speech"}));
  await waitFor(() => expect(calls.some(({init}) => init?.method === "POST")).toBe(true));

  const body = JSON.parse(String(calls.find(({init}) => init?.method === "POST")?.init?.body));
  expect(body).not.toHaveProperty("comma_pause_ms");
});

it("shows script statistics and disables generation for blank text", async () => {
  stubApi();
  const user = userEvent.setup();
  render(<App />);
  const editor = await screen.findByLabelText("Script");
  expect(screen.getByRole("button", {name: "Generate speech"})).toBeDisabled();
  await user.type(editor, "Three simple words");
  expect(screen.getByText("3 words")).toBeVisible();
  expect(screen.getByRole("button", {name: "Generate speech"})).toBeEnabled();
});

it("uploads a Markdown storyboard and submits the selected column as read-only row segments", async () => {
  const calls = stubApi();
  const user = userEvent.setup();
  render(<App />);
  await screen.findByLabelText("Script");

  await user.click(screen.getByRole("button", {name: "Upload storyboard"}));
  const storyboard = new File([`
| Beat | Original VO | Visual cue |
| --- | --- | --- |
| 1 | First row, exactly. | A kitchen. |
| 2 | Second row? Yes! | A garden. |
`], "storyboard.md", {type: "text/markdown"});
  await user.upload(screen.getByLabelText("Markdown storyboard"), storyboard);
  await user.selectOptions(await screen.findByLabelText("Speech column"), "1");

  expect(screen.getByText("First row, exactly.")).toBeVisible();
  expect(screen.getByText("Second row? Yes!")).toBeVisible();
  expect(screen.queryByRole("textbox", {name: "Script"})).not.toBeInTheDocument();
  expect(screen.getByText("2 segments")).toBeVisible();

  await user.click(screen.getByRole("button", {name: "Generate speech"}));
  await waitFor(() => expect(calls.some(({init}) => init?.method === "POST")).toBe(true));
  const body = JSON.parse(String(calls.find(({init}) => init?.method === "POST")?.init?.body));
  expect(body.text).toBe("First row, exactly.\n\nSecond row? Yes!");
  expect(body.segments).toEqual(["First row, exactly.", "Second row? Yes!"]);
});

it("pastes a Markdown storyboard and submits the selected column as row segments", async () => {
  const calls = stubApi();
  const user = userEvent.setup();
  render(<App />);
  await screen.findByLabelText("Script");

  await user.click(screen.getByRole("button", {name: "Upload storyboard"}));
  await user.type(screen.getByLabelText("Paste Markdown storyboard"), `
| Beat | VO script | Visual cue |
| --- | --- | --- |
| 1 | Pasted first row. | A kitchen. |
| 2 | Pasted second row! | A garden. |
`);
  await user.click(screen.getByRole("button", {name: "Use pasted table"}));
  await user.selectOptions(screen.getByLabelText("Speech column"), "1");

  expect(screen.getByText("Pasted first row.")).toBeVisible();
  expect(screen.getByText("Pasted second row!")).toBeVisible();
  expect(screen.getByText("2 segments")).toBeVisible();

  await user.click(screen.getByRole("button", {name: "Generate speech"}));
  await waitFor(() => expect(calls.some(({init}) => init?.method === "POST")).toBe(true));
  const body = JSON.parse(String(calls.find(({init}) => init?.method === "POST")?.init?.body));
  expect(body.segments).toEqual(["Pasted first row.", "Pasted second row!"]);
});

it("uses the configured Fish engine and voice defaults and submits them", async () => {
  const calls = stubApi({
    ...config,
    defaults: {...config.defaults, engine: "fish_audio"},
  });
  const user = userEvent.setup();
  render(<App />);
  await screen.findByLabelText("Script");

  expect(screen.getByRole("radio", {name: "Fish Audio S2.1 Pro Free — OpenRouter"})).toBeChecked();
  expect(screen.queryByLabelText("Primary voice")).not.toBeInTheDocument();
  expect(screen.queryByRole("group", {name: "Audio format"})).not.toBeInTheDocument();
  expect(screen.getByText("MP3", {selector: "strong"})).toBeVisible();
  await screen.findByRole("option", {name: "Original Fish voice"});
  expect(screen.getByLabelText("Fish voice")).toHaveValue("original");

  await user.selectOptions(screen.getByLabelText("Delivery Style"), "documentary");
  await user.type(screen.getByLabelText("OpenRouter API Key"), "ui-secret-key");
  await user.type(screen.getByLabelText("Script"), "A remote narration.");
  await user.click(screen.getByRole("button", {name: "Generate speech"}));
  await waitFor(() => expect(calls.some(({init}) => init?.method === "POST")).toBe(true));

  const body = JSON.parse(String(calls.find(({init}) => init?.method === "POST")?.init?.body));
  expect(body).toMatchObject({
    engine: "fish_audio",
    text: "A remote narration.",
    fish_voice: "b0204e37cbc94a16954c78697b844af2",
    fish_style: "documentary",
    openrouter_api_key: "ui-secret-key",
    output_format: "mp3",
  });
  expect(body).not.toHaveProperty("primary_voice");
  expect(screen.getByLabelText("OpenRouter API Key")).toHaveAttribute("type", "password");
});

it("submits the selected saved reference and omits it for provider default", async () => {
  const calls = stubApi({...config, defaults: {...config.defaults, engine: "fish_audio"}});
  const user = userEvent.setup();
  render(<App />);
  await screen.findByRole("option", {name: "Documentary narrator"});
  await user.selectOptions(screen.getByLabelText("Fish voice"), "saved-two");
  await user.click(screen.getByRole("radio", {name: "Kokoro Local"}));
  await user.click(screen.getByRole("radio", {name: "Fish Audio S2.1 Pro Free — OpenRouter"}));
  await screen.findByRole("option", {name: "Documentary narrator"});
  expect(screen.getByLabelText("Fish voice")).toHaveValue("saved-two");
  fireEvent.change(screen.getByLabelText("Script"), {target: {value: "A saved voice narration."}});
  await user.click(screen.getByRole("button", {name: "Generate speech"}));
  await waitFor(() => expect(calls.filter(({url, init}) => url === "/api/jobs" && init?.method === "POST")).toHaveLength(1));
  let submitted = calls.filter(({url, init}) => url === "/api/jobs" && init?.method === "POST");
  expect(JSON.parse(String(submitted[0].init?.body)).fish_voice).toBe("saved-documentary-ref");

  await user.selectOptions(screen.getByLabelText("Fish voice"), "provider");
  await user.click(screen.getByRole("button", {name: "Generate speech"}));
  await waitFor(() => expect(calls.filter(({url, init}) => url === "/api/jobs" && init?.method === "POST")).toHaveLength(2));
  submitted = calls.filter(({url, init}) => url === "/api/jobs" && init?.method === "POST");
  expect(JSON.parse(String(submitted[1].init?.body))).not.toHaveProperty("fish_voice");
});

it("opens the voice management page and uses a voice without losing the script", async () => {
  stubApi({...config, defaults: {...config.defaults, engine: "fish_audio"}});
  const user = userEvent.setup();
  render(<App />);
  await screen.findByRole("option", {name: "Documentary narrator"});
  fireEvent.change(screen.getByLabelText("Script"), {target: {value: "Keep this script while managing voices."}});
  await user.selectOptions(screen.getByLabelText("Fish voice"), "custom");
  await user.click(screen.getByRole("link", {name: "Manage all voices"}));
  expect(await screen.findByRole("heading", {name: "Voice library"})).toBeVisible();
  await user.click(await screen.findByRole("button", {name: "Use Documentary narrator"}));
  await waitFor(() => expect(screen.queryByRole("heading", {name: "Voice library"})).not.toBeInTheDocument());
  expect(screen.getByLabelText("Script")).toHaveValue("Keep this script while managing voices.");
  await waitFor(() => expect(screen.getByLabelText("Fish voice")).toHaveValue("saved-two"));
});

it("honors a configured Kokoro default and does not add Fish delivery instructions", async () => {
  const calls = stubApi();
  const user = userEvent.setup();
  render(<App />);
  await screen.findByLabelText("Script");

  expect(screen.getByRole("radio", {name: "Kokoro Local"})).toBeChecked();
  fireEvent.change(screen.getByLabelText("Script"), {target: {value: "[quiet] Keep this text unchanged."}});
  await user.click(screen.getByRole("button", {name: "Generate speech"}));
  await waitFor(() => expect(calls.some(({init}) => init?.method === "POST")).toBe(true));

  const body = JSON.parse(String(calls.find(({init}) => init?.method === "POST")?.init?.body));
  expect(body.engine).toBe("kokoro");
  expect(body.text).toBe("[quiet] Keep this text unchanged.");
  expect(body).not.toHaveProperty("fish_style");
});
