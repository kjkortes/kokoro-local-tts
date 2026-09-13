import {act, fireEvent, render, screen, waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {AudioTransport} from "../src/components/AudioTransport";
import type {JobResponse} from "../src/types";


const result: JobResponse = {
  id: "job-1",
  state: "complete",
  phase: "Audio ready",
  progress: 1,
  error: null,
  audio_url: "/api/jobs/job-1/audio",
  download_url: "/api/jobs/job-1/download",
  filename: "hello.mp3",
  duration: 5.2,
  transcript: "Hello there.\n\nThis is the whole transcript.",
  segments: [
    {text: "Hello there.", start: 0, end: 2.5, paragraph_end: true},
    {text: "This is the whole transcript.", start: 2.72, end: 5.2, paragraph_end: true},
  ],
  words: [
    {text: "Hello", start: 0.08, end: 0.46},
    {text: "there.", start: 0.52, end: 0.91},
    {text: "This", start: 2.8, end: 3.07},
    {text: "is", start: 3.12, end: 3.24},
    {text: "the", start: 3.29, end: 3.46},
    {text: "whole", start: 3.51, end: 3.88},
    {text: "transcript.", start: 3.94, end: 4.61},
  ],
};

it("keeps legacy completed jobs playable when transcript fields are absent", () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  const {segments: _segments, transcript: _transcript, words: _words, ...legacyResult} = result;

  render(<AudioTransport result={legacyResult as JobResponse} />);

  expect(screen.getByRole("region", {name: "Generated audio"})).toBeVisible();
  expect(screen.queryByRole("region", {name: "Timestamped transcript"})).not.toBeInTheDocument();
});

it("switches from segment timestamps to aligned word timestamps", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  const user = userEvent.setup();
  const {container} = render(<AudioTransport result={result} />);

  expect(screen.getByRole("button", {name: "Segment timestamps"})).toHaveAttribute("aria-pressed", "true");
  await user.click(screen.getByRole("button", {name: "Word timestamps"}));

  expect(screen.getByRole("button", {name: "Word timestamps"})).toHaveAttribute("aria-pressed", "true");
  const word = screen.getByRole("button", {name: "Seek to word at 0:03.9: transcript."});
  expect(screen.getByText("0:03.9 — 0:04.6")).toBeVisible();
  await user.click(word);
  expect(container.querySelector("audio")?.currentTime).toBe(3.94);
});

it("falls back to segments when a later result has no aligned words", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  const user = userEvent.setup();
  const {rerender} = render(<AudioTransport result={result} />);
  await user.click(screen.getByRole("button", {name: "Word timestamps"}));

  rerender(<AudioTransport result={{...result, id: "job-2", words: []}} />);

  expect(screen.queryByRole("button", {name: "Word timestamps"})).not.toBeInTheDocument();
  expect(screen.getByText("Hello there.")).toBeVisible();
  expect(screen.getByText("0:00.0 — 0:02.5")).toBeVisible();
});

it("makes the completed result playable and downloadable without autoplay", async () => {
  const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  render(<AudioTransport result={result} />);
  expect(screen.getByRole("button", {name: "Play"})).toBeEnabled();
  expect(screen.getByRole("link", {name: "Download MP3"})).toHaveAttribute("href", "/api/jobs/job-1/download");
  expect(play).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", {name: "Play"}));
  expect(play).toHaveBeenCalledOnce();
});

it("shows the result filename and duration", () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  render(<AudioTransport result={result} />);
  expect(screen.getByText("hello.mp3")).toBeVisible();
  expect(screen.getByText("0:00 / 0:05")).toBeVisible();
});

it("shows every timestamped transcript segment", () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  render(<AudioTransport result={result} />);

  expect(screen.getByRole("region", {name: "Timestamped transcript"})).toBeVisible();
  expect(screen.getByText("Hello there.")).toBeVisible();
  expect(screen.getByText("This is the whole transcript.")).toBeVisible();
  expect(screen.getByText("0:00.0 — 0:02.5")).toBeVisible();
  expect(screen.getByText("0:02.7 — 0:05.2")).toBeVisible();
});

