import {render, screen, waitFor} from "@testing-library/react";
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
    {id: "am_adam", name: "Adam", language: "a", gender: "male"},
    {id: "bf_emma", name: "Emma", language: "b", gender: "female"},
    {id: "bm_george", name: "George", language: "b", gender: "male"},
  ],
  presets: [
    {id: "neutral", name: "Neutral", description: "Natural timing.", speed: 1, pitch: 0, tempo: 1, pause_scale: 1},
    {id: "calm", name: "Calm", description: "Measured and spacious.", speed: .9, pitch: -.7, tempo: .94, pause_scale: 1.25},
  ],
  formats: ["wav", "mp3", "flac", "ogg"],
  defaults: {language: "a", voice: "af_heart", preset: "neutral", format: "wav"},
  limits: {
    speed: {min: .5, max: 2}, pitch: {min: -4, max: 4}, tempo: {min: .75, max: 1.25},
    pause_scale: {min: .5, max: 2}, volume: {min: 0, max: 1.5},
  },
};

function stubApi() {
  const calls: Array<{url: string; init?: RequestInit}> = [];
  vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    calls.push({url, init});
    if (url.endsWith("/api/config")) return Response.json(config);
    if (url.endsWith("/api/status")) return Response.json({state: "ready", device: "cpu", version: "0.1.0", detail: null});
    return Response.json({
      id: "one", state: "complete", phase: "Audio ready", progress: 1, error: null,
      audio_url: "/api/jobs/one/audio", download_url: "/api/jobs/one/download",
      filename: "script.wav", duration: 1,
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
