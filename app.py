from dash import Dash, dcc, html, Input, Output
import plotly.graph_objects as go
import pandas as pd
from PIL import Image
import math
from pathlib import Path


# =========================================================
# APPLICATION
# =========================================================

app = Dash(__name__)


# =========================================================
# LOAD FLOOR PLAN
# =========================================================

floor_plan = Image.open("assets/museum_plan.png")
width, height = floor_plan.size


# =========================================================
# LOAD DATA
# =========================================================

spatial_nodes = pd.read_csv("data/spatial_nodes.csv")
spatial_edges = pd.read_csv("data/spatial_edges.csv")

poi_nodes = pd.read_csv("data/poi_nodes.csv")
poi_edges = pd.read_csv("data/poi_edges.csv")

mo_nodes = pd.read_csv("data/mo_nodes.csv")
mo_edges = pd.read_csv("data/mo_edges.csv")

diff_nodes = pd.read_csv("data/diff_nodes.csv")
diff_edges = pd.read_csv("data/diff_edges.csv")

cross_edges = pd.read_csv("data/cross_edges.csv")


# =========================================================
# CLEAN COLUMN NAMES
# =========================================================

for df in [
    spatial_nodes,
    spatial_edges,
    poi_nodes,
    poi_edges,
    mo_nodes,
    mo_edges,
    diff_nodes,
    diff_edges,
    cross_edges
]:
    df.columns = df.columns.str.strip()


# =========================================================
# NORMALIZED COORDINATES -> PIXELS
# =========================================================

for df in [spatial_nodes, poi_nodes, mo_nodes, diff_nodes]:

    df["plot_x"] = df["x"] * width
    df["plot_y"] = df["y"] * height


# =========================================================
# GLOBAL LOOKUPS
# =========================================================

spatial_lookup = spatial_nodes.set_index("id")
poi_lookup = poi_nodes.set_index("id")
mo_lookup = mo_nodes.set_index("id")
diff_lookup = diff_nodes.set_index("id")


# =========================================================
# PAPER SCENARIO 1 — ARTWORK RELOCATION
# =========================================================
#
# Scenario data are stored outside the Python code in:
# data/scenarios/artwork_relocation.csv
#
# Expected CSV columns:
# scenario,entity,state,room,time_start,time_end
#
# Example:
# artwork_relocation,P1,P1S1,R3,09:00,12:00
# artwork_relocation,P1,P1S2,R7,12:00,16:00
#
# The persistent artwork P1 remains defined in poi_nodes.csv.
# This file defines only its successive temporal states and
# their scenario-specific rooms/validity intervals.
# =========================================================

SCENARIO_DIR = Path("data") / "scenarios"
ARTWORK_RELOCATION_FILE = SCENARIO_DIR / "artwork_relocation.csv"

if not ARTWORK_RELOCATION_FILE.exists():
    raise FileNotFoundError(
        f"Scenario file not found: {ARTWORK_RELOCATION_FILE}\n"
        "Expected: data/scenarios/artwork_relocation.csv"
    )

artwork_relocation = pd.read_csv(ARTWORK_RELOCATION_FILE)
artwork_relocation.columns = artwork_relocation.columns.str.strip()

required_scenario_columns = {
    "scenario",
    "entity",
    "state",
    "room",
    "time_start",
    "time_end"
}

missing_scenario_columns = (
    required_scenario_columns - set(artwork_relocation.columns)
)

if missing_scenario_columns:
    raise ValueError(
        "artwork_relocation.csv is missing required columns: "
        + ", ".join(sorted(missing_scenario_columns))
    )

for column in [
    "scenario",
    "entity",
    "state",
    "room",
    "time_start",
    "time_end"
]:
    artwork_relocation[column] = (
        artwork_relocation[column]
        .astype(str)
        .str.strip()
    )

artwork_relocation = artwork_relocation[
    artwork_relocation["scenario"] == "artwork_relocation"
].copy()

if artwork_relocation.empty:
    raise ValueError(
        "artwork_relocation.csv contains no row with "
        "scenario = artwork_relocation"
    )

# ---------------------------------------------------------
# Scenario time bounds, directly derived from the CSV.
# ---------------------------------------------------------

def scenario_time_to_minutes(t):
    hour, minute = map(int, str(t).split(":"))
    return hour * 60 + minute


artwork_relocation["start_min"] = (
    artwork_relocation["time_start"]
    .apply(scenario_time_to_minutes)
)

artwork_relocation["end_min"] = (
    artwork_relocation["time_end"]
    .apply(scenario_time_to_minutes)
)

SCENARIO1_T0 = int(artwork_relocation["start_min"].min())

ordered_relocation_times = (
    artwork_relocation
    .sort_values("start_min")
    .reset_index(drop=True)
)

SCENARIO1_T1 = (
    int(ordered_relocation_times.iloc[1]["start_min"])
    if len(ordered_relocation_times) >= 2
    else int(ordered_relocation_times.iloc[0]["end_min"])
)

SCENARIO1_T2 = int(artwork_relocation["end_min"].max())


# ---------------------------------------------------------
# Build Scenario 1 V_seq nodes from the CSV.
# ---------------------------------------------------------
#
# The temporal state is positioned close to the room with
# which it is associated. A small offset prevents the V_seq
# marker from completely covering the spatial V_base node.
# ---------------------------------------------------------

scenario_node_rows = []

for index, row in artwork_relocation.reset_index(drop=True).iterrows():

    room_id = row["room"]

    if room_id not in spatial_lookup.index:
        raise ValueError(
            f"Scenario room '{room_id}' does not exist "
            "in spatial_nodes.csv"
        )

    room_node = spatial_lookup.loc[room_id]

    room_x = float(room_node["x"])
    room_y = float(room_node["y"])

    # Small visual offset only. It has no semantic meaning.
    offset_x = 0.025 if index % 2 == 0 else -0.025
    offset_y = -0.025

    scenario_node_rows.append(
        {
            "id": row["state"],
            "label": row["state"],
            "name": (
                f"{row['entity']} location state in {room_id}"
            ),
            "node_type": "V_seq",
            "dimension": "poi",
            "entity_id": row["entity"],
            "time_start": row["time_start"],
            "time_end": row["time_end"],
            "symbolic_interval": (
                f"[{row['time_start']},{row['time_end']})"
            ),
            "room_id": room_id,
            "x": room_x + offset_x,
            "y": room_y + offset_y,
            "start_min": int(row["start_min"]),
            "end_min": int(row["end_min"])
        }
    )

scenario1_nodes = pd.DataFrame(scenario_node_rows)

scenario1_nodes["plot_x"] = scenario1_nodes["x"] * width
scenario1_nodes["plot_y"] = scenario1_nodes["y"] * height

scenario1_lookup = scenario1_nodes.set_index("id")


# ---------------------------------------------------------
# E_rel — each V_seq is an InstanceOf its persistent V_base.
# ---------------------------------------------------------

scenario1_rel_edges = pd.DataFrame(
    [
        {
            "id": f"S1R{i+1:02d}",
            "source": row["state"],
            "target": row["entity"],
            "edge_type": "E_rel",
            "relation": "InstanceOf"
        }
        for i, (_, row) in enumerate(
            artwork_relocation.reset_index(drop=True).iterrows()
        )
    ]
)


# ---------------------------------------------------------
# E_evol — order successive V_seq states chronologically.
# ---------------------------------------------------------

ordered_states = (
    artwork_relocation
    .sort_values("start_min")
    .reset_index(drop=True)
)

scenario1_evol_edges = pd.DataFrame(
    [
        {
            "id": f"S1E{i+1:02d}",
            "source": ordered_states.iloc[i]["state"],
            "target": ordered_states.iloc[i + 1]["state"],
            "edge_type": "E_evol",
            "relation": "evolves_to"
        }
        for i in range(len(ordered_states) - 1)
    ]
)


# ---------------------------------------------------------
# E_cross — temporal displayed_in state -> room relation.
# ---------------------------------------------------------

scenario1_cross_edges = pd.DataFrame(
    [
        {
            "id": f"S1C{i+1:02d}",
            "source": row["state"],
            "target": row["room"],
            "edge_type": "E_cross",
            "relation": "displayed_in",
            "time_start": row["time_start"],
            "time_end": row["time_end"],
            "symbolic_interval": (
                f"[{row['time_start']},{row['time_end']})"
            )
        }
        for i, (_, row) in enumerate(
            artwork_relocation.reset_index(drop=True).iterrows()
        )
    ]
)

print("\nARTWORK RELOCATION SCENARIO")
print(
    artwork_relocation[
        [
            "scenario",
            "entity",
            "state",
            "room",
            "time_start",
            "time_end"
        ]
    ]
)



# =========================================================
# PAPER SCENARIO 2 — TEMPORARY ROOM CLOSURE
# =========================================================
#
# File:
# data/scenarios/room_closure.csv
#
# Expected columns:
# scenario,entity,state,time_start,time_end,status
#
# G-SITM representation:
#   R5      = V_base : persistent room identity
#   R5S1    = V_seq  : temporally valid state affected by the update
#   R5C1    = V_diff : localized temporary closure update
#
# Relations:
#   R5S1 --InstanceOf--> R5
#   R5S1 --records (E_diff)--> R5C1
# =========================================================

ROOM_CLOSURE_FILE = SCENARIO_DIR / "room_closure.csv"

if ROOM_CLOSURE_FILE.exists():
    room_closure = pd.read_csv(ROOM_CLOSURE_FILE)
    room_closure.columns = room_closure.columns.str.strip()

    required_room_closure_columns = {
        "scenario",
        "entity",
        "state",
        "time_start",
        "time_end",
        "status"
    }

    missing = (
        required_room_closure_columns
        - set(room_closure.columns)
    )

    if missing:
        raise ValueError(
            "room_closure.csv is missing required columns: "
            + ", ".join(sorted(missing))
        )

    for column in required_room_closure_columns:
        room_closure[column] = (
            room_closure[column]
            .astype(str)
            .str.strip()
        )

    room_closure = room_closure[
        room_closure["scenario"] == "room_closure"
    ].copy()

    room_closure["start_min"] = (
        room_closure["time_start"]
        .apply(scenario_time_to_minutes)
    )

    room_closure["end_min"] = (
        room_closure["time_end"]
        .apply(scenario_time_to_minutes)
    )

else:
    room_closure = pd.DataFrame(
        columns=[
            "scenario",
            "entity",
            "state",
            "time_start",
            "time_end",
            "status",
            "start_min",
            "end_min"
        ]
    )


# ---------------------------------------------------------
# Build Scenario 2 V_seq and V_diff nodes.
# ---------------------------------------------------------

room_closure_state_rows = []
room_closure_diff_rows = []

