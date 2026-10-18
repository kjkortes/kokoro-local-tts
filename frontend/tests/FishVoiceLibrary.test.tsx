import {fireEvent, render, screen, waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {useState} from "react";

import {FishVoiceLibrary} from "../src/components/FishVoiceLibrary";

const starter = {id: "starter", name: "Original narrator", description: "Original voice", reference_id: "original-ref"};

function Workbench() {
  const [voice, setVoice] = useState("original-ref");
  return <><FishVoiceLibrary voice={voice} onVoice={setVoice} /><output aria-label="Generation voice">{voice}</output></>;
}

function stubLibrary() {
  let voices = [starter];
  vi.stubGlobal("fetch", vi.fn(async (input: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      const voice = {id: "new", ...JSON.parse(String(init.body))};
      voices = [...voices, voice];
      return Response.json(voice, {status: 201});
    }
    if (init?.method === "PUT") {
      const voice = {id: "new", ...JSON.parse(String(init.body))};
      voices = voices.map((item) => item.id === "new" ? voice : item);
      return Response.json(voice);
    }
    if (init?.method === "DELETE") {
      const removed = voices.find((item) => input.endsWith(item.id));
      voices = voices.filter((item) => item !== removed);
      return Response.json(removed);
    }
    return Response.json(voices);
  }));
}

it("selects, creates, edits, and deletes saved voices and reloads the library", async () => {
  stubLibrary();
  const user = userEvent.setup();
  const view = render(<Workbench />);
  await screen.findByRole("option", {name: "Original narrator"});
  expect(screen.getByLabelText("Fish voice")).toHaveValue("starter");

  await user.click(screen.getByRole("button", {name: "Add voice"}));
  fireEvent.change(screen.getByLabelText("Name"), {target: {value: "Documentary"}});
  fireEvent.change(screen.getByLabelText("Reference ID"), {target: {value: "new-ref"}});
  await user.click(screen.getByRole("button", {name: "Save voice"}));
  await screen.findByRole("option", {name: "Documentary"});
  expect(screen.getByLabelText("Generation voice")).toHaveTextContent("new-ref");

  await user.click(screen.getByRole("button", {name: "Edit voice"}));
  fireEvent.change(screen.getByLabelText("Name"), {target: {value: "Warm narrator"}});
  fireEvent.change(screen.getByLabelText("Reference ID"), {target: {value: "updated-ref"}});
  await user.click(screen.getByRole("button", {name: "Save voice"}));
  await screen.findByRole("option", {name: "Warm narrator"});
  expect(screen.getByLabelText("Generation voice")).toHaveTextContent("updated-ref");

  view.unmount();
  render(<Workbench />);
  await user.selectOptions(await screen.findByLabelText("Fish voice"), "new");
  expect(screen.getByLabelText("Generation voice")).toHaveTextContent("updated-ref");
  await user.click(screen.getByRole("button", {name: "Delete voice"}));
  await user.click(screen.getByRole("button", {name: "Keep voice"}));
  expect(screen.getByRole("option", {name: "Warm narrator"})).toBeInTheDocument();
  await user.click(screen.getByRole("button", {name: "Delete voice"}));
  await user.click(screen.getByRole("button", {name: "Confirm delete"}));
  await waitFor(() => expect(screen.queryByRole("option", {name: "Warm narrator"})).not.toBeInTheDocument());
  expect(screen.getByLabelText("Fish voice")).toHaveValue("provider");
  expect(screen.getByLabelText("Generation voice")).toBeEmptyDOMElement();
});

it("supports a custom reference and provider default without saving", async () => {
  stubLibrary();
  const user = userEvent.setup();
  render(<Workbench />);
  await screen.findByRole("option", {name: "Original narrator"});
  await user.selectOptions(screen.getByLabelText("Fish voice"), "custom");
  fireEvent.change(screen.getByLabelText("Custom Fish Voice / Reference ID"), {target: {value: "temporary-ref"}});
  expect(screen.getByLabelText("Generation voice")).toHaveTextContent("temporary-ref");
  await user.selectOptions(screen.getByLabelText("Fish voice"), "provider");
  expect(screen.getByLabelText("Generation voice")).toBeEmptyDOMElement();
});

it("keeps the editor and current generation voice when a save fails", async () => {
  stubLibrary();
  const user = userEvent.setup();
  render(<Workbench />);
  await screen.findByRole("option", {name: "Original narrator"});
  await user.click(screen.getByRole("button", {name: "Add voice"}));
  fireEvent.change(screen.getByLabelText("Name"), {target: {value: "Duplicate"}});
  fireEvent.change(screen.getByLabelText("Reference ID"), {target: {value: "original-ref"}});
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({error: {message: "This reference is already saved."}}, {status: 409})));
  await user.click(screen.getByRole("button", {name: "Save voice"}));
  expect(await screen.findByRole("alert")).toHaveTextContent("This reference is already saved.");
  expect(screen.getByLabelText("Name")).toHaveValue("Duplicate");
  expect(screen.getByLabelText("Generation voice")).toHaveTextContent("original-ref");
});

it("reports loading failures and lets the user retry", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({error: {message: "Library unavailable."}}, {status: 503})));
  const user = userEvent.setup();
  render(<Workbench />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Library unavailable.");
  expect(screen.getByLabelText("Generation voice")).toHaveTextContent("original-ref");
  stubLibrary();
  await user.click(screen.getByRole("button", {name: "Reload voices"}));
  await screen.findByRole("option", {name: "Original narrator"});
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
