export interface MarkdownTable {
  headers: string[];
  rows: string[][];
}

function splitRow(line: string): string[] {
  const trimmed = line.trim();
  const content = trimmed.startsWith("|") ? trimmed.slice(1) : trimmed;
  const withoutTrailingPipe = content.endsWith("|") && !content.endsWith("\\|")
    ? content.slice(0, -1)
    : content;
  const cells: string[] = [];
  let cell = "";
  let escaped = false;

  for (const character of withoutTrailingPipe) {
    if (escaped) {
      cell += character === "|" ? "|" : `\\${character}`;
      escaped = false;
    } else if (character === "\\") {
      escaped = true;
    } else if (character === "|") {
      cells.push(cell.trim());
      cell = "";
    } else {
      cell += character;
    }
  }
  if (escaped) cell += "\\";
  cells.push(cell.trim());
  return cells;
}

function isSeparatorRow(cells: string[]) {
  return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}

export function parseMarkdownTable(source: string): MarkdownTable {
  const lines = source.replace(/\r\n?/g, "\n").split("\n");
  for (let index = 0; index < lines.length - 1; index += 1) {
    const headers = splitRow(lines[index]);
    const separator = splitRow(lines[index + 1]);
    if (headers.length < 2 || separator.length !== headers.length || !isSeparatorRow(separator)) continue;

    const rows: string[][] = [];
    for (const line of lines.slice(index + 2)) {
      if (!line.trim() || !line.includes("|")) break;
      const cells = splitRow(line);
      rows.push(headers.map((_, cellIndex) => cells[cellIndex] ?? ""));
    }
    return {headers, rows};
  }
  throw new Error("No Markdown table was found.");
}
