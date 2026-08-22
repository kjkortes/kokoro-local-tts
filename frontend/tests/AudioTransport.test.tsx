import {render, screen} from "@testing-library/react";
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
  duration: 1.2,
};

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
  expect(screen.getByText("0:00 / 0:01")).toBeVisible();
});
