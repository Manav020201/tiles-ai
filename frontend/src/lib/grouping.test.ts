import { describe, expect, it } from "vitest";
import { groupTiles } from "./grouping";
import { makeTile } from "../test/fixtures";

describe("groupTiles", () => {
  it("leads with instant tiles under 'Instant'", () => {
    const groups = groupTiles([
      makeTile({ id: "inbox", connector: "gmail" }),
      makeTile({ id: "ask", connector: null }),
    ]);
    expect(groups[0].heading).toBe("Instant");
    expect(groups[0].items.map((t) => t.id)).toEqual(["ask"]);
  });

  it("groups app tiles by connector", () => {
    const groups = groupTiles([
      makeTile({ id: "a", connector: "gmail" }),
      makeTile({ id: "b", connector: "gmail" }),
      makeTile({ id: "c", connector: "slack" }),
    ]);
    expect(groups.find((g) => g.heading === "gmail")!.items.map((t) => t.id)).toEqual(["a", "b"]);
    expect(groups.find((g) => g.heading === "slack")!.items).toHaveLength(1);
  });

  it("omits the Instant group when there are none", () => {
    const groups = groupTiles([makeTile({ id: "a", connector: "gmail" })]);
    expect(groups.some((g) => g.heading === "Instant")).toBe(false);
  });
});
