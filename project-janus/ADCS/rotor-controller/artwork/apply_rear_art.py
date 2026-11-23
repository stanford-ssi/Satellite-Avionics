#!/usr/bin/env python3
"""Place the approved full-resolution PNG on B.SilkS in a separate KiCad 10 PCB."""
import argparse
from pathlib import Path
import tempfile

import contourpy
import numpy as np
import pcbnew as pcb
from PIL import Image

GROUP = "Waterline Eclipse"
SOURCE = Path(__file__).resolve().parents[1] / "review/art-concepts/Anableps-Waterline-Eclipse.png"
TOLERANCE = pcb.FromMM(0.006)
CLEARANCE = pcb.FromMM(0.20)


def box_polygon(bounds, padding):
    box = pcb.BOX2I(bounds.GetOrigin(), bounds.GetSize())
    box.Inflate(padding)
    polygon = pcb.SHAPE_POLY_SET()
    polygon.NewOutline()
    for corner in (box.GetOrigin(), pcb.VECTOR2I(box.GetRight(), box.GetTop()),
                   box.GetEnd(), pcb.VECTOR2I(box.GetLeft(), box.GetBottom())):
        polygon.Append(corner)
    return polygon


def board_outline(board):
    area = pcb.SHAPE_POLY_SET()
    if not board.GetBoardPolygonOutlines(area, False, None, False, True):
        raise ValueError("Cannot determine the board outline and shaft aperture")
    return area


def printable_area(board, area):
    area = pcb.SHAPE_POLY_SET(area)
    corner_style = pcb.CORNER_STRATEGY_ROUND_ALL_CORNERS
    area.Inflate(-CLEARANCE, corner_style, TOLERANCE)
    keepout = pcb.SHAPE_POLY_SET()

    for footprint in board.GetFootprints():
        courtyard = footprint.GetCourtyard(pcb.B_CrtYd)
        # M1 has separate rear spacer-seat circles even though the footprint is on F.Cu.
        # J101 is an unpopulated pogo landing. Its temporary cable body occupies the
        # courtyard only during programming. Mask each pad, guide hole and pin-1 mark.
        if footprint.GetReference() != "J101" and courtyard.OutlineCount():
            space = pcb.SHAPE_POLY_SET(courtyard)
            space.Inflate(CLEARANCE, corner_style, TOLERANCE)
            keepout.BooleanAdd(space)
        graphics = list(footprint.GraphicalItems()) + list(footprint.GetFields())
        for item in graphics:
            if item.GetLayer() == pcb.B_SilkS and (not hasattr(item, "IsVisible") or item.IsVisible()):
                keepout.BooleanAdd(box_polygon(item.GetBoundingBox(), CLEARANCE))
            elif item.GetLayer() == pcb.B_Mask:
                keepout.BooleanAdd(box_polygon(item.GetBoundingBox(), CLEARANCE))
        for pad in footprint.Pads():
            if pad.GetLayerSet().Contains(pcb.B_Mask):
                margin = max(0, pad.GetSolderMaskExpansion(pcb.B_Mask))
                pad.TransformShapeToPolygon(keepout, pcb.B_Mask, CLEARANCE + margin, TOLERANCE, pcb.ERROR_OUTSIDE)
            if pad.HasDrilledHole():
                pad.TransformHoleToPolygon(keepout, CLEARANCE, TOLERANCE, pcb.ERROR_OUTSIDE)

    for item in board.GetDrawings():
        if item.GetLayer() == pcb.B_SilkS:
            keepout.BooleanAdd(box_polygon(item.GetBoundingBox(), CLEARANCE))
    # Reserve exposed vias and free-standing bottom mask graphics on the release board.
    # Subtract these separately so final routing may add tented or untented vias.
    for item in board.GetTracks():
        if isinstance(item, pcb.PCB_VIA):
            if item.GetLayerSet().Contains(pcb.B_Cu) and not item.IsTented(pcb.B_Cu):
                margin = max(0, item.GetSolderMaskExpansion())
                item.TransformShapeToPolygon(keepout, pcb.B_Cu, CLEARANCE + margin, TOLERANCE, pcb.ERROR_OUTSIDE)
        elif item.GetLayer() == pcb.B_Cu and item.HasSolderMask():
            item.TransformShapeToPolygon(keepout, pcb.B_Mask, CLEARANCE, TOLERANCE, pcb.ERROR_OUTSIDE)
    for item in board.GetDrawings():
        if item.GetLayer() == pcb.B_Mask:
            keepout.BooleanAdd(box_polygon(item.GetBoundingBox(), CLEARANCE))
    area.BooleanSubtract(keepout)
    return area


