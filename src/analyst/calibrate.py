"""Interactive region calibration.

Open a screenshot in a Tk window, walk through every region name, click two
corners per region, write the resulting boxes back into the YAML config.

Usage:
    analyst calibrate path/to/screenshot.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml
from PIL import Image


REGION_NAMES: list[str] = [
    # Global / phase
    "phase_ribbon",
    "turn_indicator",
    "priority_indicator",
    "match_score",
    # Opponent
    "opp_avatar", "opp_life", "opp_poison", "opp_energy", "opp_experience",
    "opp_library_count", "opp_graveyard_count", "opp_exile_count",
    "opp_hand_count", "opp_mana_pool", "opp_command_zone",
    "opp_monarch_marker", "opp_initiative_marker", "opp_ring_marker",
    "opp_day_night_marker", "opp_turn_timer",
    "opp_hand",
    "opp_battlefield_lands", "opp_battlefield_creatures", "opp_battlefield_other",
    "opp_graveyard", "opp_exile",
    # Me
    "my_avatar", "my_life", "my_poison", "my_energy", "my_experience",
    "my_library_count", "my_graveyard_count", "my_exile_count",
    "my_hand_count", "my_mana_pool", "my_command_zone",
    "my_monarch_marker", "my_initiative_marker", "my_ring_marker",
    "my_day_night_marker", "my_turn_timer",
    "my_hand",
    "my_battlefield_lands", "my_battlefield_creatures", "my_battlefield_other",
    "my_graveyard", "my_exile",
    # Stack & overlay
    "stack",
    "dialog",
]


def calibrate(screenshot_path: str, config_path: str) -> dict[str, list[int]]:
    import tkinter as tk
    from PIL import ImageTk

    img = Image.open(screenshot_path)
    sw, sh = img.size

    # Fit to a reasonable window while remembering the scale factor.
    scale = min(1.0, 1600 / sw, 900 / sh)
    disp = img.resize((int(sw * scale), int(sh * scale)))

    root = tk.Tk()
    root.title("Analyst region calibration")
    photo = ImageTk.PhotoImage(disp)
    canvas = tk.Canvas(root, width=disp.size[0], height=disp.size[1])
    canvas.pack()
    canvas.create_image(0, 0, anchor=tk.NW, image=photo)

    label = tk.Label(root, text="", anchor="w", font=("monospace", 12))
    label.pack(fill=tk.X)

    state = {
        "idx": 0,
        "first": None,
        "rect": None,
        "results": {},
    }

    def update_label():
        i = state["idx"]
        if i < len(REGION_NAMES):
            label.config(
                text=f"[{i+1}/{len(REGION_NAMES)}]  {REGION_NAMES[i]}   "
                     "(click top-left, then bottom-right.  's' = skip,  'u' = undo)"
            )
        else:
            label.config(text="DONE — closing window will save the config.")

    def on_click(event):
        if state["idx"] >= len(REGION_NAMES):
            return
        if state["first"] is None:
            state["first"] = (event.x, event.y)
            if state["rect"] is not None:
                canvas.delete(state["rect"])
            state["rect"] = canvas.create_rectangle(
                event.x, event.y, event.x, event.y, outline="lime", width=2
            )
        else:
            x0, y0 = state["first"]
            x1, y1 = event.x, event.y
            box = [
                int(min(x0, x1) / scale), int(min(y0, y1) / scale),
                int(max(x0, x1) / scale), int(max(y0, y1) / scale),
            ]
            name = REGION_NAMES[state["idx"]]
            state["results"][name] = box
            state["first"] = None
            state["rect"] = None
            state["idx"] += 1
            update_label()

    def on_motion(event):
        if state["first"] is None or state["rect"] is None:
            return
        x0, y0 = state["first"]
        canvas.coords(state["rect"], x0, y0, event.x, event.y)

    def on_key(event):
        if event.keysym == "s" and state["idx"] < len(REGION_NAMES):
            state["idx"] += 1
            state["first"] = None
            if state["rect"] is not None:
                canvas.delete(state["rect"])
                state["rect"] = None
            update_label()
        elif event.keysym == "u" and state["idx"] > 0:
            state["idx"] -= 1
            state["results"].pop(REGION_NAMES[state["idx"]], None)
            update_label()

    canvas.bind("<Button-1>", on_click)
    canvas.bind("<Motion>", on_motion)
    root.bind("<Key>", on_key)
    update_label()
    root.mainloop()

    _write_back(config_path, state["results"])
    return state["results"]


def _write_back(config_path: str, regions: dict[str, list[int]]) -> None:
    p = Path(config_path)
    cfg = yaml.safe_load(p.read_text()) if p.exists() else {}
    cfg.setdefault("perception", {}).setdefault("regions", {}).update(regions)
    p.write_text(yaml.safe_dump(cfg, sort_keys=False))
    print(f"\nwrote {len(regions)} regions to {config_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m analyst.calibrate <screenshot.png> [config.yaml]")
        sys.exit(1)
    screenshot = sys.argv[1]
    cfg = sys.argv[2] if len(sys.argv) > 2 else "config/default.yaml"
    calibrate(screenshot, cfg)