it("identifies Whisper-derived timing for Fish Audio transcripts", () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  render(<AudioTransport result={{...result, timing_source: "whisper"}} />);

  expect(screen.getByText("Timed locally with Whisper")).toBeVisible();
});

it("switches between the readable transcript and timescript JSON", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  const user = userEvent.setup();
  render(<AudioTransport result={result} />);

  expect(screen.getByRole("button", {name: "Transcript view"})).toHaveAttribute("aria-pressed", "true");
  await user.click(screen.getByRole("button", {name: "JSON view"}));

  expect(screen.getByRole("button", {name: "JSON view"})).toHaveAttribute("aria-pressed", "true");
  const json = screen.getByLabelText("Timescript JSON");
  expect(JSON.parse(json.textContent ?? "")).toEqual(
    result.segments?.map(({start, end, text}) => ({start, end, text})),
  );
  expect(screen.queryByText("0:00.0 — 0:02.5")).not.toBeInTheDocument();
});

it("includes the segment text in its accessible seek control", () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  render(<AudioTransport result={result} />);

  expect(screen.getByRole("button", {
    name: "Seek to segment at 0:02.7: This is the whole transcript.",
  })).toBeVisible();
});

it("seeks to a transcript segment", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  const user = userEvent.setup();
  const {container} = render(<AudioTransport result={result} />);

  await user.click(screen.getByRole("button", {
    name: "Seek to segment at 0:02.7: This is the whole transcript.",
  }));

  expect(container.querySelector("audio")?.currentTime).toBe(2.72);
});

it("marks the segment at the current playback position", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  const user = userEvent.setup();
  render(<AudioTransport result={result} />);
  const first = screen.getByRole("button", {name: "Seek to segment at 0:00.0: Hello there."});
  const second = screen.getByRole("button", {
    name: "Seek to segment at 0:02.7: This is the whole transcript.",
  });

  expect(first).toHaveAttribute("aria-current", "true");
  await user.click(second);
  expect(second).toHaveAttribute("aria-current", "true");
  expect(first).not.toHaveAttribute("aria-current");
});

it("does not mark speech as current during an inserted pause", () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  const {container} = render(<AudioTransport result={result} />);
  const audio = container.querySelector("audio")!;

  audio.currentTime = 2.6;
  fireEvent.timeUpdate(audio);

  expect(screen.queryByRole("button", {current: true})).not.toBeInTheDocument();
});

it("copies the full transcript with a timestamp range on every segment", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  const user = userEvent.setup();
  render(<AudioTransport result={result} />);

  await user.click(screen.getByRole("button", {name: "Copy transcript"}));

  expect(await navigator.clipboard.readText()).toBe(
    "[0:00.0 — 0:02.5] Hello there.\n\n[0:02.7 — 0:05.2] This is the whole transcript.",
  );
});

it("copies one aligned timestamp range per word in word mode", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  const user = userEvent.setup();
  render(<AudioTransport result={result} />);

  await user.click(screen.getByRole("button", {name: "Word timestamps"}));
  await user.click(screen.getByRole("button", {name: "Copy transcript"}));

  expect(await navigator.clipboard.readText()).toBe(
    "[0:00.0 — 0:00.4] Hello\n[0:00.5 — 0:00.9] there.\n[0:02.8 — 0:03.0] This\n"
      + "[0:03.1 — 0:03.2] is\n[0:03.2 — 0:03.4] the\n[0:03.5 — 0:03.8] whole\n"
      + "[0:03.9 — 0:04.6] transcript.",
  );
});

it("copies the displayed JSON with numeric start and end timestamps", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  const user = userEvent.setup();
  render(<AudioTransport result={result} />);

  await user.click(screen.getByRole("button", {name: "JSON view"}));
  await user.click(screen.getByRole("button", {name: "Copy JSON"}));

  expect(JSON.parse(await navigator.clipboard.readText())).toEqual([
    {start: 0, end: 2.5, text: "Hello there."},
    {start: 2.72, end: 5.2, text: "This is the whole transcript."},
  ]);
});