for index, row in room_closure.reset_index(drop=True).iterrows():
    room_id = str(row["entity"]).strip()

    if room_id not in spatial_lookup.index:
        raise ValueError(
            "Room closure scenario references unknown room "
            f"'{room_id}'."
        )

    room_node = spatial_lookup.loc[room_id]
    room_x = float(room_node["x"])
    room_y = float(room_node["y"])

    # One V_seq state is introduced for the state affected by the
    # differential closure update. The suffix S1 is scenario-local.
    affected_state_id = f"{room_id}S1"

    room_closure_state_rows.append(
        {
            "id": affected_state_id,
            "label": affected_state_id,
            "name": f"{room_id} temporally valid state",
            "node_type": "V_seq",
            "dimension": "spatial",
            "entity_id": room_id,
            "status": "state affected by closure",
            "time_start": row["time_start"],
            "time_end": row["time_end"],
            "start_min": int(row["start_min"]),
            "end_min": int(row["end_min"]),
            # Visualization-only offset.
            "x": room_x - 0.030,
            "y": room_y - 0.030
        }
    )

    room_closure_diff_rows.append(
        {
            "id": row["state"],
            "label": row["state"],
            "name": f"{room_id} temporary closure update",
            "node_type": "V_diff",
            "dimension": "spatial",
            "entity_id": room_id,
            "affected_state": affected_state_id,
            "status": row["status"],
            "time_start": row["time_start"],
            "time_end": row["time_end"],
            "start_min": int(row["start_min"]),
            "end_min": int(row["end_min"]),
            # Visualization-only offset.
            "x": room_x + 0.030,
            "y": room_y - 0.030
        }
    )

room_closure_state_nodes = pd.DataFrame(room_closure_state_rows)
room_closure_nodes = pd.DataFrame(room_closure_diff_rows)

if not room_closure_state_nodes.empty:
    room_closure_state_nodes["plot_x"] = room_closure_state_nodes["x"] * width
    room_closure_state_nodes["plot_y"] = room_closure_state_nodes["y"] * height
    room_closure_state_lookup = room_closure_state_nodes.set_index("id")
else:
    room_closure_state_lookup = pd.DataFrame()

if not room_closure_nodes.empty:
    room_closure_nodes["plot_x"] = room_closure_nodes["x"] * width
    room_closure_nodes["plot_y"] = room_closure_nodes["y"] * height
    room_closure_lookup = room_closure_nodes.set_index("id")
else:
    room_closure_lookup = pd.DataFrame()


# ---------------------------------------------------------
# E_rel — affected V_seq -> persistent V_base (InstanceOf)
# ---------------------------------------------------------

room_closure_rel_edges = pd.DataFrame(
    [
        {
            "id": f"S2R{i+1:02d}",
            "source": f"{row['entity']}S1",
            "target": row["entity"],
            "edge_type": "E_rel",
            "relation": "InstanceOf",
            "time_start": row["time_start"],
            "time_end": row["time_end"]
        }
        for i, (_, row) in enumerate(
            room_closure.reset_index(drop=True).iterrows()
        )
    ]
)


# ---------------------------------------------------------
# E_diff — affected V_seq -> V_diff
# ---------------------------------------------------------

room_closure_edges = pd.DataFrame(
    [
        {
            "id": f"S2D{i+1:02d}",
            "source": f"{row['entity']}S1",
            "target": row["state"],
            "edge_type": "E_diff",
            "relation": "records",
            "time_start": row["time_start"],
            "time_end": row["time_end"]
        }
        for i, (_, row) in enumerate(
            room_closure.reset_index(drop=True).iterrows()
        )
    ]
)

print("\nROOM CLOSURE SCENARIO")
if not room_closure.empty:
    print(
        room_closure[
            [
                "scenario",
                "entity",
                "state",
                "time_start",
                "time_end",
                "status"
            ]
        ]
    )


# =========================================================
# PAPER SCENARIO 3 — TEMPORARY EXHIBITION
# =========================================================
#
# File:
# data/scenarios/temporary_exhibition.csv
#
# Expected columns:
# scenario,exhibition,state,room,time_start,time_end,poi_ids
#
# poi_ids uses ";" as separator, e.g. P4;P5;P6
# =========================================================

TEMP_EXHIBITION_FILE = (
    SCENARIO_DIR / "temporary_exhibition.csv"
)

if TEMP_EXHIBITION_FILE.exists():
    temporary_exhibition = pd.read_csv(
        TEMP_EXHIBITION_FILE
    )
    temporary_exhibition.columns = (
        temporary_exhibition.columns.str.strip()
    )

    required_temp_exhibition_columns = {
        "scenario",
        "exhibition",
        "state",
        "room",
        "time_start",
        "time_end",
        "poi_ids"
    }

    missing = (
        required_temp_exhibition_columns
        - set(temporary_exhibition.columns)
    )

    if missing:
        raise ValueError(
            "temporary_exhibition.csv is missing required columns: "
            + ", ".join(sorted(missing))
        )

    for column in required_temp_exhibition_columns:
        temporary_exhibition[column] = (
            temporary_exhibition[column]
            .astype(str)
            .str.strip()
        )

    temporary_exhibition = temporary_exhibition[
        temporary_exhibition["scenario"]
        == "temporary_exhibition"
    ].copy()

    temporary_exhibition["start_min"] = (
        temporary_exhibition["time_start"]
        .apply(scenario_time_to_minutes)
    )

    temporary_exhibition["end_min"] = (
        temporary_exhibition["time_end"]
        .apply(scenario_time_to_minutes)
    )

else:
    temporary_exhibition = pd.DataFrame(
        columns=[
            "scenario",
            "exhibition",
            "state",
            "room",
            "time_start",
            "time_end",
            "poi_ids",
            "start_min",
            "end_min"
        ]
    )


temporary_exhibition_node_rows = []

for index, row in temporary_exhibition.reset_index(
    drop=True
).iterrows():

    room_id = row["room"]

    if room_id not in spatial_lookup.index:
        raise ValueError(
            "Temporary exhibition scenario references "
            f"unknown room '{room_id}'."
        )

    room_node = spatial_lookup.loc[room_id]

    temporary_exhibition_node_rows.append(
        {
            "id": row["exhibition"],
            "label": row["exhibition"],
            "name": "Temporary exhibition",
            "node_type": "V_base",
            "dimension": "poi",
            "entity_id": row["exhibition"],
            "room_id": room_id,
            "time_start": row["time_start"],
            "time_end": row["time_end"],
            "start_min": int(row["start_min"]),
            "end_min": int(row["end_min"]),
            "poi_ids": row["poi_ids"],
            "x": float(room_node["x"]) + 0.050,
            "y": float(room_node["y"]) - 0.030
        }
    )

    temporary_exhibition_node_rows.append(
        {
            "id": row["state"],
            "label": row["state"],
            "name": "Temporary exhibition active state",
            "node_type": "V_seq",
            "dimension": "poi",
            "entity_id": row["exhibition"],
            "room_id": room_id,
            "time_start": row["time_start"],
            "time_end": row["time_end"],
            "start_min": int(row["start_min"]),
            "end_min": int(row["end_min"]),
            "poi_ids": row["poi_ids"],
            "x": float(room_node["x"]) + 0.025,
            "y": float(room_node["y"]) - 0.055
        }
    )

temporary_exhibition_nodes = pd.DataFrame(
    temporary_exhibition_node_rows
)

if not temporary_exhibition_nodes.empty:
    temporary_exhibition_nodes["plot_x"] = (
        temporary_exhibition_nodes["x"] * width
    )
    temporary_exhibition_nodes["plot_y"] = (
        temporary_exhibition_nodes["y"] * height
    )
    temporary_exhibition_lookup = (
        temporary_exhibition_nodes.set_index("id")
    )
else:
    temporary_exhibition_lookup = pd.DataFrame()


temporary_exhibition_rel_edges = []
temporary_exhibition_cross_edges = []

for i, (_, row) in enumerate(
    temporary_exhibition.reset_index(drop=True).iterrows()
):

    exhibition_id = row["exhibition"]
    state_id = row["state"]
    room_id = row["room"]

    temporary_exhibition_rel_edges.append(
        {
            "id": f"S3R{i+1:02d}",
            "source": state_id,
            "target": exhibition_id,
            "edge_type": "E_rel",
            "relation": "InstanceOf",
            "time_start": row["time_start"],
            "time_end": row["time_end"]
        }
    )

    temporary_exhibition_cross_edges.append(
        {
            "id": f"S3C{i+1:02d}",
            "source": state_id,
            "target": room_id,
            "edge_type": "E_cross",
            "relation": "displayed_in",
            "time_start": row["time_start"],
            "time_end": row["time_end"]
        }
    )

    poi_ids = [
        p.strip()
        for p in str(row["poi_ids"]).split(";")
        if p.strip()
    ]

    for j, poi_id in enumerate(poi_ids):

        if poi_id not in poi_lookup.index:
            raise ValueError(
                "Temporary exhibition scenario references "
                f"unknown POI '{poi_id}'."
            )

        temporary_exhibition_rel_edges.append(
            {
                "id": f"S3P{i+1:02d}_{j+1:02d}",
                "source": poi_id,
                "target": exhibition_id,
                "edge_type": "E_rel",
                "relation": "part_of",
                "time_start": row["time_start"],
                "time_end": row["time_end"]
            }
        )

        temporary_exhibition_cross_edges.append(
            {
                "id": f"S3X{i+1:02d}_{j+1:02d}",
                "source": poi_id,
                "target": room_id,
                "edge_type": "E_cross",
                "relation": "displayed_in",
                "time_start": row["time_start"],
                "time_end": row["time_end"]
            }
        )

temporary_exhibition_rel_edges = pd.DataFrame(
    temporary_exhibition_rel_edges
)

temporary_exhibition_cross_edges = pd.DataFrame(
    temporary_exhibition_cross_edges
)


def interval_is_active(start_min, end_min, selected_time):
    """Half-open temporal validity: [start, end)."""
    return (
        int(start_min)
        <= int(selected_time)
        < int(end_min)
    )


def active_room_closure_rows(selected_time):
    if room_closure.empty:
        return room_closure.copy()

    return room_closure[
        (room_closure["start_min"] <= selected_time)
        &
        (selected_time < room_closure["end_min"])
    ].copy()


def active_temporary_exhibition_rows(selected_time):
    if temporary_exhibition.empty:
        return temporary_exhibition.copy()

    return temporary_exhibition[
        (temporary_exhibition["start_min"] <= selected_time)
        &
        (selected_time < temporary_exhibition["end_min"])
    ].copy()


# =========================================================
# HELPER
# DRAW EDGE + HOVER ALONG THE ENTIRE EDGE
# =========================================================

