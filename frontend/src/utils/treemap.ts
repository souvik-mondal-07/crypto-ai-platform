/**
 * Squarified treemap layout (Bruls, Huizing & van Wijk).
 *
 * Pure geometry: given weighted items, returns one rectangle per item with
 * area proportional to its weight, tiling `width × height` exactly. Used by
 * the Dashboard heatmap; kept separate from React so it is unit-testable.
 *
 * Items with a missing, non-finite or non-positive weight are DROPPED (never
 * given a made-up size) — the caller decides how to tell the user.
 */
export interface TreemapInput<T> {
  item: T;
  weight: number | null | undefined;
}

export interface TreemapRect<T> {
  item: T;
  x: number;
  y: number;
  w: number;
  h: number;
}

interface Node<T> {
  item: T;
  area: number;
}

function worstRatio(areas: number[], side: number): number {
  const sum = areas.reduce((acc, value) => acc + value, 0);
  const max = Math.max(...areas);
  const min = Math.min(...areas);
  const sideSquared = side * side;
  return Math.max((sideSquared * max) / (sum * sum), (sum * sum) / (sideSquared * min));
}

export function squarify<T>(inputs: TreemapInput<T>[], width = 100, height = 100): TreemapRect<T>[] {
  const valid = inputs
    .filter((input): input is { item: T; weight: number } => Number.isFinite(input.weight) && (input.weight as number) > 0)
    .sort((a, b) => b.weight - a.weight);

  const total = valid.reduce((acc, input) => acc + input.weight, 0);
  if (valid.length === 0 || total <= 0 || width <= 0 || height <= 0) return [];

  const scale = (width * height) / total;
  const nodes: Node<T>[] = valid.map((input) => ({ item: input.item, area: input.weight * scale }));

  const result: TreemapRect<T>[] = [];
  let x = 0;
  let y = 0;
  let remainingW = width;
  let remainingH = height;
  let row: Node<T>[] = [];

  function layoutRow() {
    const rowArea = row.reduce((acc, node) => acc + node.area, 0);
    if (remainingW >= remainingH) {
      // Shorter side is the height: stack the row as a column on the left.
      const columnWidth = rowArea / remainingH;
      let cursorY = y;
      for (const node of row) {
        const rectHeight = node.area / columnWidth;
        result.push({ item: node.item, x, y: cursorY, w: columnWidth, h: rectHeight });
        cursorY += rectHeight;
      }
      x += columnWidth;
      remainingW -= columnWidth;
    } else {
      // Shorter side is the width: lay the row along the top.
      const rowHeight = rowArea / remainingW;
      let cursorX = x;
      for (const node of row) {
        const rectWidth = node.area / rowHeight;
        result.push({ item: node.item, x: cursorX, y, w: rectWidth, h: rowHeight });
        cursorX += rectWidth;
      }
      y += rowHeight;
      remainingH -= rowHeight;
    }
    row = [];
  }

  let index = 0;
  while (index < nodes.length) {
    const side = Math.min(remainingW, remainingH);
    const next = nodes[index];
    if (
      row.length === 0 ||
      worstRatio([...row, next].map((n) => n.area), side) <= worstRatio(row.map((n) => n.area), side)
    ) {
      row.push(next);
      index += 1;
    } else {
      layoutRow();
    }
  }
  if (row.length > 0) layoutRow();

  return result;
}