it("serializes aligned words as JSON in word mode", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  const user = userEvent.setup();
  render(<AudioTransport result={result} />);

  await user.click(screen.getByRole("button", {name: "Word timestamps"}));
  await user.click(screen.getByRole("button", {name: "JSON view"}));

  const expected = [
    {start: 0.08, end: 0.46, text: "Hello"},
    {start: 0.52, end: 0.91, text: "there."},
    {start: 2.8, end: 3.07, text: "This"},
    {start: 3.12, end: 3.24, text: "is"},
    {start: 3.29, end: 3.46, text: "the"},
    {start: 3.51, end: 3.88, text: "whole"},
    {start: 3.94, end: 4.61, text: "transcript."},
  ];
  expect(JSON.parse(screen.getByLabelText("Timescript JSON").textContent ?? "")).toEqual(expected);
});

it("downloads the readable timestamped transcript as a text file", () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  render(<AudioTransport result={result} />);

  const download = screen.getByRole("link", {name: "Download transcript"});
  expect(download).toHaveAttribute("download", "hello-transcript.txt");
  const href = download.getAttribute("href") ?? "";
  expect(href).toMatch(/^data:text\/plain;charset=utf-8,/);
  expect(decodeURIComponent(href.split(",", 2)[1])).toBe(
    "[0:00.0 — 0:02.5] Hello there.\n\n[0:02.7 — 0:05.2] This is the whole transcript.",
  );
});

it("downloads the selected JSON timescript as a JSON file", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  const user = userEvent.setup();
  render(<AudioTransport result={result} />);

  await user.click(screen.getByRole("button", {name: "JSON view"}));

  const download = screen.getByRole("link", {name: "Download JSON"});
  expect(download).toHaveAttribute("download", "hello-timescript.json");
  const href = download.getAttribute("href") ?? "";
  expect(href).toMatch(/^data:application\/json;charset=utf-8,/);
  expect(JSON.parse(decodeURIComponent(href.split(",", 2)[1]))).toEqual([
    {start: 0, end: 2.5, text: "Hello there."},
    {start: 2.72, end: 5.2, text: "This is the whole transcript."},
  ]);
});

it("labels word-level transcript downloads unambiguously", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  const user = userEvent.setup();
  render(<AudioTransport result={result} />);

  await user.click(screen.getByRole("button", {name: "Word timestamps"}));
  expect(screen.getByRole("link", {name: "Download transcript"})).toHaveAttribute(
    "download", "hello-word-transcript.txt",
  );
  await user.click(screen.getByRole("button", {name: "JSON view"}));
  expect(screen.getByRole("link", {name: "Download JSON"})).toHaveAttribute(
    "download", "hello-word-timescript.json",
  );
});

it("clears stale copy feedback when the timescript view changes", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  const user = userEvent.setup();
  render(<AudioTransport result={result} />);

  await user.click(screen.getByRole("button", {name: "Copy transcript"}));
  expect(screen.getByRole("status")).toHaveTextContent("Transcript copied");
  await user.click(screen.getByRole("button", {name: "JSON view"}));

  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

it("ignores a delayed copy result after the timescript view changes", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  const user = userEvent.setup();
  let finishCopy = () => {};
  vi.spyOn(navigator.clipboard, "writeText").mockImplementation(() => (
    new Promise<void>((resolve) => { finishCopy = resolve; })
  ));
  render(<AudioTransport result={result} />);

  await user.click(screen.getByRole("button", {name: "Copy transcript"}));
  await user.click(screen.getByRole("button", {name: "JSON view"}));
  await act(async () => {
    finishCopy();
    await Promise.resolve();
  });

  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

it("serializes repeated copy attempts so the last click wins", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  const user = userEvent.setup();
  const finishes: Array<() => void> = [];
  const writeText = vi.spyOn(navigator.clipboard, "writeText").mockImplementation(() => (
    new Promise<void>((resolve) => { finishes.push(resolve); })
  ));
  render(<AudioTransport result={result} />);

  await user.click(screen.getByRole("button", {name: "Copy transcript"}));
  await user.click(screen.getByRole("button", {name: "JSON view"}));
  await user.click(screen.getByRole("button", {name: "Copy JSON"}));
  expect(writeText).toHaveBeenCalledOnce();

  await act(async () => { finishes[0](); });
  await waitFor(() => expect(writeText).toHaveBeenCalledTimes(2));
  await act(async () => { finishes[1](); });

  expect(screen.getByRole("status")).toHaveTextContent("JSON copied");
});

it("confirms when the transcript is copied", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  const user = userEvent.setup();
  render(<AudioTransport result={result} />);

  await user.click(screen.getByRole("button", {name: "Copy transcript"}));

  expect(screen.getByRole("status")).toHaveTextContent("Transcript copied");
});

