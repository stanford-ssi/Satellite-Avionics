"""Small-signal model of the protected 2S input. Run with --output DIR to save plots."""
from argparse import ArgumentParser
from itertools import product
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def parallel(*branches):
    return 1 / sum(1 / impedance for impedance in branches)


def capacitor(s, capacitance, esr, esl):
    return esr + s * esl + 1 / (s * capacitance)


def response(frequency, capacitance_scale, inductance_scale, source_r, harness_l):
    s = 2j * np.pi * frequency
    source = source_r + s * harness_l
    entrance_cap = capacitor(s, 0.86e-6 * capacitance_scale, 0.0055, 0.42e-9)
    entrance = parallel(source, entrance_cap)
    choke = 0.0132 + s * 2.2e-6 * inductance_scale
    # CL-000001 gives 9.44 µF at 8.4 V for each nominal 22 µF part.
    ceramic_pair = capacitor(s, 2 * 9.44e-6 * capacitance_scale, 0.0035 / 2, 0.5e-9 / 2)
    damped_pair = 0.68 + ceramic_pair
    zout = parallel(entrance + choke, ceramic_pair, damped_pair)
    # Inject a unit ripple current at VIN; take the fraction returning through the PDU.
    pdu_current = (zout / (entrance + choke)) * (entrance / source)
    return abs(zout), abs(pdu_current)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='directory for the two figures')
    args = parser.parse_args()
    frequency = np.geomspace(200, 5e6, 900)
    nominal = response(frequency, 1, 1, 0.050, 0.4e-6)
    corners = np.array([response(frequency, *corner) for corner in product(
        (0.8, 1.2), (0.8, 1.2), (0.025, 0.125), (0.1e-6, 1e-6))])
    input_power = (3.318 * 1 + 4.890 * 2) / 0.85
    converter_z = 6.0**2 / input_power
    worst_z = corners[:, 0].max()
    print(f'Peak filter impedance {worst_z:.3f} ohm; static converter estimate '
          f'{converter_z:.3f} ohm; separation {20*np.log10(converter_z/worst_z):.1f} dB.')
    if not args.output:
        return
    args.output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.size': 9, 'axes.spines.right': False, 'axes.spines.top': False})
    x = frequency / 1e3
    for idx, filename in enumerate(('input-impedance.png', 'conducted-current.png')):
        fig, ax = plt.subplots(figsize=(4.15, 1.9))
        envelope = corners[:, idx]
        typical = nominal[idx]
        if idx == 0:
            ax.set_yscale('log')
            ax.set(xlim=(0.2, 1000), ylim=(0.003, 5), ylabel='Impedance (Ω)')
            ax.axhline(converter_z, color='#914021', linestyle='--', lw=1)
            ax.text(0.25, 2.65, 'Converter input estimate', fontsize=7)
        else:
            typical, envelope = 20*np.log10(typical), 20*np.log10(envelope)
            ax.set(xlim=(1, 5000), ylim=(-145, 9), ylabel='Current transfer (dB)')
            ax.set_yticks([-140, -105, -70, -35, 0])
            ax.axvline(2000, color='#914021', linestyle=':', lw=1)
            ax.text(1180, -9, '2 MHz', fontsize=7)
        ax.set_xscale('log')
        ax.fill_between(x, envelope.min(axis=0), envelope.max(axis=0), color='#cbdfe1')
        ax.plot(x, typical, color='#145f69', lw=1.6)
        ax.set_xlabel('Frequency (kHz)')
        ax.grid(color='#dbe3e4', linewidth=0.5)
        fig.tight_layout(pad=0.45)
        fig.savefig(args.output / filename, dpi=160)
        plt.close(fig)


if __name__ == '__main__':
    main()
