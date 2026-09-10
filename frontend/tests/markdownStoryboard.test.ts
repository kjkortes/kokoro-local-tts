import {describe, expect, it} from "vitest";

import {parseMarkdownTable} from "../src/markdownStoryboard";


describe("parseMarkdownTable", () => {
  it("extracts storyboard headers and cells from an aligned Markdown table", () => {
    const table = parseMarkdownTable(`
# Storyboard

| Beat | Approx. | Original VO | Visual cue |
| ---- | ------: | ----------- | ---------- |
| 1 | 3.2s | Want to feel better through what you eat? | Breakfast table. |
| 2 | 4.8s | Here are ten foods, for mood, brain, and energy. | Food spread. |
`);

    expect(table).toEqual({
      headers: ["Beat", "Approx.", "Original VO", "Visual cue"],
      rows: [
        ["1", "3.2s", "Want to feel better through what you eat?", "Breakfast table."],
        ["2", "4.8s", "Here are ten foods, for mood, brain, and energy.", "Food spread."],
      ],
    });
  });

  it("keeps escaped pipes inside a cell instead of creating another column", () => {
    const table = parseMarkdownTable(`
| Beat | VO |
| --- | --- |
| 1 | Choose this \\| that. |
`);

    expect(table.rows[0]).toEqual(["1", "Choose this | that."]);
  });

  it("reports when the file does not contain a Markdown table", () => {
    expect(() => parseMarkdownTable("Just a regular script.")).toThrow(
      "No Markdown table was found.",
    );
  });
});