it("copies again and refreshes the confirmation on every click", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  const user = userEvent.setup();
  render(<AudioTransport result={result} />);
  const copyButton = screen.getByRole("button", {name: "Copy transcript"});

  await user.click(copyButton);
  await navigator.clipboard.writeText("cleared");
  await user.click(copyButton);

  expect(await navigator.clipboard.readText()).toContain("[0:00.0 — 0:02.5] Hello there.");
  expect(screen.getByRole("status")).toHaveTextContent("Transcript copied · 2");
});

it("copies when the modern Clipboard API is unavailable", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  const user = userEvent.setup();
  const originalClipboard = navigator.clipboard;
  const originalExecCommand = document.execCommand;
  try {
    Object.defineProperty(navigator, "clipboard", {value: undefined, configurable: true});
    document.execCommand = vi.fn(() => true);
    render(<AudioTransport result={result} />);

    await user.click(screen.getByRole("button", {name: "Copy transcript"}));

    expect(screen.getByRole("status")).toHaveTextContent("Transcript copied");
  } finally {
    Object.defineProperty(navigator, "clipboard", {value: originalClipboard, configurable: true});
    document.execCommand = originalExecCommand;
  }
});

it("offers the timestamped transcript for manual copying when browser copy fails", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  const user = userEvent.setup();
  const originalClipboard = navigator.clipboard;
  const originalExecCommand = document.execCommand;
  try {
    Object.defineProperty(navigator, "clipboard", {value: undefined, configurable: true});
    document.execCommand = vi.fn(() => false);
    render(<AudioTransport result={result} />);

    await user.click(screen.getByRole("button", {name: "Copy transcript"}));

    expect(screen.getByRole("status")).toHaveTextContent("Copy failed");
    expect(screen.getByLabelText("Full transcript")).toHaveValue(
      "[0:00.0 — 0:02.5] Hello there.\n\n[0:02.7 — 0:05.2] This is the whole transcript.",
    );
  } finally {
    Object.defineProperty(navigator, "clipboard", {value: originalClipboard, configurable: true});
    document.execCommand = originalExecCommand;
  }
});

it("offers the selected JSON for manual copying when browser copy fails", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(new ArrayBuffer(8))));
  const user = userEvent.setup();
  const originalClipboard = navigator.clipboard;
  const originalExecCommand = document.execCommand;
  try {
    Object.defineProperty(navigator, "clipboard", {value: undefined, configurable: true});
    document.execCommand = vi.fn(() => false);
    render(<AudioTransport result={result} />);

    await user.click(screen.getByRole("button", {name: "JSON view"}));
    await user.click(screen.getByRole("button", {name: "Copy JSON"}));

    expect(screen.getByRole("status")).toHaveTextContent("Copy failed. Select the JSON below.");
    const field = screen.getByLabelText("Full JSON timescript") as HTMLTextAreaElement;
    expect(JSON.parse(field.value)).toEqual(result.segments?.map(({start, end, text}) => ({start, end, text})));
  } finally {
    Object.defineProperty(navigator, "clipboard", {value: originalClipboard, configurable: true});
    document.execCommand = originalExecCommand;
  }
});
