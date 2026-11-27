import { describe, expect, it } from "vitest";
import {
  diffStandings,
  displayPath,
  displayTokenFromHash,
  formatCountdown,
  parseDisplaySearch,
  resolveDisplayOptions,
} from "@/lib/display";

describe("display options", () => {
  it.each([
    [{}, { bracket: undefined, rotate: 0, scale: 1 }],
    [
      { rotate: "3", scale: "9" },
      { bracket: undefined, rotate: 10, scale: 3 },
    ],
    [
      { rotate: "", scale: true },
      { bracket: undefined, rotate: 0, scale: 1 },
    ],
    [
      { bracket: "pro", rotate: "30" },
      { bracket: "pro", rotate: 0, scale: 1 },
    ],
    [{ rotate: 45.4 }, { bracket: undefined, rotate: 45, scale: 1 }],
  ])("resolves %j", (search, expected) => {
    expect(resolveDisplayOptions(parseDisplaySearch(search))).toEqual(expected);
  });
});

it.each([
  [-5_000, "0:00:00"],
  [61_999, "0:01:01"],
  [3_725_000, "1:02:05"],
  [90_061_000, "1d 1:01:01"],
])("formats %i ms as %s", (ms, expected) => {
  expect(formatCountdown(ms)).toBe(expected);
});

it("reports teams that moved or scored, ignoring new teams", () => {
  const before = [
    { team_id: "a", rank: 1, total: 300 },
    { team_id: "b", rank: 2, total: 200 },
    { team_id: "c", rank: 3, total: 100 },
  ];

  const changes = diffStandings(before, [
    { team_id: "b", rank: 1, total: 400 },
    { team_id: "a", rank: 2, total: 300 },
    { team_id: "c", rank: 3, total: 100 },
    { team_id: "d", rank: 4, total: 50 },
  ]);

  expect(Object.fromEntries(changes)).toEqual({
    a: { rankDelta: -1, scored: false },
    b: { rankDelta: 1, scored: true },
  });
});

it.each([
  [{}, "/display"],
  [{ bracket: "pro" }, "/display?bracket=pro"],
  [{ rotate: "5", scale: "1.25" }, "/display?rotate=10&scale=1.25"],
])("builds the display path for %j", (search, expected) => {
  const path = displayPath(resolveDisplayOptions(parseDisplaySearch(search)));

  expect(path).toBe(expected);
  const query = Object.fromEntries(new URL(path, "http://x").searchParams);
  expect(resolveDisplayOptions(parseDisplaySearch(query))).toEqual(
    resolveDisplayOptions(parseDisplaySearch(search)),
  );
});

it.each([
  ["", null],
  ["#token=nxt_abc", "nxt_abc"],
  ["#token=", null],
  ["#other=1&token=a%2Bb", "a+b"],
])("reads the screen token from %j", (hash, expected) => {
  expect(displayTokenFromHash(hash)).toBe(expected);
});

it("puts the given day unit on a countdown past 24 hours", () => {
  expect(formatCountdown(90_061_000, "j")).toBe("1j 1:01:01");
});
