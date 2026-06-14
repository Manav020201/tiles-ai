import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { TileIcon } from "./TileIcon";
import { makeTile } from "../test/fixtures";

describe("TileIcon", () => {
  it("shows the tile name", () => {
    render(<TileIcon tile={makeTile({ name: "Brainstorm" })} onOpen={() => {}} />);
    expect(screen.queryByText("Brainstorm")).not.toBeNull();
  });

  it("opens the sheet when tapped", () => {
    const onOpen = vi.fn();
    render(<TileIcon tile={makeTile()} onOpen={onOpen} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onOpen).toHaveBeenCalledOnce();
  });

  it("marks a tile whose connector needs credentials with a lock", () => {
    render(
      <TileIcon
        tile={makeTile({ connector: "github", connector_ready: false, missing_env: ["GITHUB_TOKEN"] })}
        onOpen={() => {}}
      />
    );
    expect(screen.queryByText("🔒")).not.toBeNull();
    expect(screen.getByRole("button").className).toContain("is-blocked");
  });

  it("shows a running indicator when active", () => {
    const { container } = render(<TileIcon tile={makeTile({ state: "active" })} onOpen={() => {}} />);
    expect(container.querySelector(".run-dot")).not.toBeNull();
    expect(screen.getByRole("button").className).toContain("is-active");
  });
});
