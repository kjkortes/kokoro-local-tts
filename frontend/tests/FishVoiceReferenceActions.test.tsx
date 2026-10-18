import {render, screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {FishVoiceReferenceActions} from "../src/components/FishVoiceReferenceActions";

const reference = "689b47ca83dd48dba90b160affb8a118";

it("copies only the reference ID and links to the corresponding Fish Audio page", async () => {
  const user = userEvent.setup();
  render(<FishVoiceReferenceActions name="FairyTail 1" reference={reference} />);
  await user.click(screen.getByRole("button", {name: "Copy reference ID for FairyTail 1"}));
  expect(await navigator.clipboard.readText()).toBe(reference);
  expect(screen.getByRole("status")).toHaveTextContent("ID copied");
  const link = screen.getByRole("link", {name: "Open FairyTail 1 in Fish Audio"});
  expect(link).toHaveAttribute("href", "https://fish.audio/app/m/689b47ca83dd48dba90b160affb8a118/");
  expect(link).toHaveAttribute("target", "_blank");
  expect(link).toHaveAttribute("rel", "noopener noreferrer");
});

it("offers a selected ID for manual copying when browser copying is unavailable", async () => {
  const user = userEvent.setup();
  vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(new Error("Denied"));
  render(<FishVoiceReferenceActions name="FairyTail 1" reference={reference} />);
  await user.click(screen.getByRole("button", {name: "Copy reference ID for FairyTail 1"}));
  const field = await screen.findByRole("textbox", {name: "Reference ID to copy for FairyTail 1"});
  expect(field).toHaveValue(reference);
  expect(field).toHaveFocus();
  expect((field as HTMLInputElement).selectionEnd).toBe(32);
});

it("keeps legacy references copyable without linking invalid IDs", async () => {
  const user = userEvent.setup();
  render(<FishVoiceReferenceActions name="Legacy voice" reference="https://example.com/old" />);
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", {name: "Copy reference ID for Legacy voice"}));
  expect(await navigator.clipboard.readText()).toBe("https://example.com/old");
});