def add_edge_with_hover(
    fig,
    source_node,
    target_node,
    edge,
    color,
    width=2,
    dash="solid"
):

    x1 = float(source_node["plot_x"])
    y1 = float(source_node["plot_y"])

    x2 = float(target_node["plot_x"])
    y2 = float(target_node["plot_y"])

    edge_id = str(edge["id"])
    source = str(edge["source"])
    target = str(edge["target"])
    edge_type = str(edge["edge_type"])
    relation = str(edge["relation"])

    time_start = ""
    time_end = ""

    if "time_start" in edge.index and pd.notna(edge["time_start"]):
        time_start = str(edge["time_start"]).strip()

    if "time_end" in edge.index and pd.notna(edge["time_end"]):
        time_end = str(edge["time_end"]).strip()

    if time_start and time_end:
        hover_text = (
            f"<b>Relation: {relation}</b><br>"
            f"Edge ID: {edge_id}<br>"
            f"Source: {source}<br>"
            f"Target: {target}<br>"
            f"Edge type: {edge_type}<br>"
            f"<b>Validity:</b> [{time_start}, {time_end})"
        )
    else:
        hover_text = (
            f"<b>Relation: {relation}</b><br>"
            f"Edge ID: {edge_id}<br>"
            f"Source: {source}<br>"
            f"Target: {target}<br>"
            f"Edge type: {edge_type}"
        )


    # -----------------------------------------------------
    # VISIBLE EDGE
    # -----------------------------------------------------

    fig.add_trace(
        go.Scatter(
            x=[x1, x2],
            y=[y1, y2],

            mode="lines",

            line=dict(
                color=color,
                width=width,
                dash=dash
            ),

            hoverinfo="skip",

            showlegend=False
        )
    )


    # -----------------------------------------------------
    # INVISIBLE HOVER POINTS
    # -----------------------------------------------------

    number_of_hover_points = 30

    hover_x = []
    hover_y = []

    for i in range(number_of_hover_points + 1):

        ratio = i / number_of_hover_points

        hover_x.append(
            x1 + ratio * (x2 - x1)
        )

        hover_y.append(
            y1 + ratio * (y2 - y1)
        )


    hover_texts = [hover_text for _ in hover_x]

    fig.add_trace(
        go.Scatter(
            x=hover_x,
            y=hover_y,

            mode="markers",

            marker=dict(
                size=14,
                color="rgba(0,0,0,0.01)"
            ),

            text=hover_texts,

            hovertemplate="%{text}<extra></extra>",

            showlegend=False
        )
    )


# =========================================================
# HELPER
# E_EVOL WITH ARROW
# =========================================================

def add_evolution_edge(
    fig,
    source_node,
    target_node,
    edge
):

    color = "#4F9D55"

    add_edge_with_hover(
        fig=fig,
        source_node=source_node,
        target_node=target_node,
        edge=edge,
        color=color,
        width=3,
        dash="solid"
    )

    x1 = float(source_node["plot_x"])
    y1 = float(source_node["plot_y"])

    x2 = float(target_node["plot_x"])
    y2 = float(target_node["plot_y"])

    dx = x2 - x1
    dy = y2 - y1

    distance = math.sqrt(
        dx ** 2 + dy ** 2
    )

    if distance == 0:
        return

    ux = dx / distance
    uy = dy / distance

    target_offset = 18

    arrow_x = x2 - ux * target_offset
    arrow_y = y2 - uy * target_offset

    fig.add_annotation(
        x=arrow_x,
        y=arrow_y,

        ax=x1,
        ay=y1,

        xref="x",
        yref="y",

        axref="x",
        ayref="y",

        text="",

        showarrow=True,

        arrowhead=3,
        arrowsize=1.2,
        arrowwidth=2.5,
        arrowcolor=color
    )


# =========================================================
# TEMPORAL HELPERS
# =========================================================

def time_to_minutes(t):
    """
    Convert a time value to minutes since midnight.

    Accepted examples:
        10:03
        10:03:00
        " 10:03 "
        603
        603.0

    Returns None for empty/invalid values.
    """
    if pd.isna(t):
        return None

    if isinstance(t, (int, float)):
        return int(t)

    value = str(t).strip()

    if value == "":
        return None

    parts = value.split(":")

    try:
        if len(parts) >= 2:
            hour = int(parts[0])
            minute = int(parts[1])
            return hour * 60 + minute

        return int(float(value))

    except (TypeError, ValueError):
        return None


def minutes_to_time(value):
    """Convert minutes since midnight into HH:MM."""
    value = int(round(value))
    hour = value // 60
    minute = value % 60
    return f"{hour:02d}:{minute:02d}"


# =========================================================
# BUILD FIGURE
# =========================================================

