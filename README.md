# G-SITM Dynamic Museum Knowledge Graph Visualizer

An interactive proof-of-concept demonstrator for representing and exploring **Dynamic Museum Knowledge Graphs (DMKGs)** using **G-SITM**.

The application integrates indoor museum spaces, cultural heritage Points of Interest (POIs), synthetic visitor trajectories, and controlled dynamic scenarios within a unified graph representation. It is designed to support the **representational validation of G-SITM** through temporal reconstruction and competency questions.

> **Research scope:** The current prototype evaluates the representational capacity of G-SITM. The dynamic scenarios and visitor trajectories are controlled/synthetic proof-of-concept data. They must not be interpreted as historical events at the museum or as empirical observations of visitor behavior. The prototype does not evaluate scalability, runtime performance, storage efficiency, or predictive accuracy.

---

## 1. Overview

Museums are dynamic indoor environments in which artworks may be relocated, rooms may become temporarily inaccessible, temporary exhibitions may be installed, and visitors move through configurations that evolve over time.

This demonstrator represents these heterogeneous elements within a common graph and allows the user to explore either the complete temporal representation or the museum configuration reconstructed at a selected time.

The current proof of concept is instantiated using the **National Archaeological Museum of Athens** as a museum case study and integrates:

- indoor spaces and connectivity;
- cultural heritage POIs and semantic relations;
- synthetic visitor trajectories;
- cross-dimensional relations;
- temporally valid museum changes;
- competency-question-based validation.

---

## 2. G-SITM Representation

The demonstrator follows the G-SITM distinction between persistent entities, temporal states, and localized updates.

### Node Types

| Type | Meaning | Example |
|---|---|---|
| `V_base` | Persistent identity of an entity | Room, artwork, visitor, exhibition |
| `V_seq` | Temporally ordered state or observation | Artwork location state, visitor observation, active exhibition state |
| `V_diff` | Localized differential update | Temporary room closure |

### Edge Types

| Type | Meaning | Example |
|---|---|---|
| `E_rel` | Structural or semantic relation | `connected_to`, `InstanceOf`, `part_of` |
| `E_cross` | Relation across dimensions | `displayed_in`, `located_in` |
| `E_evol` | Temporal continuity between successive states | `evolves_to` |
| `E_diff` | Relation involving a differential update | `temporarily_closes` |

The visualizer follows a consistent graphical convention:

- `V_base`: yellow nodes;
- `V_seq`: blue nodes;
- `V_diff`: violet nodes;
- `E_evol`: green directed edges;
- `E_diff`: red edges.

---

## 3. Museum Dimensions

The current prototype integrates three principal dimensions.

### Spatial Dimension (`D_space`)

Represents museum rooms and their indoor connectivity.

Example:

```text
R8 --connected_to--> R7
```

Rooms are represented as persistent spatial entities.

### POI Dimension (`D_poi`)

Represents cultural heritage objects and semantic relations between them.

Examples of semantic relations include:

```text
same_artifact_class_as
same_material_as
```

POIs are connected to museum spaces through cross-dimensional relations such as:

```text
P1 --displayed_in--> R12
```

### Moving Object Dimension (`D_MO`)

Represents museum visitors as persistent moving objects and their successive observations as temporal nodes.

For example:

```text
Visitor 1
   |
   | InstanceOf
   |
V1S1 --> V1S2 --> V1S3 --> V1S4
          E_evol
```

Each `V_seq` observation can additionally be connected to the corresponding museum room through an `E_cross` relation.

---

## 4. Temporal Semantics

The application intentionally distinguishes two temporal visualization semantics.

### 4.1 Museum Configuration

Dynamic museum states and relations follow half-open interval validity:

```text
time_start <= T < time_end
```

A state or relation is therefore part of the reconstructed museum configuration only when it is valid at the selected time `T`.

Formally:

```text
valid(x, T) iff time_start(x) <= T < time_end(x)
```

This mechanism is used for:

