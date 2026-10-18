import {fireEvent, render, screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {FishVoiceManager} from "../src/components/FishVoiceManager";
import type {FishVoiceReference} from "../src/types";

function stubLibrary(count: number) {
  let voices = Array.from({length: count}, (_, index) => ({
    id: `voice-${index}`, name: `Voice ${String(index).padStart(2, "0")}`,
    description: `Description ${index}`, reference_id: `ref-${index}`,
  }));
  vi.stubGlobal("fetch", vi.fn(async (input: string, init?: RequestInit) => {
    const url = new URL(input, "http://localhost");
    if (init?.method === "POST") {
      const saved = {id: "new", ...JSON.parse(String(init.body))} as FishVoiceReference;
      voices = [...voices, saved];
      return Response.json(saved, {status: 201});
    }
    if (init?.method === "DELETE") {
      const saved = voices.find((item) => url.pathname.endsWith(item.id));
      voices = voices.filter((item) => item !== saved);
      return Response.json(saved);
    }
    if (init?.method === "PUT") {
      const id = url.pathname.split("/").pop()!;
      const saved = {id, ...JSON.parse(String(init.body))} as FishVoiceReference;
      voices = voices.map((item) => item.id === id ? saved : item);
      return Response.json(saved);
    }
    const page = Number(url.searchParams.get("page") ?? 1);
    return Response.json({items: voices.slice((page - 1) * 10, page * 10), total: voices.length, page, page_size: 10});
  }));
}

it("paginates all saved voices and shows descriptions and references", async () => {
  stubLibrary(12);
  const user = userEvent.setup();
  render(<FishVoiceManager onUse={vi.fn()} onChanged={vi.fn()} />);
  expect(await screen.findByText("Voice 00")).toBeVisible();
  expect(screen.getByText("Description 0")).toBeVisible();
  expect(screen.getByText("ref-0")).toBeVisible();
  expect(screen.queryByText("Voice 10")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", {name: "Next page"}));
  expect(await screen.findByText("Voice 10")).toBeVisible();
  expect(screen.queryByText("Voice 00")).not.toBeInTheDocument();
  expect(screen.getByRole("button", {name: "Next page"})).toBeDisabled();
  await user.click(screen.getByRole("button", {name: "Previous page"}));
  expect(await screen.findByText("Voice 00")).toBeVisible();
});

it("adds and edits descriptions and extracts the reference from a pasted URL", async () => {
  stubLibrary(0);
  const user = userEvent.setup();
  render(<FishVoiceManager onUse={vi.fn()} onChanged={vi.fn()} />);
  await screen.findByText(/No saved voices/);
  await user.click(screen.getByRole("button", {name: "Add voice"}));
  fireEvent.change(screen.getByLabelText("Name"), {target: {value: "FairyTail"}});
  fireEvent.change(screen.getByLabelText("Description"), {target: {value: "Storytelling, narrating"}});
  await user.click(screen.getByLabelText("Reference ID"));
  await user.paste("https://fish.audio/app/m/689b47ca83dd48dba90b160affb8a118/");
  expect(screen.getByLabelText("Reference ID")).toHaveValue("689b47ca83dd48dba90b160affb8a118");
  await user.click(screen.getByRole("button", {name: "Save voice"}));
  expect(await screen.findByText("FairyTail")).toBeVisible();
  expect(screen.getByText("Storytelling, narrating")).toBeVisible();
  expect(screen.getByRole("link", {name: "Open FairyTail in Fish Audio"})).toHaveAttribute("href", "https://fish.audio/app/m/689b47ca83dd48dba90b160affb8a118/");
  await user.click(screen.getByRole("button", {name: "Copy reference ID for FairyTail"}));
  expect(await navigator.clipboard.readText()).toBe("689b47ca83dd48dba90b160affb8a118");
  await user.click(screen.getByRole("button", {name: "Edit FairyTail"}));
  expect(screen.getByLabelText("Description")).toHaveValue("Storytelling, narrating");
  fireEvent.change(screen.getByLabelText("Description"), {target: {value: "Warm narration"}});
  await user.click(screen.getByRole("button", {name: "Save voice"}));
  expect(await screen.findByText("Warm narration")).toBeVisible();
});

it("returns to the previous page when the last row on a page is deleted", async () => {
  stubLibrary(11);
  const user = userEvent.setup();
  render(<FishVoiceManager onUse={vi.fn()} onChanged={vi.fn()} />);
  await screen.findByText("Voice 00");
  await user.click(screen.getByRole("button", {name: "Next page"}));
  await user.click(await screen.findByRole("button", {name: "Delete Voice 10"}));
  await user.click(screen.getByRole("button", {name: "Confirm delete"}));
  expect(await screen.findByText("Voice 00")).toBeVisible();
  expect(screen.queryByText("Voice 10")).not.toBeInTheDocument();
  expect(screen.getByRole("button", {name: "Next page"})).toBeDisabled();
});

it("rejects unrelated URLs without losing the form", async () => {
  stubLibrary(0);
  const user = userEvent.setup();
  render(<FishVoiceManager onUse={vi.fn()} onChanged={vi.fn()} />);
  await screen.findByText(/No saved voices/);
  await user.click(screen.getByRole("button", {name: "Add voice"}));
  fireEvent.change(screen.getByLabelText("Name"), {target: {value: "Narrator"}});
  fireEvent.change(screen.getByLabelText("Reference ID"), {target: {value: "https://example.com/voice"}});
  await user.click(screen.getByRole("button", {name: "Save voice"}));
  expect(await screen.findByRole("alert")).toHaveTextContent(/Fish Audio voice URL/);
  expect(screen.getByLabelText("Name")).toHaveValue("Narrator");
});