def build_figure(
    selected_dimensions,
    selected_node_types,
    selected_relations,
    selected_time,
    time_mode,
    selected_scenario
):

    selected_dimensions = selected_dimensions or []
    selected_node_types = selected_node_types or []
    selected_relations = selected_relations or []
    selected_time = selected_time if selected_time is not None else 600
    selected_time = int(float(selected_time))
    time_mode = time_mode or "all"
    selected_scenario = selected_scenario or "baseline"

    fig = go.Figure()


    # =====================================================
    # FLOOR PLAN
    # =====================================================

    fig.add_layout_image(
        dict(
            source=floor_plan,

            x=0,
            y=0,

            sizex=width,
            sizey=height,

            xref="x",
            yref="y",

            xanchor="left",
            yanchor="top",

            sizing="stretch",

            opacity=0.60,

            layer="below"
        )
    )


    # =====================================================
    # FILTER NODES
    # =====================================================

    filtered_spatial = spatial_nodes[
        spatial_nodes["node_type"].isin(
            selected_node_types
        )
    ]

    filtered_poi = poi_nodes[
        poi_nodes["node_type"].isin(
            selected_node_types
        )
    ]

    filtered_mo = mo_nodes[
        mo_nodes["node_type"].isin(
            selected_node_types
        )
    ]

    # =====================================================
    # GLOBAL MO TEMPORAL VISIBILITY
    # =====================================================
    #
    # These sets are computed outside the MO rendering block
    # because E_cross is rendered later and may refer to
    # visitor V_seq nodes even when the MO dimension itself
    # is not selected.
    # =====================================================

    all_mo_seq = mo_nodes[
        mo_nodes["node_type"] == "V_seq"
    ].copy()

    all_mo_seq_ids = set(
        all_mo_seq["id"].astype(str)
    )

    if "V_seq" not in selected_node_types:

        visible_mo_seq_ids = set()

    elif time_mode == "history":

        all_mo_seq["_start_min"] = (
            all_mo_seq["time_start"]
            .apply(time_to_minutes)
        )

        visible_mo_seq = all_mo_seq[
            all_mo_seq["_start_min"].notna()
            &
            (
                all_mo_seq["_start_min"]
                <= selected_time
            )
        ].copy()

        visible_mo_seq_ids = set(
            visible_mo_seq["id"].astype(str)
        )

    else:

        visible_mo_seq_ids = set(
            all_mo_seq["id"].astype(str)
        )


    # =====================================================
    # SPATIAL DIMENSION
    # =====================================================

    if "spatial" in selected_dimensions:


        # -------------------------------------------------
        # SPATIAL E_rel
        # -------------------------------------------------

        if "E_rel" in selected_relations:

            active_closed_rooms = set()

            if (
                selected_scenario == "room_closure"
                and time_mode == "history"
            ):
                active_closed_rooms = set(
                    active_room_closure_rows(
                        selected_time
                    )["entity"].astype(str)
                )

            for _, edge in spatial_edges.iterrows():

                source = str(edge["source"])
                target = str(edge["target"])

                # During a temporary closure, navigation
                # connectivity involving the closed room is
                # not valid in the selected-time configuration.
                if (
                    source in active_closed_rooms
                    or target in active_closed_rooms
                ):
                    continue

                if (
                    source in spatial_lookup.index
                    and target in spatial_lookup.index
                ):

                    source_node = spatial_lookup.loc[source]
                    target_node = spatial_lookup.loc[target]

                    add_edge_with_hover(
                        fig=fig,
                        source_node=source_node,
                        target_node=target_node,
                        edge=edge,
                        color="#5277B8",
                        width=3
                    )


        # -------------------------------------------------
        # SPATIAL NODES
        # -------------------------------------------------

        if not filtered_spatial.empty:

            fig.add_trace(
                go.Scatter(
                    x=filtered_spatial["plot_x"],
                    y=filtered_spatial["plot_y"],

                    mode="markers+text",

                    marker=dict(
                        size=28,
                        color="#FFF2CD",

                        line=dict(
                            color="#D8A62A",
                            width=1.5
                        )
                    ),

                    text=filtered_spatial["label"],

                    textposition="middle center",

                    textfont=dict(
                        size=10,
                        color="black"
                    ),

                    name="Spatial V_base",

                    customdata=filtered_spatial[
                        [
                            "id",
                            "node_type",
                            "dimension",
                            "x",
                            "y"
                        ]
                    ].values,

                    hovertemplate=(
                        "<b>Spatial node %{text}</b><br>"
                        "ID: %{customdata[0]}<br>"
                        "Node type: %{customdata[1]}<br>"
                        "Dimension: %{customdata[2]}<br>"
                        "x: %{customdata[3]:.3f}<br>"
                        "y: %{customdata[4]:.3f}"
                        "<extra></extra>"
                    )
                )
            )


    # =====================================================
    # POI DIMENSION
    # =====================================================

    if "poi" in selected_dimensions:


        # -------------------------------------------------
        # POI E_rel
        # -------------------------------------------------

        if "E_rel" in selected_relations:

            for _, edge in poi_edges.iterrows():

                source = edge["source"]
                target = edge["target"]

                if (
                    source in poi_lookup.index
                    and target in poi_lookup.index
                ):

                    source_node = poi_lookup.loc[source]
                    target_node = poi_lookup.loc[target]

                    add_edge_with_hover(
                        fig=fig,
                        source_node=source_node,
                        target_node=target_node,
                        edge=edge,
                        color="#8E6BBE",
                        width=3
                    )


        # -------------------------------------------------
        # POI NODES
        # -------------------------------------------------

        if not filtered_poi.empty:

            fig.add_trace(
                go.Scatter(
                    x=filtered_poi["plot_x"],
                    y=filtered_poi["plot_y"],

                    mode="markers+text",

                    marker=dict(
                        size=24,
                        color="#F4CCCC",

                        line=dict(
                            color="#B85450",
                            width=1.5
                        )
                    ),

                    text=filtered_poi["label"],

                    textposition="middle center",

                    textfont=dict(
                        size=9,
                        color="black"
                    ),

                    name="POI V_base",

                    customdata=filtered_poi[
                        [
                            "id",
                            "name",
                            "node_type",
                            "dimension",
                            "x",
                            "y"
                        ]
                    ].values,

                    hovertemplate=(
                        "<b>POI %{text}</b><br>"
                        "ID: %{customdata[0]}<br>"
                        "Name: %{customdata[1]}<br>"
                        "Node type: %{customdata[2]}<br>"
                        "Dimension: %{customdata[3]}<br>"
                        "x: %{customdata[4]:.3f}<br>"
                        "y: %{customdata[5]:.3f}"
                        "<extra></extra>"
                    )
                )
            )


    # =====================================================
    # SCENARIO 1 — ARTWORK RELOCATION
    # =====================================================
    #
    # Persistent artwork:
    #   P1 = V_base
    #
    # Successive temporal states:
    #   P1S1 valid in [t0,t1) and displayed_in R3
    #   P1S2 valid in [t1,t2) and displayed_in R7
    #
    # In "all" mode both states are shown.
    # In "history" mode the museum configuration at the
    # selected time is shown for this scenario, while the
    # visitor trajectories remain cumulative histories.
    # =====================================================

    if selected_scenario == "artwork_relocation":

        # -------------------------------------------------
        # DETERMINE WHICH ARTWORK STATES ARE DISPLAYED
        # -------------------------------------------------

        if time_mode == "all":

            scenario1_visible_nodes = scenario1_nodes.copy()

        else:

            # Museum configuration at selected time:
            # a temporal artwork state is visible iff
            # start <= selected_time < end.
            scenario1_visible_nodes = scenario1_nodes[
                (
                    scenario1_nodes["start_min"]
                    <= selected_time
                )
                &
                (
                    selected_time
                    < scenario1_nodes["end_min"]
                )
            ].copy()

        # Respect the global node-type selector.
        if "V_seq" not in selected_node_types:
            scenario1_visible_nodes = scenario1_visible_nodes.iloc[0:0].copy()

        scenario1_visible_ids = set(
            scenario1_visible_nodes["id"].astype(str)
        )


        # -------------------------------------------------
        # E_rel : V_seq -> V_base (InstanceOf)
        # -------------------------------------------------

        if (
            "poi" in selected_dimensions
            and "E_rel" in selected_relations
            and "V_base" in selected_node_types
        ):

            for _, edge in scenario1_rel_edges.iterrows():

                source = str(edge["source"])
                target = str(edge["target"])

                if source not in scenario1_visible_ids:
                    continue

                if (
                    source in scenario1_lookup.index
                    and target in poi_lookup.index
                ):
                    add_edge_with_hover(
                        fig=fig,
                        source_node=scenario1_lookup.loc[source],
                        target_node=poi_lookup.loc[target],
                        edge=edge,
                        color="#1F77B4",
                        width=2,
                        dash="solid"
                    )


        # -------------------------------------------------
        # E_evol : successive artwork states
        # -------------------------------------------------

        if (
            "poi" in selected_dimensions
            and "E_evol" in selected_relations
            and "V_seq" in selected_node_types
        ):

            for _, edge in scenario1_evol_edges.iterrows():

                source = str(edge["source"])
                target = str(edge["target"])

                # In the complete view, show the full
                # evolution chain.
                if time_mode == "all":

                    if (
                        source in scenario1_lookup.index
                        and target in scenario1_lookup.index
                    ):
                        add_evolution_edge(
                            fig=fig,
                            source_node=scenario1_lookup.loc[source],
                            target_node=scenario1_lookup.loc[target],
                            edge=edge
                        )

                # In temporal mode, an evolution edge is
                # displayed only once the target state has
                # appeared. This preserves chronological
                # interpretation and avoids edges to hidden nodes.
                else:

                    # In a point-in-time museum configuration, only
                    # the currently valid state is materialized.
                    # Therefore an E_evol edge is not drawn if one
                    # of its endpoint states is hidden.
                    if (
                        source in scenario1_visible_ids
                        and target in scenario1_visible_ids
                    ):
                        add_evolution_edge(
                            fig=fig,
                            source_node=scenario1_lookup.loc[source],
                            target_node=scenario1_lookup.loc[target],
                            edge=edge
                        )


        # -------------------------------------------------
        # E_cross : temporal displayed_in relation
        # -------------------------------------------------

        if (
            "poi" in selected_dimensions
            and "spatial" in selected_dimensions
            and "E_cross" in selected_relations
        ):

            for _, edge in scenario1_cross_edges.iterrows():

                source = str(edge["source"])
                target = str(edge["target"])

                if source not in scenario1_visible_ids:
                    continue

                if (
                    source in scenario1_lookup.index
                    and target in spatial_lookup.index
                ):
                    add_edge_with_hover(
                        fig=fig,
                        source_node=scenario1_lookup.loc[source],
                        target_node=spatial_lookup.loc[target],
                        edge=edge,
                        color="#9C27B0",
                        width=3,
                        dash="dot"
                    )


        # -------------------------------------------------
        # DRAW V_seq ARTWORK STATES
        # -------------------------------------------------

        if (
            "poi" in selected_dimensions
            and not scenario1_visible_nodes.empty
        ):

            fig.add_trace(
                go.Scatter(
                    x=scenario1_visible_nodes["plot_x"],
                    y=scenario1_visible_nodes["plot_y"],

                    mode="markers+text",

                    marker=dict(
                        size=25,
                        color="#6FA8DC",
                        line=dict(
                            color="#2F5597",
                            width=2
                        )
                    ),

                    text=scenario1_visible_nodes["label"],
                    textposition="middle center",

                    textfont=dict(
                        size=8,
                        color="black"
                    ),

                    name="POI V_seq — Artwork relocation",

                    customdata=scenario1_visible_nodes[
                        [
                            "id",
                            "entity_id",
                            "room_id",
                            "time_start",
                            "time_end",
                            "symbolic_interval",
                            "node_type"
                        ]
                    ].values,

                    hovertemplate=(
                        "<b>Artwork temporal state %{text}</b><br>"
                        "ID: %{customdata[0]}<br>"
                        "Persistent entity: %{customdata[1]}<br>"
                        "Displayed in: %{customdata[2]}<br>"
                        "Validity: %{customdata[5]}<br>"
                        "Demo time: [%{customdata[3]}, %{customdata[4]})<br>"
                        "Node type: %{customdata[6]}"
                        "<extra></extra>"
                    )
                )
            )



    # =====================================================
    # SCENARIO 2 — TEMPORARY ROOM CLOSURE
    # =====================================================
    #
    # R5S1 (V_seq) --InstanceOf--> R5 (V_base)
    # R5S1 (V_seq) --records (E_diff)--> R5C1 (V_diff)
    # =====================================================

    if selected_scenario == "room_closure":

        # -------------------------------------------------
        # Determine visible V_seq and V_diff nodes.
        # -------------------------------------------------

        if time_mode == "all":
            closure_visible_diff_nodes = room_closure_nodes.copy()
            closure_visible_state_nodes = room_closure_state_nodes.copy()
        else:
            active_closures = active_room_closure_rows(selected_time)

            active_diff_ids = set(
                active_closures["state"].astype(str)
            )

            active_state_ids = set(
                active_closures["entity"].astype(str) + "S1"
            )

            if not room_closure_nodes.empty:
                closure_visible_diff_nodes = room_closure_nodes[
                    room_closure_nodes["id"]
                    .astype(str)
                    .isin(active_diff_ids)
                ].copy()
            else:
                closure_visible_diff_nodes = room_closure_nodes.copy()

            if not room_closure_state_nodes.empty:
                closure_visible_state_nodes = room_closure_state_nodes[
                    room_closure_state_nodes["id"]
                    .astype(str)
                    .isin(active_state_ids)
                ].copy()
            else:
                closure_visible_state_nodes = room_closure_state_nodes.copy()

        # Respect the global node-type selector.
        if "V_diff" not in selected_node_types:
            closure_visible_diff_nodes = (
                closure_visible_diff_nodes.iloc[0:0].copy()
            )

        if "V_seq" not in selected_node_types:
            closure_visible_state_nodes = (
                closure_visible_state_nodes.iloc[0:0].copy()
            )

        closure_visible_diff_ids = (
            set(closure_visible_diff_nodes["id"].astype(str))
            if not closure_visible_diff_nodes.empty
            else set()
        )

        closure_visible_state_ids = (
            set(closure_visible_state_nodes["id"].astype(str))
            if not closure_visible_state_nodes.empty
            else set()
        )

        # -------------------------------------------------
        # E_rel : affected V_seq -> V_base (InstanceOf)
        # -------------------------------------------------

        if (
            "spatial" in selected_dimensions
            and "E_rel" in selected_relations
            and "V_seq" in selected_node_types
            and "V_base" in selected_node_types
            and not room_closure_rel_edges.empty
        ):
            for _, edge in room_closure_rel_edges.iterrows():
                source = str(edge["source"])
                target = str(edge["target"])

                if source not in closure_visible_state_ids:
                    continue

                if (
                    source in room_closure_state_lookup.index
                    and target in spatial_lookup.index
                ):
                    add_edge_with_hover(
                        fig=fig,
                        source_node=room_closure_state_lookup.loc[source],
                        target_node=spatial_lookup.loc[target],
                        edge=edge,
                        color="#5277B8",
                        width=2,
                        dash="dot"
                    )

        # -------------------------------------------------
        # E_diff : affected V_seq -> V_diff
        # -------------------------------------------------

        if (
            "spatial" in selected_dimensions
            and "E_diff" in selected_relations
            and "V_diff" in selected_node_types
            and "V_seq" in selected_node_types
            and not room_closure_edges.empty
        ):
            for _, edge in room_closure_edges.iterrows():
                source = str(edge["source"])  # V_seq
                target = str(edge["target"])  # V_diff

                if source not in closure_visible_state_ids:
                    continue

                if target not in closure_visible_diff_ids:
                    continue

                if (
                    source in room_closure_state_lookup.index
                    and target in room_closure_lookup.index
                ):
                    add_edge_with_hover(
                        fig=fig,
                        source_node=room_closure_state_lookup.loc[source],
                        target_node=room_closure_lookup.loc[target],
                        edge=edge,
                        color="red",
                        width=3,
                        dash="solid"
                    )

        # -------------------------------------------------
        # Draw affected V_seq room state.
        # -------------------------------------------------

        if (
            "spatial" in selected_dimensions
            and "V_seq" in selected_node_types
            and not closure_visible_state_nodes.empty
        ):
            fig.add_trace(
                go.Scatter(
                    x=closure_visible_state_nodes["plot_x"],
                    y=closure_visible_state_nodes["plot_y"],
                    mode="markers+text",
                    marker=dict(
                        size=30,
                        color="#9DC3E6",
                        line=dict(
                            color="#4472C4",
                            width=2
                        )
                    ),
                    text=closure_visible_state_nodes["label"],
                    textposition="top center",
                    textfont=dict(
                        size=9,
                        color="black"
                    ),
                    name="Spatial V_seq — Affected room state",
                    customdata=closure_visible_state_nodes[
                        [
                            "id",
                            "entity_id",
                            "time_start",
                            "time_end",
                            "node_type"
                        ]
                    ].values,
                    hovertemplate=(
                        "<b>Room temporal state</b><br>"
                        "ID: %{customdata[0]}<br>"
                        "Persistent room: %{customdata[1]}<br>"
                        "Validity: [%{customdata[2]}, %{customdata[3]})<br>"
                        "Node type: %{customdata[4]}"
                        "<extra></extra>"
                    )
                )
            )

        # -------------------------------------------------
        # Draw V_diff temporary closure update.
        # -------------------------------------------------

        if (
            "spatial" in selected_dimensions
            and "V_diff" in selected_node_types
            and not closure_visible_diff_nodes.empty
        ):
            fig.add_trace(
                go.Scatter(
                    x=closure_visible_diff_nodes["plot_x"],
                    y=closure_visible_diff_nodes["plot_y"],
                    mode="markers+text",
                    marker=dict(
                        size=32,
                        color="#C9A0DC",
                        line=dict(
                            color="#7D3C98",
                            width=2
                        )
                    ),
                    text=closure_visible_diff_nodes["label"],
                    textposition="top center",
                    textfont=dict(
                        size=9,
                        color="black"
                    ),
                    name="Spatial V_diff — Room closure",
                    customdata=closure_visible_diff_nodes[
                        [
                            "id",
                            "entity_id",
                            "affected_state",
                            "status",
                            "time_start",
                            "time_end",
                            "node_type"
                        ]
                    ].values,
                    hovertemplate=(
                        "<b>Temporary room closure update</b><br>"
                        "ID: %{customdata[0]}<br>"
                        "Persistent room: %{customdata[1]}<br>"
                        "Affected V_seq: %{customdata[2]}<br>"
                        "Update: %{customdata[3]}<br>"
                        "Validity: [%{customdata[4]}, %{customdata[5]})<br>"
                        "Node type: %{customdata[6]}"
                        "<extra></extra>"
                    )
                )
            )


    # =====================================================
    # SCENARIO 3 — TEMPORARY EXHIBITION
    # =====================================================

    if selected_scenario == "temporary_exhibition":

        if time_mode == "all":
            exhibition_visible_nodes = (
                temporary_exhibition_nodes.copy()
            )
            active_exhibition_rows = (
                temporary_exhibition.copy()
            )
        else:
            active_exhibition_rows = (
                active_temporary_exhibition_rows(
                    selected_time
                )
            )

            active_exhibition_ids = set(
                active_exhibition_rows[
                    "exhibition"
                ].astype(str)
            )

            active_state_ids = set(
                active_exhibition_rows[
                    "state"
                ].astype(str)
            )

            allowed_ids = (
                active_exhibition_ids
                | active_state_ids
            )

            exhibition_visible_nodes = (
                temporary_exhibition_nodes[
                    temporary_exhibition_nodes["id"]
                    .astype(str)
                    .isin(allowed_ids)
                ].copy()
                if not temporary_exhibition_nodes.empty
                else temporary_exhibition_nodes.copy()
            )

        allowed_types = set(selected_node_types)

        if not exhibition_visible_nodes.empty:
            exhibition_visible_nodes = (
                exhibition_visible_nodes[
                    exhibition_visible_nodes[
                        "node_type"
                    ].isin(allowed_types)
                ].copy()
            )

        exhibition_visible_ids = set(
            exhibition_visible_nodes["id"].astype(str)
        ) if not exhibition_visible_nodes.empty else set()

        # E_rel inside the POI dimension:
        # E1S1 -> E1 (InstanceOf)
        # P4/P5/P6 -> E1S1 (part_of)
        if (
            "poi" in selected_dimensions
            and "E_rel" in selected_relations
            and not temporary_exhibition_rel_edges.empty
        ):

            for _, edge in (
                temporary_exhibition_rel_edges.iterrows()
            ):

                source = str(edge["source"])
                target = str(edge["target"])

                source_node = None
                target_node = None

                if source in temporary_exhibition_lookup.index:
                    source_node = (
                        temporary_exhibition_lookup.loc[source]
                    )
                elif source in poi_lookup.index:
                    source_node = poi_lookup.loc[source]

                if target in temporary_exhibition_lookup.index:
                    target_node = (
                        temporary_exhibition_lookup.loc[target]
                    )
                elif target in poi_lookup.index:
                    target_node = poi_lookup.loc[target]

                # Any temporary-exhibition endpoint must
                # currently be visible.
                if (
                    source in temporary_exhibition_lookup.index
                    and source not in exhibition_visible_ids
                ):
                    continue

                if (
                    target in temporary_exhibition_lookup.index
                    and target not in exhibition_visible_ids
                ):
                    continue

                if source_node is None or target_node is None:
                    continue

                add_edge_with_hover(
                    fig=fig,
                    source_node=source_node,
                    target_node=target_node,
                    edge=edge,
                    color="#8E6BBE",
                    width=2,
                    dash="dot"
                )

        # E_cross: active exhibition/POIs -> hosting room.
        if (
            "poi" in selected_dimensions
            and "spatial" in selected_dimensions
            and "E_cross" in selected_relations
            and not temporary_exhibition_cross_edges.empty
        ):

            for _, edge in (
                temporary_exhibition_cross_edges.iterrows()
            ):

                source = str(edge["source"])
                target = str(edge["target"])

                # In selected-time mode, there must be an
                # active exhibition interval.
                if (
                    time_mode == "history"
                    and active_exhibition_rows.empty
                ):
                    continue

                if source in temporary_exhibition_lookup.index:
                    if source not in exhibition_visible_ids:
                        continue
                    source_node = (
                        temporary_exhibition_lookup.loc[source]
                    )
                elif source in poi_lookup.index:
                    source_node = poi_lookup.loc[source]
                else:
                    continue

                if target not in spatial_lookup.index:
                    continue

                add_edge_with_hover(
                    fig=fig,
                    source_node=source_node,
                    target_node=spatial_lookup.loc[target],
                    edge=edge,
                    color="#9C27B0",
                    width=3,
                    dash="dot"
                )

        # Draw exhibition V_base / V_seq nodes.
        if (
            "poi" in selected_dimensions
            and not exhibition_visible_nodes.empty
        ):

            exhibition_base = exhibition_visible_nodes[
                exhibition_visible_nodes[
                    "node_type"
                ] == "V_base"
            ]

            exhibition_seq = exhibition_visible_nodes[
                exhibition_visible_nodes[
                    "node_type"
                ] == "V_seq"
            ]

            if not exhibition_base.empty:
                fig.add_trace(
                    go.Scatter(
                        x=exhibition_base["plot_x"],
                        y=exhibition_base["plot_y"],
                        mode="markers+text",
                        marker=dict(
                            size=30,
                            color="#FFF2CD",
                            line=dict(
                                color="#D8A62A",
                                width=2
                            )
                        ),
                        text=exhibition_base["label"],
                        textposition="middle center",
                        name="Exhibition V_base",
                        customdata=exhibition_base[
                            [
                                "id",
                                "room_id",
                                "time_start",
                                "time_end"
                            ]
                        ].values,
                        hovertemplate=(
                            "<b>Temporary exhibition</b><br>"
                            "ID: %{customdata[0]}<br>"
                            "Hosting room: %{customdata[1]}<br>"
                            "Scenario interval: "
                            "[%{customdata[2]}, %{customdata[3]})"
                            "<extra></extra>"
                        )
                    )
                )

            if not exhibition_seq.empty:
                fig.add_trace(
                    go.Scatter(
                        x=exhibition_seq["plot_x"],
                        y=exhibition_seq["plot_y"],
                        mode="markers+text",
                        marker=dict(
                            size=26,
                            color="#9DC3E6",
                            line=dict(
                                color="#4472C4",
                                width=2
                            )
                        ),
                        text=exhibition_seq["label"],
                        textposition="middle center",
                        name="Exhibition V_seq",
                        customdata=exhibition_seq[
                            [
                                "id",
                                "entity_id",
                                "room_id",
                                "time_start",
                                "time_end",
                                "poi_ids"
                            ]
                        ].values,
                        hovertemplate=(
                            "<b>Exhibition temporal state</b><br>"
                            "ID: %{customdata[0]}<br>"
                            "Persistent entity: %{customdata[1]}<br>"
                            "Room: %{customdata[2]}<br>"
                            "Validity: "
                            "[%{customdata[3]}, %{customdata[4]})<br>"
                            "POIs: %{customdata[5]}"
                            "<extra></extra>"
                        )
                    )
                )


    # =====================================================
    # MOVING OBJECT DIMENSION
    # =====================================================

    if "mo" in selected_dimensions:


        # -------------------------------------------------
        # MO TEMPORAL VISIBILITY
        # -------------------------------------------------

        mo_seq_all = filtered_mo[
            filtered_mo["node_type"] == "V_seq"
        ].copy()

        if time_mode == "history":

            # CUMULATIVE VISITOR HISTORY:
            # show every visitor state that has started
            # at or before the selected time.
            mo_seq_visible = mo_seq_all[
                mo_seq_all["id"].astype(str).isin(
                    visible_mo_seq_ids
                )
            ].copy()

        else:
            mo_seq_visible = mo_seq_all.copy()


        # -------------------------------------------------
        # MO E_rel
        # V_seq -> V_base : InstanceOf
        # -------------------------------------------------

        if "E_rel" in selected_relations:

            mo_rel_edges = mo_edges[
                mo_edges["edge_type"] == "E_rel"
            ]

            for _, edge in mo_rel_edges.iterrows():

                source = str(edge["source"])
                target = str(edge["target"])

                # In history mode, draw InstanceOf only when
                # its V_seq source has already appeared.
                if (
                    time_mode == "history"
                    and source not in visible_mo_seq_ids
                ):
                    continue

                if (
                    source in mo_lookup.index
                    and target in mo_lookup.index
                ):

                    source_node = mo_lookup.loc[source]
                    target_node = mo_lookup.loc[target]

                    add_edge_with_hover(
                        fig=fig,
                        source_node=source_node,
                        target_node=target_node,
                        edge=edge,
                        color="#5277B8",
                        width=2,
                        dash="dot"
                    )


        # -------------------------------------------------
        # MO E_evol
        # -------------------------------------------------

        if "E_evol" in selected_relations:

            mo_evolution_edges = mo_edges[
                mo_edges["edge_type"] == "E_evol"
            ]

            for _, edge in mo_evolution_edges.iterrows():

                source = str(edge["source"])
                target = str(edge["target"])

                # In "all" mode the complete trajectory is shown.
                # In history mode, E_evol appears only when
                # both endpoint states have already appeared.
                if time_mode == "history":

                    if (
                        source not in visible_mo_seq_ids
                        or target not in visible_mo_seq_ids
                    ):
                        continue

                if (
                    source in mo_lookup.index
                    and target in mo_lookup.index
                ):

                    source_node = mo_lookup.loc[source]
                    target_node = mo_lookup.loc[target]

                    add_evolution_edge(
                        fig=fig,
                        source_node=source_node,
                        target_node=target_node,
                        edge=edge
                    )


        # -------------------------------------------------
        # MO V_base
        # -------------------------------------------------

        mo_base = filtered_mo[
            filtered_mo["node_type"] == "V_base"
        ]

        if not mo_base.empty:

            fig.add_trace(
                go.Scatter(
                    x=mo_base["plot_x"],
                    y=mo_base["plot_y"],

                    mode="markers+text",

                    marker=dict(
                        size=38,
                        color="#FFF2CD",

                        line=dict(
                            color="#D8A62A",
                            width=2
                        )
                    ),

                    text=mo_base["visitor_id"],

                    textposition="middle center",

                    textfont=dict(
                        size=9,
                        color="black"
                    ),

                    name="MO V_base",

                    customdata=mo_base[
                        [
                            "id",
                            "label",
                            "visitor_id",
                            "node_type",
                            "dimension"
                        ]
                    ].values,

                    hovertemplate=(
                        "<b>%{customdata[1]}</b><br>"
                        "ID: %{customdata[0]}<br>"
                        "Visitor: %{customdata[2]}<br>"
                        "Node type: %{customdata[3]}<br>"
                        "Dimension: %{customdata[4]}"
                        "<extra></extra>"
                    )
                )
            )


        # -------------------------------------------------
        # MO V_seq
        # -------------------------------------------------

        if not mo_seq_visible.empty:

            fig.add_trace(
                go.Scatter(
                    x=mo_seq_visible["plot_x"],
                    y=mo_seq_visible["plot_y"],

                    mode="markers+text",

                    marker=dict(
                        size=30,
                        color="#9DC3E6",

                        line=dict(
                            color="#4472C4",
                            width=2
                        )
                    ),

                    text=mo_seq_visible["label"],

                    textposition="middle center",

                    textfont=dict(
                        size=8,
                        color="black"
                    ),

                    name="MO V_seq",

                    customdata=mo_seq_visible[
                        [
                            "id",
                            "visitor_id",
                            "room_id",
                            "time_start",
                            "time_end",
                            "node_type",
                            "dimension"
                        ]
                    ].values,

                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "Visitor: %{customdata[1]}<br>"
                        "Room: %{customdata[2]}<br>"
                        "<b>Temporal interval:</b> "
                        "[%{customdata[3]}, %{customdata[4]})<br>"
                        "Node type: %{customdata[5]}<br>"
                        "Dimension: %{customdata[6]}"
                        "<extra></extra>"
                    )
                )
            )

    # =====================================================
    # DIFFERENTIAL NODES — V_diff
    # =====================================================

    if "V_diff" in selected_node_types:

        if not diff_nodes.empty:

            fig.add_trace(
                go.Scatter(
                    x=diff_nodes["plot_x"],
                    y=diff_nodes["plot_y"],

                    mode="markers+text",

                    marker=dict(
                        size=32,
                        color="#C9A0DC",   # violet

                        line=dict(
                            color="#7D3C98",
                            width=2
                        )
                    ),

                    text=diff_nodes["label"],

                    textposition="top center",

                    textfont=dict(
                        size=9,
                        color="black"
                    ),

                    name="V_diff",

                    customdata=diff_nodes[
                        [
                            "id",
                            "label",
                            "dimension",
                            "time_start",
                            "time_end"
                        ]
                    ].values,

                    hovertemplate=(
                        "<b>%{customdata[1]}</b><br>"
                        "ID: %{customdata[0]}<br>"
                        "Node type: V_diff<br>"
                        "Dimension: %{customdata[2]}<br>"
                        "<b>Temporal interval:</b> "
                        "[%{customdata[3]}, %{customdata[4]})"
                        "<extra></extra>"
                    )
                )
            )
                # =====================================================
    # DIFFERENTIAL EDGES — E_diff
    # =====================================================

    if "E_diff" in selected_relations:

        for _, edge in diff_edges.iterrows():

            source = str(edge["source"]).strip()
            target = str(edge["target"]).strip()

            source_node = None
            target_node = None

            # ---------------------------------------------
            # FIND SOURCE
            # ---------------------------------------------
            if source in diff_lookup.index:
                source_node = diff_lookup.loc[source]

            elif source in spatial_lookup.index:
                source_node = spatial_lookup.loc[source]

            elif source in poi_lookup.index:
                source_node = poi_lookup.loc[source]

            elif source in mo_lookup.index:
                source_node = mo_lookup.loc[source]

            # ---------------------------------------------
            # FIND TARGET
            # ---------------------------------------------
            if target in diff_lookup.index:
                target_node = diff_lookup.loc[target]

            elif target in spatial_lookup.index:
                target_node = spatial_lookup.loc[target]

            elif target in poi_lookup.index:
                target_node = poi_lookup.loc[target]

            elif target in mo_lookup.index:
                target_node = mo_lookup.loc[target]

            # ---------------------------------------------
            # DEBUG
            # ---------------------------------------------
            if source_node is None:
                print(f"E_diff source not found: {source}")

            if target_node is None:
                print(f"E_diff target not found: {target}")

            if source_node is None or target_node is None:
                continue

            # ---------------------------------------------
            # DRAW E_diff IN RED
            # ---------------------------------------------
            add_edge_with_hover(
                fig=fig,
                source_node=source_node,
                target_node=target_node,
                edge=edge,
                color="red",
                width=3,
                dash="solid"
            )
    # =====================================================
    # CROSS-DIMENSION RELATIONS
    #
    # Supported:
    # POI -> Spatial
    # MO  -> Spatial
    # MO  -> POI
    # =====================================================

    if "E_cross" in selected_relations:

        for _, edge in cross_edges.iterrows():

            source = str(edge["source"])
            target = str(edge["target"])

            # -------------------------------------------------
            # SCENARIO 1 OVERRIDE
            # -------------------------------------------------
            # The baseline POI data contain a static location for P1.
            # During the paper's artwork-relocation scenario, that
            # static relation must be hidden and replaced by the two
            # temporally qualified displayed_in relations:
            # P1S1 -> R3 and P1S2 -> R7.
            if (
                selected_scenario == "artwork_relocation"
                and source == "P1"
                and target in spatial_lookup.index
            ):
                continue

            if (
                selected_scenario == "temporary_exhibition"
                and source in {"P4", "P5", "P6"}
                and target in spatial_lookup.index
            ):
                continue

            # -------------------------------------------------
            # TEMPORAL VISIBILITY OF MO V_seq ENDPOINTS
            # -------------------------------------------------
            # If an E_cross edge is attached to a visitor
            # sequential node, the edge must not appear before
            # that V_seq node appears in history mode.
            if time_mode == "history":

                if (
                    source in all_mo_seq_ids
                    and source not in visible_mo_seq_ids
                ):
                    continue

                if (
                    target in all_mo_seq_ids
                    and target not in visible_mo_seq_ids
                ):
                    continue

            source_node = None
            target_node = None

            source_dimension = None
            target_dimension = None


            # -------------------------------------------------
            # FIND SOURCE
            # -------------------------------------------------

            if source in spatial_lookup.index:

                source_node = spatial_lookup.loc[source]
                source_dimension = "spatial"

            elif source in poi_lookup.index:

                source_node = poi_lookup.loc[source]
                source_dimension = "poi"

            elif source in mo_lookup.index:

                source_node = mo_lookup.loc[source]
                source_dimension = "mo"


            # -------------------------------------------------
            # FIND TARGET
            # -------------------------------------------------

            if target in spatial_lookup.index:

                target_node = spatial_lookup.loc[target]
                target_dimension = "spatial"

            elif target in poi_lookup.index:

                target_node = poi_lookup.loc[target]
                target_dimension = "poi"

            elif target in mo_lookup.index:

                target_node = mo_lookup.loc[target]
                target_dimension = "mo"


            # -------------------------------------------------
            # INVALID NODE
            # -------------------------------------------------

            if source_node is None or target_node is None:
                continue


            # -------------------------------------------------
            # ONLY DISPLAY IF BOTH DIMENSIONS ARE SELECTED
            # -------------------------------------------------

            if source_dimension not in selected_dimensions:
                continue

            if target_dimension not in selected_dimensions:
                continue


            # -------------------------------------------------
            # RELATION STYLE
            # -------------------------------------------------

            relation = str(edge["relation"])


            if relation == "located_in":

                edge_color = "#9C27B0"
                edge_dash = "dot"


            elif relation == "observed":

                edge_color = "#E67E22"
                edge_dash = "dot"


            else:

                edge_color = "#666666"
                edge_dash = "dot"


            # -------------------------------------------------
            # DRAW E_cross
            # -------------------------------------------------

            add_edge_with_hover(
                fig=fig,

                source_node=source_node,

                target_node=target_node,

                edge=edge,

                color=edge_color,

                width=2,

                dash=edge_dash
            )


    # =====================================================
    # AXES
    # =====================================================

    fig.update_xaxes(
        range=[0, width],

        visible=False,

        showgrid=False,

        zeroline=False,

        fixedrange=False
    )


    fig.update_yaxes(
        range=[height, 0],

        visible=False,

        showgrid=False,

        zeroline=False,

        scaleanchor="x",

        scaleratio=1,

        fixedrange=False
    )


    # =====================================================
    # LAYOUT
    # =====================================================

    fig.update_layout(
        autosize=True,

        height=850,

        margin=dict(
            l=10,
            r=10,
            t=30,
            b=10
        ),

        paper_bgcolor="white",

        plot_bgcolor="white",

        hovermode="closest",

        hoverdistance=30,

        legend=dict(
            orientation="h",

            x=0.5,
            xanchor="center",

            y=1.02,
            yanchor="bottom"
        )
    )


    return fig