- artwork relocation;
- temporary room closure;
- temporary exhibitions;
- other temporally qualified museum relations.

### 4.2 Visitor Trajectory History

Visitor observations use cumulative trajectory history:

```text
time_start <= T
```

Selecting a time `T` therefore displays all visitor observations that have occurred up to `T`.

This distinction is deliberate:

- museum scenarios reconstruct the **configuration valid at time `T`**;
- visitor visualization reconstructs the **trajectory history up to time `T`**.

These two temporal semantics should not be conflated.

---

## 5. Controlled Validation Scenarios

Three controlled scenarios are currently implemented to evaluate different representational mechanisms of G-SITM.

### Scenario 1 — Artwork Relocation

A persistent artwork `P1` is represented through successive temporal location states:

```text
P1S1 --> R3    [09:00, 12:00)
P1S2 --> R7    [12:00, 16:00)
```

The persistent identity is preserved:

```text
              P1
            V_base
           /      \
 InstanceOf      InstanceOf
       /            \
    P1S1  ------->  P1S2
    V_seq  E_evol   V_seq
      |               |
 displayed_in     displayed_in
      |               |
      v               v
     R3              R7
```

The scenario demonstrates:

- persistent artwork identity;
- successive temporal states;
- temporal continuity through `E_evol`;
- temporally qualified spatial relations through `E_cross`;
- reconstruction of the artwork location at a selected time.

Example temporal reconstruction:

```text
T = 11:00  ->  P1 is displayed in R3
T = 13:00  ->  P1 is displayed in R7
```

---

## 6. Scenario 2 — Temporary Room Closure

Room `R5` is temporarily closed during:

```text
[12:00, 14:00)
```

The room remains represented by its persistent node:

```text
R5 : V_base
```

The temporary closure is represented as a differential update:

```text
R5C1 : V_diff
```

connected to the affected room through:

```text
R5C1 --E_diff / temporarily_closes--> R5
```

During the interval:

```text
12:00 <= T < 14:00
```

the room is considered temporarily inaccessible and connectivity involving the closed room is excluded from the valid selected-time configuration.

The scenario demonstrates:

- preservation of room identity;
- representation of a localized temporary change;
- temporal accessibility;
- reconstruction of the valid indoor connectivity graph.

Example:

```text
T = 11:30
R5 accessible

T = 13:00
R5 temporarily closed

T = 14:00
R5 accessible again
```

---

## 7. Scenario 3 — Temporary Exhibition

A temporary exhibition `E1` is active in room `R8` during:

```text
[13:00, 15:00)
```

The controlled POI set associated with the exhibition is:

```text
P4
P5
P6
```

The exhibition is represented through a persistent identity:

```text
E1 : V_base
```

and an active temporal state:

```text
E1S1 : V_seq
```

with:

```text
E1S1 --InstanceOf--> E1
```

The active exhibition state is associated with its hosting room:

```text
E1S1 --displayed_in--> R8
```

The POIs participate in the exhibition through:

```text
P4 --part_of--> E1S1
P5 --part_of--> E1S1
P6 --part_of--> E1S1
```

and are temporarily displayed in `R8`:

```text
P4 --displayed_in--> R8
P5 --displayed_in--> R8
P6 --displayed_in--> R8
```

These scenario-specific relations are temporally valid during:

```text
[13:00, 15:00)
```

The scenario demonstrates the representation of a temporary semantic and spatial museum configuration.

---

## 8. Representational Validation

The application contains a **Representational Validation** panel that dynamically reports the interpretation of the selected scenario and time.

The validation follows the workflow:

```text
Controlled Scenario
        |
        v
G-SITM Encoding
        |
        v
Temporal Filtering
        |
        v
Valid Graph Configuration
        |
        v
Competency-Question Result
```

The objective is to determine whether G-SITM can represent and reconstruct representative museum dynamics while preserving entity identity, temporal validity, and semantic relationships.

---

## 9. Competency Questions

