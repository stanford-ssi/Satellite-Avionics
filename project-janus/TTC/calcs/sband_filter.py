"""Plot the Yapling FL401 filter from Mini-Circuits' measured two-port sweeps.

Run with Python, NumPy and Matplotlib: python sband_filter.py --output fl401.png
An offline copy of the manufacturer's ZIP may be supplied with --archive.
"""

from argparse import ArgumentParser
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

import matplotlib.pyplot as plt
import numpy as np

SOURCE = 'https://www.minicircuits.com/pages/s-params/LFCN-2500%2B_S2P.zip'
ARCHIVE_SHA256 = 'f0e7ad2a43b974c2ea321796aa53511dc4a23caa13166923a38910c373be4cbd'
CENTER_MHZ = 2437  # Illustrative channel. Frequency coordination is pending.
OCCUPIED_MHZ = 22
EDGES = np.array([CENTER_MHZ - OCCUPIED_MHZ / 2, CENTER_MHZ + OCCUPIED_MHZ / 2])


def read_sweeps(archive):
    if sha256(archive).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('The vendor archive differs from the reviewed two-unit sweep.')
    sweeps = []
    with ZipFile(BytesIO(archive)) as files:
        for unit in (1, 2):
            lines = files.read(f'LFCN-2500+_UNIT {unit}.S2P').decode('ascii').splitlines()
            if '# MHZ S DB R 50' not in lines:
                raise ValueError('Expected a 50-ohm Touchstone sweep in MHz and dB.')
            rows = [row for row in lines if row.strip() and not row.startswith(('!', '#'))]
            frequency, s21_db = np.loadtxt(rows, usecols=(0, 3), unpack=True)
            sweeps.append((frequency, -s21_db))
    return sweeps


def band_losses(sweeps, harmonic=1):
    """Keep measured interior points and linearly interpolate in dB at band edges."""
    low, high = harmonic * EDGES
    loss = []
    for freq, il in sweeps:
        loss.extend(il[(low < freq) & (freq < high)])
        loss.extend(np.interp([low, high], freq, il))
    return np.array([min(loss), max(loss)])


def draw(sweeps, output):
    plt.rcParams.update({'font.size': 8, 'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.labelcolor': '#273944', 'xtick.color': '#273944',
                         'ytick.color': '#273944', 'axes.edgecolor': '#76858c'})
    fig, (band, wide) = plt.subplots(1, 2, figsize=(8.1, 2.08),
                                    gridspec_kw={'width_ratios': [1.33, 1]})
    fig.subplots_adjust(left=.085, right=.984, top=.78, bottom=.29, wspace=.32)
    colors = ('#11697b', '#85532d')
    band.axvspan(*EDGES, color='#dce9eb', lw=0)
    for unit, ((freq, loss), color, marker) in enumerate(zip(sweeps, colors, ('o', 's')), 1):
        shown = (freq >= 2410) & (freq <= 2450)
        band.plot(freq[shown], loss[shown], color=color, lw=1.2, marker=marker,
                  markersize=3, label=f'Unit {unit}', zorder=3)
        wide.plot(freq / 1e3, loss, color=color, lw=.95, zorder=3)
    band.set(xlim=(2410, 2450), ylim=(.65, .75), xticks=(2410, 2420, 2430, 2440, 2450),
             yticks=(.65, .70, .75), xlabel='Frequency (MHz)', ylabel='Insertion loss (dB)')
    band.legend(frameon=False, loc='upper left', handlelength=1.6, fontsize=7, borderpad=0)
    band.set_title('Downlink band', fontsize=9, fontweight='bold', loc='left', pad=8)
    band.text(1, 1.09, '2426–2448 MHz example channel', transform=band.transAxes,
              ha='right', fontsize=7.5, color='#385963')
    wide.set(xlim=(2, 8), ylim=(-1, 90), xticks=(2, 4, 6, 8), yticks=(0, 40, 80),
             xlabel='Frequency (GHz)', ylabel='Insertion loss (dB)')
    wide.set_title('Harmonic rejection', fontsize=9, fontweight='bold', loc='left', pad=8)
    for harmonic, xytext in ((2, (5.0, 11)), (3, (7.25, 10))):
        freq, loss = sweeps[0]
        x = harmonic * CENTER_MHZ
        y = np.interp(x, freq, loss)
        wide.plot(x / 1e3, y, 'o', ms=3, color='#263c47', zorder=4)
        wide.annotate(f'{harmonic}×  {y:.0f} dB', xy=(x / 1e3, y), xytext=xytext,
                      ha='center', fontsize=7.5,
                      arrowprops={'arrowstyle': '-', 'lw': .65, 'color': '#415660'})
    for ax in (band, wide):
        ax.grid(axis='y', color='#c2cdd0', lw=.45)
        ax.tick_params(length=3, width=.6)
    loss_min, loss_max = band_losses(sweeps)
    passed_min, passed_max = 100 * 10 ** (-np.array([loss_max, loss_min]) / 10)
    fig.text(.085, .025, 'Mini-Circuits TB-270  ·  50 Ω  ·  −10 dBm drive', fontsize=8)
    fig.text(.984, .025, f'{passed_min:.1f}–{passed_max:.1f}% power through FL401 in example channel',
             fontsize=8, ha='right')
    fig.savefig(output, dpi=220, transparent=True)
    plt.close(fig)


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='output plot (PNG for KiCad)')
    parser.add_argument('--archive', type=Path, help='local Mini-Circuits S2P ZIP')
    args = parser.parse_args()
    if args.archive:
        data = args.archive.read_bytes()
    else:
        with urlopen(SOURCE, timeout=20) as response:
            data = response.read()
    sweeps = read_sweeps(data)
    for harmonic in (1, 2, 3):
        low, high = band_losses(sweeps, harmonic)
        print(f'{harmonic}× occupied span: {low:.3f} to {high:.3f} dB filter insertion loss')
    if args.output:
        draw(sweeps, args.output)