# =========================================================
# USER INTERFACE
# =========================================================


# =========================================================
# REPRESENTATIONAL VALIDATION / COMPETENCY QUESTIONS
# =========================================================

def _interval_overlap(a_start, a_end, b_start, b_end):
    """Return True iff half-open intervals [a_start,a_end) and [b_start,b_end) overlap."""
    if None in (a_start, a_end, b_start, b_end):
        return False
    return max(int(a_start), int(b_start)) < min(int(a_end), int(b_end))


def _node_interval_minutes(row):
    """Extract [start,end) minutes from a row containing time_start/time_end."""
    start = time_to_minutes(row.get("time_start", None))
    end = time_to_minutes(row.get("time_end", None))
    return start, end


def visitor_states_in_room(room_id, selected_time=None):
    """Synthetic visitor V_seq observations associated with one room."""
    rows = mo_nodes[
        (mo_nodes["node_type"] == "V_seq")
        &
        (mo_nodes["room_id"].astype(str) == str(room_id))
    ].copy()

    if rows.empty:
        return rows

    rows["_start_min"] = rows["time_start"].apply(time_to_minutes)
    rows["_end_min"] = rows["time_end"].apply(time_to_minutes)

    if selected_time is not None:
        rows = rows[
            rows["_start_min"].notna()
            &
            (rows["_start_min"] <= int(selected_time))
        ].copy()

    return rows