The proof of concept considers the following competency questions.

**CQ1.** Which cultural objects were displayed in a given room during a specified time interval?

**CQ2.** In which rooms was a given artwork displayed before and after its relocation?

**CQ3.** Which visitor trajectories occurred in the previous and new locations of a relocated artwork?

**CQ4.** Which rooms and connectivity relations were inaccessible during a specified period?

**CQ5.** Which trajectories crossed or avoided the affected area during a room closure?

**CQ6.** Which temporary exhibitions and temporary POIs were active during a visitor's trajectory?

**CQ7.** How did the valid museum configuration differ before and after a dynamic event?

These questions require joint access to temporal, spatial, cultural heritage, and moving-object information.

---

## 10. Project Structure

The repository is organized as follows:

```text
G-SITM-Visualizer/
|
|-- app.py
|-- README.md
|-- requirements.txt
|-- .gitignore
|
|-- assets/
|   |
|   `-- museum_plan.png
|
`-- data/
    |
    |-- spatial_nodes.csv
    |-- spatial_edges.csv
    |
    |-- poi_nodes.csv
    |-- poi_edges.csv
    |
    |-- mo_nodes.csv
    |-- mo_edges.csv
    |
    |-- diff_nodes.csv
    |-- diff_edges.csv
    |
    |-- cross_edges.csv
    |
    `-- scenarios/
        |
        |-- artwork_relocation.csv
        |-- room_closure.csv
        `-- temporary_exhibition.csv
```

---

## 11. Installation

### Requirements

Python **3.10 or later** is recommended.

Clone the repository:

```bash
git clone <repository-url>
cd G-SITM-Visualizer
```

Create a virtual environment:

```bash
python -m venv .venv
```

### Windows PowerShell

Activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

### Linux / macOS

