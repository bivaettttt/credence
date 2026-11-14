from pathlib import Path
from xml.etree import ElementTree as xml

MODEL = "http://www.omg.org/spec/BPMN/20100524/MODEL"
DIAGRAM = "http://www.omg.org/spec/BPMN/20100524/DI"
DC = "http://www.omg.org/spec/DD/20100524/DC"
DI = "http://www.omg.org/spec/DD/20100524/DI"

for prefix, namespace in (("bpmn", MODEL), ("bpmndi", DIAGRAM), ("dc", DC), ("di", DI)):
    xml.register_namespace(prefix, namespace)


def element(parent, namespace, tag, **attributes):
    return xml.SubElement(parent, f"{{{namespace}}}{tag}", attributes)


def render(name, stages, branches=()):
    root = xml.Element(
        f"{{{MODEL}}}definitions", {"id": "Credence", "targetNamespace": "urn:credence"}
    )
    process = element(root, MODEL, "process", id="Flow", isExecutable="false")
    diagram = element(root, DIAGRAM, "BPMNDiagram", id="View")
    plane = element(diagram, DIAGRAM, "BPMNPlane", id="Plane", bpmnElement="Flow")
    nodes = [("Start", "startEvent", "", 20, 112, 36, 36)]
    links = []
    previous = "Start"
    for index, stage in enumerate(stages):
        identifier = f"Task{index}"
        nodes.append((identifier, "task", stage, 95 + index * 185, 90, 150, 80))
        links.append((previous, identifier, ""))
        previous = identifier
    end_x = 95 + len(stages) * 185
    if branches:
        nodes.append(("Gateway", "exclusiveGateway", "Outcome", end_x, 105, 50, 50))
        links.append((previous, "Gateway", ""))
        for index, (condition, task) in enumerate(branches):
            y = 45 + index * 150
            nodes.extend(
                [
                    (f"Outcome{index}", "task", task, end_x + 115, y, 155, 80),
                    (f"End{index}", "endEvent", "", end_x + 310, y + 22, 36, 36),
                ]
            )
            links.extend(
                [
                    ("Gateway", f"Outcome{index}", condition),
                    (f"Outcome{index}", f"End{index}", ""),
                ]
            )
    else:
        nodes.append(("End", "endEvent", "", end_x, 112, 36, 36))
        links.append((previous, "End", ""))
    geometry = {}
    for key, tag, label, x, y, width, height in nodes:
        element(process, MODEL, tag, id=key, name=label)
        shape = element(plane, DIAGRAM, "BPMNShape", id=key + "Shape", bpmnElement=key)
        element(
            shape,
            DC,
            "Bounds",
            x=str(x),
            y=str(y),
            width=str(width),
            height=str(height),
        )
        geometry[key] = (x, y, width, height)
    for index, (source, target, label) in enumerate(links):
        key = f"Edge{index}"
        element(
            process,
            MODEL,
            "sequenceFlow",
            id=key,
            sourceRef=source,
            targetRef=target,
            name=label,
        )
        edge = element(plane, DIAGRAM, "BPMNEdge", id=key + "Diagram", bpmnElement=key)
        x, y, w, h = geometry[source]
        tx, ty, _, th = geometry[target]
        points = [(x + w, y + h // 2), (tx, ty + th // 2)]
        if source == "Gateway":
            points[1:1] = [(x + w + 25, y + h // 2), (x + w + 25, ty + th // 2)]
        for px, py in points:
            element(edge, DI, "waypoint", x=str(px), y=str(py))
    xml.indent(root)
    Path(f"docs/diagrams/{name}.bpmn").write_text(
        xml.tostring(root, encoding="unicode") + "\n"
    )


render(
    "submit",
    [
        "Edit draft and add documents",
        "Check membership and revision",
        "Evaluate pinned product rules",
    ],
    [
        ("Complete", "Commit snapshot and SUBMITTED"),
        ("Incomplete", "Return failed checks"),
    ],
)
render(
    "validate",
    [
        "Claim submitted application",
        "Confirm snapshot checklist",
        "Save document evidence",
        "Store risk factors",
    ],
)
render(
    "supplement",
    [
        "Request additional information",
        "Clear current evidence and notify applicant",
        "Amend draft and documents",
        "Submit fresh snapshot",
    ],
)
render(
    "decide",
    ["Analyst records recommendation", "Risk officer checks current evidence"],
    [
        ("Approve", "Commit decision and offer"),
        ("Reject", "Record rejection"),
        ("Return", "Open analyst review"),
    ],
)