def visitor_states_overlapping_room_interval(room_id, interval_start, interval_end):
    """Return visitor V_seq observations in room_id overlapping [interval_start, interval_end)."""
    rows = visitor_states_in_room(room_id)
    if rows.empty:
        return rows

    mask = rows.apply(
        lambda r: _interval_overlap(
            r["_start_min"],
            r["_end_min"],
            interval_start,
            interval_end,
        ),
        axis=1,
    )
    return rows[mask].copy()


def visitor_states_overlapping_interval(interval_start, interval_end):
    """Return all visitor V_seq observations overlapping [interval_start, interval_end)."""
    rows = mo_nodes[mo_nodes["node_type"] == "V_seq"].copy()
    if rows.empty:
        return rows

    rows["_start_min"] = rows["time_start"].apply(time_to_minutes)
    rows["_end_min"] = rows["time_end"].apply(time_to_minutes)
    mask = rows.apply(
        lambda r: _interval_overlap(
            r["_start_min"],
            r["_end_min"],
            interval_start,
            interval_end,
        ),
        axis=1,
    )
    return rows[mask].copy()


def build_validation_content(selected_scenario, selected_time, time_mode):
    """
    Produce representational validation results for the paper's final CQ1-CQ6.
    This is not a performance, scalability, predictive-accuracy, or
    empirical visitor-behaviour evaluation.
    """

    t = minutes_to_time(selected_time)

    validation_note = html.Div(
        [
            html.B("Validation scope — "),
            "The scenarios and visitor trajectories are controlled, representative "
            "proof-of-concept data. The demonstrator evaluates the representational "
            "capacity of G-SITM and its ability to reconstruct temporally valid museum "
            "configurations. It does not constitute an empirical visitor-behaviour, "
            "performance, scalability, or predictive-accuracy evaluation."
        ],
        style={
            "fontSize": "12px",
            "lineHeight": "1.55",
            "padding": "10px 12px",
            "backgroundColor": "#FFF8E1",
            "border": "1px solid #DCCB91",
            "borderRadius": "6px",
            "marginTop": "10px",
            "color": "#3A3422"
        }
    )

    if selected_scenario == "baseline":
        return [
            html.Div(
                [
                    html.H4(
                        "Baseline configuration",
                        style={"margin": "0 0 6px 0", "fontSize": "15px"}
                    ),
                    html.P(
                        "Spatial entities, POIs and synthetic visitor observations "
                        "are integrated without applying a controlled dynamic event.",
                        style={"margin": "0", "color": "#333333"}
                    )
                ],
                style={
                    "padding": "10px 12px",
                    "borderLeft": "4px solid #666666",
                    "backgroundColor": "#F7F7F7",
                    "borderRadius": "4px"
                }
            ),
            validation_note
        ]

    if selected_scenario == "artwork_relocation":
        ordered = scenario1_nodes.sort_values("start_min").copy()
        active = ordered[
            (ordered["start_min"] <= selected_time)
            &
            (selected_time < ordered["end_min"])
        ]

        if active.empty:
            current = f"At {t}, no relocation state is valid."
        else:
            row = active.iloc[0]
            current = (
                f"At {t}, {row['entity_id']} is represented by {row['id']} "
                f"and displayed_in {row['room_id']}."
            )

        temporal_locations = "; ".join(
            f"{row['entity_id']} via {row['id']} → {row['room_id']} "
            f"[{row['time_start']}, {row['time_end']})"
            for _, row in ordered.iterrows()
        )

        visitor_hits = []
        for _, arow in ordered.iterrows():
            rows = visitor_states_overlapping_room_interval(
                arow["room_id"],
                int(arow["start_min"]),
                int(arow["end_min"]),
            )
            for _, s in rows.iterrows():
                visitor_hits.append(
                    f"{s['visitor_id']}:{s['id']} in {arow['room_id']} "
                    f"while {arow['id']} is valid"
                )

        cq2 = (
            ", ".join(visitor_hits)
            if visitor_hits
            else "No synthetic visitor observation temporally overlaps the relocated artwork's valid room intervals."
        )

        return [
            html.H4("Scenario 1 — Artwork relocation", style={"margin": "0 0 6px 0"}),
            html.P(current, style={"margin": "0 0 7px 0"}),
            html.Div([
                html.B("G-SITM encoding — "),
                "P1 remains V_base; location states are V_seq; E_evol orders "
                "successive states; E_cross displayed_in carries temporal validity."
            ]),
            html.Div([
                html.B("CQ1 — Cultural objects displayed in a room during an interval — "),
                temporal_locations
            ], style={"marginTop": "6px"}),
            html.Div([
                html.B("CQ2 — Visitor trajectories in previous/new artwork locations — "),
                cq2
            ], style={"marginTop": "6px"}),
            validation_note
        ]

    if selected_scenario == "room_closure":
        active = active_room_closure_rows(selected_time)
        closed_rooms = list(active["entity"].astype(str)) if not active.empty else []

        current = (
            f"At {t}, " + ", ".join(closed_rooms) + " is temporarily inaccessible."
            if closed_rooms
            else f"At {t}, no temporary room closure is active."
        )

        invalid_edges = []
        for _, e in spatial_edges.iterrows():
            s = str(e["source"])
            tg = str(e["target"])
            if s in closed_rooms or tg in closed_rooms:
                invalid_edges.append(f"{e['id']} ({s}–{tg})")

        impacted_visitor_states = []
        for _, crow in active.iterrows():
            c_start = int(crow["start_min"])
            c_end = int(crow["end_min"])
            room_id = str(crow["entity"])
            rows = visitor_states_overlapping_room_interval(room_id, c_start, c_end)
            for _, s in rows.iterrows():
                impacted_visitor_states.append(
                    f"{s['visitor_id']}:{s['id']} overlaps {room_id} closure "
                    f"[{crow['time_start']}, {crow['time_end']})"
                )

        cq3 = (
            ", ".join(invalid_edges)
            if invalid_edges
            else "No connectivity relation is invalidated at the selected time."
        )
        cq4 = (
            ", ".join(impacted_visitor_states)
            if impacted_visitor_states
            else "No synthetic visitor trajectory observation overlaps the active closure interval in the affected room."
        )

        return [
            html.H4("Scenario 2 — Temporary room closure", style={"margin": "0 0 6px 0"}),
            html.P(current, style={"margin": "0 0 7px 0"}),
            html.Div([
                html.B("G-SITM encoding — "),
                "R5 remains V_base; R5S1 is the affected V_seq; the temporary closure is V_diff; "
                "E_diff is directed from R5S1 to R5C1 with relation records; connectivity involving "
                "R5 is invalid while the closure interval is active."
            ]),
            html.Div([
                html.B("CQ3 — Inaccessible rooms/connectivity during an interval — "),
                cq3
            ], style={"marginTop": "6px"}),
            html.Div([
                html.B("CQ4 — Trajectories crossing/avoiding the affected area during closure — "),
                cq4
            ], style={"marginTop": "6px"}),
            validation_note
        ]

    if selected_scenario == "temporary_exhibition":
        active = active_temporary_exhibition_rows(selected_time)

        if active.empty:
            current = f"At {t}, no temporary exhibition is active."
            cq5 = "No temporary exhibition/POI configuration is valid at the selected time."
            cq6 = "No E1-specific change with respect to the baseline configuration at the selected time."
        else:
            row = active.iloc[0]
            pois = [p.strip() for p in str(row["poi_ids"]).split(";") if p.strip()]
            current = (
                f"At {t}, {row['exhibition']} is active in {row['room']} "
                f"during [{row['time_start']}, {row['time_end']})."
            )

            visitors = visitor_states_overlapping_interval(
                int(row["start_min"]),
                int(row["end_min"]),
            )
            if visitors.empty:
                overlap_text = "No synthetic visitor trajectory overlaps this exhibition interval."
            else:
                overlap_text = ", ".join(
                    f"{s['visitor_id']}:{s['id']}"
                    for _, s in visitors.iterrows()
                )

            cq5 = (
                f"{row['exhibition']} and POIs {', '.join(pois)} are active in {row['room']} "
                f"during [{row['time_start']}, {row['time_end']}); {overlap_text}"
            )
            cq6 = (
                f"Compared with the baseline, the valid configuration adds state {row['state']}, "
                f"part_of relations for {', '.join(pois)}, and temporally qualified displayed_in "
                f"relations to {row['room']}."
            )

        return [
            html.H4("Scenario 3 — Temporary exhibition", style={"margin": "0 0 6px 0"}),
            html.P(current, style={"margin": "0 0 7px 0"}),
            html.Div([
                html.B("G-SITM encoding — "),
                "E1 is V_base; E1S1 is its active V_seq; part_of is E_rel; "
                "displayed_in is E_cross; scenario relations carry [start,end) validity."
            ]),
            html.Div([
                html.B("CQ5 — Temporary exhibitions/POIs active during a visitor trajectory — "),
                cq5
            ], style={"marginTop": "6px"}),
            html.Div([
                html.B("CQ6 — Valid museum configuration before/after a dynamic event — "),
                cq6
            ], style={"marginTop": "6px"}),
            validation_note
        ]

    return [validation_note]