def import_png(board, image_path):
    # A standard Gerber legend has one ink. Threshold the supplied pixels once at
    # native resolution and interpolate the boundary; no erosion, redraw or resize.
    with Image.open(image_path) as image:
        rgba = np.asarray(image.convert("RGBA"), dtype=float) / 255
    gray = (rgba[:, :, 0] * .299 + rgba[:, :, 1] * .587 + rgba[:, :, 2] * .114) * rgba[:, :, 3]
    # Quarter-turn counterclockwise in the rear view puts the open water below the shaft.
    gray = np.rot90(gray)
    outline = board_outline(board)
    bounds = outline.BBox()
    width, height = bounds.GetWidth(), bounds.GetHeight()
    if abs(width - pcb.FromMM(26)) > pcb.FromMM(.02) or abs(height - pcb.FromMM(26)) > pcb.FromMM(.02):
        raise ValueError("Artwork registration expects the 26 × 26 mm Finertia outline")
    ny, nx = gray.shape
    # Stored PNG is already a rear view. One X mirror maps it into KiCad board coordinates.
    dx, dy = width / nx, height / ny
    xs = bounds.GetRight() - (np.arange(-1, nx + 1) + 0.5) * dx
    ys = bounds.GetTop() + (np.arange(-1, ny + 1) + 0.5) * dy
    generator = contourpy.contour_generator(x=xs, y=ys, z=np.pad(gray, 1), fill_type="OuterOffset")
    vertices, offsets = generator.filled(.45, 1.01)
    ink = pcb.SHAPE_POLY_SET()
    for points, rings in zip(vertices, offsets):
        polygon = ink.NewOutline()
        for index, (start, stop) in enumerate(zip(rings[:-1], rings[1:])):
            hole = ink.NewHole(polygon) if index else -1
            for x, y in np.rint(points[start:stop - 1]).astype(int):
                ink.Append(int(x), int(y), polygon, hole)
    ink.BooleanIntersection(printable_area(board, outline))
    ink.Fracture()
    group = pcb.PCB_GROUP(board)
    group.SetName(GROUP)
    board.Add(group)
    for index in range(ink.OutlineCount()):
        shape = pcb.PCB_SHAPE(board)
        region = pcb.SHAPE_POLY_SET()
        region.AddOutline(ink.COutline(index))
        shape.SetShape(pcb.SHAPE_T_POLY)
        shape.SetPolyShape(region)
        shape.SetFilled(True)
        shape.SetWidth(0)
        shape.SetLayer(pcb.B_SilkS)
        board.Add(shape)
        group.AddItem(shape)
    return ink.OutlineCount()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("working_pcb", type=Path)
    parser.add_argument("release_pcb", type=Path, help="New path in a copy of the project")
    args = parser.parse_args()
    source = args.working_pcb.resolve(strict=True)
    dest = args.release_pcb.resolve()
    if dest == source or dest.exists() or dest.suffix != ".kicad_pcb":
        parser.error("Choose a new .kicad_pcb output path distinct from the working board")
    board = pcb.LoadBoard(str(source))
    if any(group.GetName() == GROUP for group in board.Groups()):
        parser.error("The input board already contains the artwork group")
    count = import_png(board, SOURCE)
    if not count:
        raise ValueError("No printable ink remains")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
        output = Path(tmp) / dest.name
        if not pcb.SaveBoard(str(output), board):
            raise OSError("KiCad failed to save the artwork board")
        output.rename(dest)
    print(f"Placed {count} native rear legend regions from {SOURCE.name} in {dest}")


if __name__ == "__main__":
    main()