```bash
source .venv/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

---

## 12. Dependencies

The minimal dependencies are:

```text
dash
plotly
pandas
pillow
```

A corresponding `requirements.txt` can therefore contain:

```text
dash
plotly
pandas
pillow
```

For a research release, dependency versions should eventually be pinned to the versions used for the final experiments.

---

## 13. Running the Application

From the repository root, run:

```bash
python app.py
```

Dash will start the local development server.

Open the address displayed in the terminal, typically:

```text
http://127.0.0.1:8050/
```

---

## 14. Using the Visualizer

The interface allows the user to control:

- displayed dimensions;
- node types;
- relation types;
- dynamic scenario;
- temporal visualization mode;
- selected time.

### Complete Temporal Representation

The **Show all temporal states** mode displays the graph representation independently of a particular reconstruction time.

### Selected-Time Reconstruction

The **Selected-time reconstruction** mode applies temporal validity according to the selected time.

For museum configuration elements:

```text
start <= T < end
```

For synthetic visitor trajectory history:

```text
time_start <= T
```

Hovering over nodes and edges provides semantic information about graph entities and relations. Temporally qualified scenario relations also expose their validity intervals.

---

## 15. Scenario Files

Dynamic scenarios are stored separately from the baseline museum data.

This separation is important because the scenarios are controlled validation cases rather than assertions about the baseline museum configuration.

### `data/scenarios/artwork_relocation.csv`

```csv
scenario,entity,state,room,time_start,time_end
artwork_relocation,P1,P1S1,R3,09:00,12:00
artwork_relocation,P1,P1S2,R7,12:00,16:00
```

### `data/scenarios/room_closure.csv`

```csv
scenario,entity,state,time_start,time_end,status
room_closure,R5,R5C1,12:00,14:00,closed
```

### `data/scenarios/temporary_exhibition.csv`

```csv
scenario,exhibition,state,room,time_start,time_end,poi_ids
temporary_exhibition,E1,E1S1,R8,13:00,15:00,P4;P5;P6
```

---

## 16. Data and Scenario Provenance

The application combines museum-oriented spatial and POI information with controlled proof-of-concept data.

The dynamic events used in the three validation scenarios are **representative scenarios** introduced to test the expressive and temporal capabilities of the model.

They should not be interpreted as documented historical events of the National Archaeological Museum of Athens.

Similarly, the visitor trajectories are synthetically generated for representational validation and do not reproduce actual visitor behavior.

---

## 17. Visitor–POI Interpretation

Particular care must be taken when interpreting visitor–POI relationships.

Spatial co-location between a visitor and a POI does not by itself demonstrate that the visitor observed, attended to, or interacted with the cultural object.

Therefore, visitor–POI interaction relations should only be interpreted as actual observations when supported by an appropriate source of evidence.

In the current proof of concept, synthetic visitor trajectories primarily demonstrate the ability of the model to integrate moving-object observations with spatial and cultural heritage entities.

---

## 18. Reproducibility Protocol

A scenario can be reproduced using the following procedure:

1. keep the baseline museum graph unchanged;
2. load the controlled scenario from `data/scenarios/`;
3. select the corresponding scenario in the interface;
4. activate **Selected-time reconstruction**;
5. select a time before the event;
6. inspect the reconstructed graph;
7. select a time during the event;
8. inspect the temporally valid configuration;
9. select a time after the event;
10. compare the resulting configurations and competency-question outputs.

For example, for the temporary room closure:

```text
11:30 -> before closure
13:00 -> during closure
14:30 -> after closure
```

This provides a simple and reproducible validation of the temporal representation.

---

## 19. Validation Scope and Limitations

The prototype is intended to validate:

- heterogeneous museum data integration;
- persistent entity identity;
- temporal state representation;
- localized differential updates;
- temporal evolution;
- cross-dimensional relationships;
- temporal validity;
- museum configuration reconstruction;
- competency-question support.

The current implementation does **not** evaluate:

- database scalability;
- query execution performance;
- storage efficiency;
- graph compression;
- predictive accuracy;
- recommendation quality;
- real visitor behavior.

These aspects require separate experimental protocols and datasets.

---

## 20. Technologies

The demonstrator is implemented in Python using:

- **Dash** — interactive web application;
- **Plotly** — graph visualization;
- **Pandas** — graph and scenario data processing;
- **Pillow** — image processing support.

---

## 21. Research Status

This repository contains a **research proof-of-concept implementation**.

It accompanies ongoing research on semantic indoor trajectories, G-SITM, and dynamic museum knowledge graphs.

The current objective is to demonstrate that heterogeneous museum entities and representative dynamic events can be encoded within a unified graph while preserving:

```text
identity
+
semantics
+
temporal validity
+
evolution
+
cross-dimensional relationships
```

---

## 22. Citation

If you use this repository or its concepts in academic work, please cite the associated publication.

The final bibliographic information will be added after publication.

```bibtex
@inproceedings{gsitm_dmkg_2026,
  title  = {Building a Dynamic Museum Knowledge Graph from Heterogeneous Cultural Heritage Data Using G-SITM},
  author = {Alaa Eddine Siouane and others},
  year   = {2026},
  note   = {Publication details to be updated}
}
```

---

## 23. License

A license has not yet been specified for the public release.

Before publishing the repository, the redistribution rights of the museum floor plan, cultural heritage data, and any other external resources included in the repository should be verified.

The software license should then be specified in a dedicated `LICENSE` file.

---

## 24. Author

**Alaa Eddine Siouane**  
PhD Researcher  
Nantes Université — LS2N  
Polytech Nantes, France

Research topic: **Semantic Indoor Trajectories and Dynamic Museum Environments**

---

## 25. Acknowledgements

This demonstrator was developed as part of doctoral research on semantic indoor trajectory modeling and dynamic museum environments.

The National Archaeological Museum of Athens is used as the museum case study for the proof-of-concept instantiation.

---

## Disclaimer

This repository is a scientific research prototype. The controlled dynamic scenarios and synthetic visitor trajectories are intended solely for model demonstration and representational validation.