app.layout = html.Div(
    [

        # =================================================
        # TITLE
        # =================================================

        html.H1(
            "G-SITM Visualizer",

            style={
                "textAlign": "center",
                "fontFamily": "Arial",
                "marginBottom": "5px"
            }
        ),


        html.P(
            "Interactive visualization of the G-SITM museum graph",

            style={
                "textAlign": "center",
                "fontFamily": "Arial",
                "color": "#666",
                "marginTop": "0"
            }
        ),


        # =================================================
        # MAIN CONTENT
        # =================================================

        html.Div(
            [

                # =========================================
                # LEFT CONTROL PANEL
                # =========================================

                html.Div(
                    [

                        # ---------------------------------
                        # DIMENSIONS
                        # ---------------------------------

                        html.H3(
                            "Dimensions",

                            style={
                                "marginTop": "0"
                            }
                        ),


                        dcc.Checklist(
                            id="dimension-selector",

                            options=[
                                {
                                    "label": " Spatial",
                                    "value": "spatial"
                                },

                                {
                                    "label": " POI",
                                    "value": "poi"
                                },

                                {
                                    "label": " Moving Object",
                                    "value": "mo"
                                }
                            ],

                            value=[
                                "spatial",
                                "poi"
                            ],

                            labelStyle={
                                "display": "block",
                                "marginBottom": "8px"
                            }
                        ),


                        html.Hr(),


                        # ---------------------------------
                        # NODE TYPES
                        # ---------------------------------

                        html.H3(
                            "Node Types"
                        ),


                        dcc.Checklist(
                            id="node-type-selector",

                            options=[
                                {
                                    "label": " V_base",
                                    "value": "V_base"
                                },

                                {
                                    "label": " V_seq",
                                    "value": "V_seq"
                                },

                                {
                                    "label": " V_diff",
                                    "value": "V_diff"
                                }
                            ],

                            value=[
                                "V_base",
                                "V_seq",
                                "V_diff"
                            ],

                            labelStyle={
                                "display": "block",
                                "marginBottom": "8px"
                            }
                        ),


                        html.Hr(),


                        # ---------------------------------
                        # RELATIONS
                        # ---------------------------------

                        html.H3(
                            "Relations"
                        ),


                        dcc.Checklist(
                            id="relation-selector",

                            options=[
                                {
                                    "label": " E_rel",
                                    "value": "E_rel"
                                },

                                {
                                    "label": " E_evol",
                                    "value": "E_evol"
                                },

                                {
                                    "label": " E_cross",
                                    "value": "E_cross"
                                },

                                {
                                    "label": " E_diff",
                                    "value": "E_diff"
                                }
                            ],

                            value=[
                                "E_rel",
                                "E_evol",
                                "E_cross",
                                "E_diff"
                            ],

                            labelStyle={
                                "display": "block",
                                "marginBottom": "8px"
                            }
                        ),
                        html.Hr(),

                        html.H3("Scenario"),

                        dcc.RadioItems(
                            id="scenario-selector",

                            options=[
                                {
                                    "label": " Baseline",
                                    "value": "baseline"
                                },
                                {
                                    "label": " Artwork relocation",
                                    "value": "artwork_relocation"
                                },
                                {
                                    "label": " Temporary room closure",
                                    "value": "room_closure"
                                },
                                {
                                    "label": " Temporary exhibition",
                                    "value": "temporary_exhibition"
                                }
                            ],

                            value="baseline",

                            labelStyle={
                                "display": "block",
                                "marginBottom": "8px"
                            }
                        ),

                        html.Div(
                            [
                                html.Small(
                                    "Scenario data are read from data/scenarios/. "
                                    "Selected-time reconstruction shows the museum "
                                    "configuration valid at the chosen time."
                                )
                            ],
                            style={
                                "padding": "8px",
                                "backgroundColor": "#F5F5F5",
                                "borderRadius": "5px",
                                "fontSize": "12px",
                                "lineHeight": "1.4"
                            }
                        ),

                        html.Hr(),

                        html.H3("Temporal visualization"),

                        dcc.RadioItems(
                            id="time-mode",

                            options=[
                                {
                                    "label": " Show all temporal states",
                                    "value": "all"
                                },
                                {
                                    "label": " Selected-time reconstruction",
                                    "value": "history"
                                }
                            ],

                            value="all",

                            labelStyle={
                                "display": "block",
                                "marginBottom": "8px"
                            }
                        ),

                        html.Hr(),

                        html.H3("Time"),

                        dcc.Slider(
                            id="time-slider",

                            min=540,      # 09:00
                            max=960,      # 16:00
                            step=1,       # one-minute precision
                            value=600,    # 10:00

                            marks={
                                540: "09:00",
                                600: "10:00",
                                660: "11:00",
                                720: "12:00",
                                780: "13:00",
                                840: "14:00",
                                900: "15:00",
                                960: "16:00"
                            },

                            tooltip={
                                "placement": "bottom",
                                "always_visible": False
                            }
                        ),

                        html.Div(
                            id="selected-time-label",

                            style={
                                "marginTop": "15px",
                                "fontWeight": "bold",
                                "fontSize": "14px",
                                "color": "#444"
                            }
                        )

                    ],

                    style={
                        "width": "220px",

                        "minWidth": "220px",

                        "padding": "20px",

                        "border": "1px solid #DDD",

                        "borderRadius": "8px",

                        "backgroundColor": "#FAFAFA",

                        "fontFamily": "Arial",

                        "height": "fit-content"
                    }
                ),


                # =========================================
                # GRAPH
                # =========================================

                html.Div(
                    [

                        # =========================================
                        # REPRESENTATIONAL VALIDATION PANEL
                        # =========================================
                        #
                        # Placed ABOVE the graph so the validation
                        # results are visible immediately and do not
                        # fall below a large Plotly canvas.
                        # =========================================

                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.H3(
                                            "Representational validation",
                                            style={
                                                "margin": "0",
                                                "fontSize": "18px"
                                            }
                                        ),

                                        html.Span(
                                            "Proof-of-concept assessment",
                                            style={
                                                "fontSize": "12px",
                                                "fontWeight": "600",
                                                "padding": "4px 8px",
                                                "border": "1px solid #C9C9C9",
                                                "borderRadius": "12px",
                                                "backgroundColor": "white"
                                            }
                                        )
                                    ],
                                    style={
                                        "display": "flex",
                                        "justifyContent": "space-between",
                                        "alignItems": "center",
                                        "gap": "12px",
                                        "marginBottom": "10px"
                                    }
                                ),

                                html.Div(
                                    id="validation-panel",
                                    style={
                                        "minHeight": "92px"
                                    }
                                )
                            ],
                            style={
                                "marginBottom": "12px",
                                "padding": "16px",
                                "border": "1px solid #CFCFCF",
                                "borderRadius": "8px",
                                "backgroundColor": "#FFFFFF",
                                "fontFamily": "Arial",
                                "fontSize": "13px",
                                "lineHeight": "1.55",
                                "boxShadow": "0 1px 4px rgba(0,0,0,0.08)",
                                "overflow": "visible"
                            }
                        ),

                        # =========================================
                        # GRAPH
                        # =========================================

                        html.Div(
                            [
                                dcc.Graph(
                                    id="museum-graph",

                                    config={
                                        "scrollZoom": True,

                                        "displaylogo": False,

                                        "responsive": True,

                                        "modeBarButtonsToRemove": [
                                            "lasso2d",
                                            "select2d"
                                        ]
                                    },

                                    style={
                                        "width": "100%",
                                        "height": "690px"
                                    }
                                )
                            ],
                            style={
                                "border": "1px solid #E2E2E2",
                                "borderRadius": "8px",
                                "backgroundColor": "white",
                                "overflow": "hidden"
                            }
                        )

                    ],

                    style={
                        "flex": "1",
                        "minWidth": "0",
                        "overflow": "visible"
                    }
                )

            ],

            style={
                "display": "flex",

                "gap": "20px",

                "alignItems": "flex-start"
            }
        )

    ],

    style={
        "maxWidth": "1500px",
        "margin": "auto",
        "padding": "15px",
        "fontFamily": "Arial",
        "boxSizing": "border-box",
        "overflow": "visible"
    }
)


