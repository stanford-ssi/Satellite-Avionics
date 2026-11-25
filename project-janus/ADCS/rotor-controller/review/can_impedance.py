"""Estimate the differential impedance of Finertia's uniform L1 CAN pair.

Run with Python 3, NumPy and SciPy. Example:
    python can_impedance.py --width 115 --gap 395 --step 2

All physical dimensions are micrometres. The conductor and soldermask profiles
follow JLCPCB's published impedance calculator assumptions. Connector and
IC breakouts, lands, etch tolerance and dielectric dispersion are outside the
2-D model. Check the manufactured pair on a coupon for a measured value.
"""
import argparse

import numpy as np
from scipy.constants import c, epsilon_0
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve


def mesh_axis(intervals):
    nodes = [0.0]
    for limit, pitch in intervals:
        if limit <= nodes[-1]:
            continue
        count = int(np.ceil((limit - nodes[-1]) / pitch))
        nodes.extend(np.linspace(nodes[-1], limit, count + 1)[1:])
    return np.asarray(nodes)


def differential_impedance(width, gap, step):
    substrate = 116.4
    copper = 40.64
    etch_per_side = 8.89
    mask_on_copper = 15.24
    mask_between = 30.48
    near_edge = gap / 2
    far_edge = near_edge + width
    lateral_ground = far_edge + 400
    x = mesh_axis([(near_edge, step), (far_edge, step), (far_edge + 80, step),
                   (lateral_ground, 6), (1000, 12), (2000, 25), (4000, 50)])
    y = mesh_axis([(substrate, step), (substrate + mask_between, step),
                   (substrate + copper, step), (substrate + copper + mask_on_copper, step),
                   (370, 2 * step), (860, 12), (1700, 25), (4000, 50)])
    xx, yy = np.meshgrid(x, y)
    inset = np.clip((yy - substrate) / copper, 0, 1) * etch_per_side
    metal_height = (yy >= substrate) & (yy <= substrate + copper)
    driven = (xx >= near_edge + inset) & (xx <= far_edge - inset) & metal_height
    fixed = driven | ((xx >= lateral_ground + inset) & metal_height)
    # Odd symmetry at x=0 and grounded reference at y=0.
    fixed[[0, -1], :] = True
    fixed[:, [0, -1]] = True

    xc, yc = np.meshgrid((x[1:] + x[:-1]) / 2, (y[1:] + y[:-1]) / 2)
    above_copper = ((xc >= near_edge) & (xc <= far_edge)) | (xc >= lateral_ground)
    in_mask = ((yc < substrate + mask_between) |
               (above_copper & (yc < substrate + copper + mask_on_copper)))
    relative_eps = np.where(yc < substrate, 4.16, np.where(in_mask, 3.8, 1.0))
    index = np.arange(xx.size).reshape(xx.shape)
    a = np.r_[index[:, :-1].ravel(), index[:-1].ravel()]
    b = np.r_[index[:, 1:].ravel(), index[1:].ravel()]
    dx = np.diff(x)[None, :]
    dy = np.diff(y)[:, None]
    free = ~fixed.ravel()

    def capacitance(material):
        # Half of each adjacent dielectric cell contributes to a mesh face.
        horizontal = material * dy
        vertical = material * dx
        gx = (np.pad(horizontal, ((0, 1), (0, 0))) +
              np.pad(horizontal, ((1, 0), (0, 0)))) / (2 * dx)
        gy = (np.pad(vertical, ((0, 0), (0, 1))) +
              np.pad(vertical, ((0, 0), (1, 0)))) / (2 * dy)
        g = np.r_[gx.ravel(), gy.ravel()]
        matrix = coo_matrix((np.r_[g, g, -g, -g],
                             (np.r_[a, b, a, b], np.r_[a, b, b, a])),
                            shape=(xx.size, xx.size)).tocsr()
        potential = driven.ravel().astype(float)
        potential[free] = spsolve(matrix[free, :][:, free], -(matrix[free, :] @ potential))
        return epsilon_0 * (potential @ (matrix @ potential))

    odd_mode = capacitance(relative_eps)
    vacuum = capacitance(np.ones_like(relative_eps))
    return 2 / (c * np.sqrt(odd_mode * vacuum))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=float, default=115)
    parser.add_argument("--gap", type=float, default=395)
    parser.add_argument("--step", type=float, default=2)
    args = parser.parse_args()
    print(f"{differential_impedance(args.width, args.gap, args.step):.2f} ohm differential")