# =========================================================
# CALLBACK
# =========================================================

@app.callback(
    [
        Output(
            "museum-graph",
            "figure"
        ),

        Output(
            "selected-time-label",
            "children"
        ),

        Output(
            "validation-panel",
            "children"
        )
    ],

    [
        Input(
            "dimension-selector",
            "value"
        ),

        Input(
            "node-type-selector",
            "value"
        ),

        Input(
            "relation-selector",
            "value"
        ),

        Input(
            "time-slider",
            "value"
        ),

        Input(
            "time-mode",
            "value"
        ),

        Input(
            "scenario-selector",
            "value"
        )
    ]
)
def update_graph(
    selected_dimensions,
    selected_node_types,
    selected_relations,
    selected_time,
    time_mode,
    selected_scenario
):

    selected_time = (
        int(float(selected_time))
        if selected_time is not None
        else 600
    )

    print(
        "UPDATE GRAPH | "
        f"scenario={selected_scenario} | "
        f"time_mode={time_mode} | "
        f"selected_time={selected_time}"
    )

    figure = build_figure(
        selected_dimensions,
        selected_node_types,
        selected_relations,
        selected_time,
        time_mode,
        selected_scenario
    )

    if time_mode == "history":

        base_label = (
            "Selected time: "
            + minutes_to_time(selected_time)
            + " | Visitor trajectory history up to this time"
        )

        if selected_scenario == "artwork_relocation":

            active_state = scenario1_nodes[
                (
                    scenario1_nodes["start_min"]
                    <= selected_time
                )
                &
                (
                    selected_time
                    < scenario1_nodes["end_min"]
                )
            ]

            if not active_state.empty:
                current = active_state.iloc[0]
                scenario_state = (
                    f"{current['entity_id']} is displayed in "
                    f"{current['room_id']}"
                )
            else:
                scenario_state = (
                    "no relocation state is valid at this time"
                )

            time_label = (
                base_label
                + " | Artwork relocation: "
                + scenario_state
            )

        elif selected_scenario == "room_closure":

            active = active_room_closure_rows(
                selected_time
            )

            if not active.empty:
                row = active.iloc[0]
                scenario_state = (
                    f"{row['entity']} is {row['status']}"
                )
            else:
                scenario_state = (
                    "no room closure is active"
                )

            time_label = (
                base_label
                + " | Room closure: "
                + scenario_state
            )

        elif selected_scenario == "temporary_exhibition":

            active = active_temporary_exhibition_rows(
                selected_time
            )

            if not active.empty:
                row = active.iloc[0]
                scenario_state = (
                    f"{row['exhibition']} active in "
                    f"{row['room']} with "
                    f"{row['poi_ids']}"
                )
            else:
                scenario_state = (
                    "no temporary exhibition is active"
                )

            time_label = (
                base_label
                + " | Temporary exhibition: "
                + scenario_state
            )

        else:
            time_label = base_label

    else:

        if selected_scenario == "artwork_relocation":

            scenario_descriptions = []

            for _, row in scenario1_nodes.sort_values(
                "start_min"
            ).iterrows():
                scenario_descriptions.append(
                    f"{row['id']} displayed in "
                    f"{row['room_id']} during "
                    f"[{row['time_start']},{row['time_end']})"
                )

            time_label = (
                "Complete temporal view | Artwork relocation: "
                + "; ".join(scenario_descriptions)
            )

        elif selected_scenario == "room_closure":

            if room_closure.empty:
                time_label = (
                    "Complete temporal view | Room closure: "
                    "scenario file is empty or unavailable"
                )
            else:
                descriptions = [
                    (
                        f"{row['entity']} {row['status']} during "
                        f"[{row['time_start']},{row['time_end']})"
                    )
                    for _, row in room_closure.iterrows()
                ]

                time_label = (
                    "Complete temporal view | Room closure: "
                    + "; ".join(descriptions)
                )

        elif selected_scenario == "temporary_exhibition":

            if temporary_exhibition.empty:
                time_label = (
                    "Complete temporal view | Temporary exhibition: "
                    "scenario file is empty or unavailable"
                )
            else:
                descriptions = [
                    (
                        f"{row['exhibition']} in {row['room']} "
                        f"with {row['poi_ids']} during "
                        f"[{row['time_start']},{row['time_end']})"
                    )
                    for _, row in temporary_exhibition.iterrows()
                ]

                time_label = (
                    "Complete temporal view | Temporary exhibition: "
                    + "; ".join(descriptions)
                )

        else:
            time_label = (
                "All visitor temporal states are displayed"
            )

    validation_content = build_validation_content(
        selected_scenario=selected_scenario,
        selected_time=selected_time,
        time_mode=time_mode
    )

    return figure, time_label, validation_content


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(debug=True)