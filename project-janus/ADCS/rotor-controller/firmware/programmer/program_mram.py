#!/usr/bin/env python3
"""Write and verify a Bleps image through OpenOCD/GDB and the SRAM MRAM tool."""

import argparse
import hashlib
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

MRAM_SIZE = 512 * 1024
TRANSFER_CAPACITY = 16 * 1024
BOOT_SEARCH_SIZE = 4096
SRAM_START = 0x20000000
SRAM_END = 0x20082000

# RP2350 picobin metadata constants.
BLOCK_START = 0xFFFFDED3
BLOCK_END = 0xAB123579
IMAGE_TYPE_ITEM = 0x42
LAST_ITEM = 0xFF
RP2350_ARM_SECURE_EXECUTABLE = 0x1021
MAX_IMAGE_DEF_SIZE = 0x180


def validate_programmer(path):
    elf = path.read_bytes()
    if elf[:6] != b"\x7fELF\x01\x01" or len(elf) < 52:
        raise ValueError("programmer must be a little-endian ELF32 file")
    kind, machine, _, entry, phoff = struct.unpack_from("<HHIII", elf, 16)
    phsize, phnum = struct.unpack_from("<HH", elf, 42)
    if (
        kind != 2 or machine != 40 or not SRAM_START <= entry < SRAM_END
        or not entry & 1 or phsize != 32 or phoff + phsize * phnum > len(elf)
    ):
        raise ValueError("programmer must be an Arm Thumb executable linked for SRAM")
    loadable = False
    for offset in range(phoff, phoff + phsize * phnum, phsize):
        segment, _, vaddr, paddr, _, length = struct.unpack_from("<6I", elf, offset)
        if segment != 1 or length == 0:
            continue
        if vaddr != paddr or not SRAM_START <= paddr < paddr + length <= SRAM_END:
            raise ValueError("programmer has a load segment outside SRAM")
        loadable = True
    if not loadable:
        raise ValueError("programmer has no loadable SRAM segments")


def is_image_definition(image, offset):
    if struct.unpack_from("<I", image, offset)[0] != BLOCK_START:
        return False
    cursor = offset + 4
    limit = min(len(image), offset + MAX_IMAGE_DEF_SIZE)
    secure_arm = False
    while cursor + 12 <= limit:
        item = image[cursor]
        size = int.from_bytes(image[cursor + 1:cursor + (3 if item & 0x80 else 2)], "little")
        if item == LAST_ITEM:
            link, marker = struct.unpack_from("<iI", image, cursor + 4)
            next_block = offset + link
            return (
                secure_arm and size == (cursor - offset - 4) // 4 and marker == BLOCK_END
                and 0 <= next_block <= len(image) - 4 and next_block % 4 == 0
                and struct.unpack_from("<I", image, next_block)[0] == BLOCK_START
            )
        if not size:
            return False
        if item == IMAGE_TYPE_ITEM:
            secure_arm = size == 1 and struct.unpack_from("<H", image, cursor + 2)[0] == RP2350_ARM_SECURE_EXECUTABLE
        cursor += 4 * size
    return False


def check_image(image):
    if not 20 <= len(image) <= MRAM_SIZE:
        raise ValueError("image must fit in the 512 KiB MRAM")
    offsets = [
        offset for offset in range(0, min(len(image) - 3, BOOT_SEARCH_SIZE), 4)
        if is_image_definition(image, offset)
    ]
    if len(offsets) != 1:
        raise ValueError("expected exactly one secure Arm RP2350 IMAGE_DEF in the first 4 KiB")
    return offsets[0]


def check_halt(commands):
    commands.extend([
        "if ((unsigned long)$pc & ~1) != ((unsigned long)&mram_programmer_ready & ~1)",
        r'  printf "Programmer stopped unexpectedly at PC 0x%lx\n", (unsigned long)$pc',
        "  quit 1",
        "end",
    ])


def issue_request(commands, operation, address, length):
    commands.extend([
        f"set variable mram_address = {address}",
        f"set variable mram_size = {length}",
        f"set variable mram_request = {operation}",
        "continue",
    ])
    check_halt(commands)
    commands.extend([
        "if mram_result != 0",
        r'  printf "MRAM error %u at address 0x%08x\n", mram_result, mram_fail_address',
        "  quit 1",
        "end",
    ])


def build_command_file(directory, image, port):
    commands = [
        "set pagination off",
        "set confirm off",
        "set remotetimeout 10",
        f"target extended-remote localhost:{port}",
        "monitor reset halt",
        "load",
        "set $pc = &_entry_point",
        "hbreak *mram_programmer_ready",
        "continue",
    ]
    check_halt(commands)

    def write_chunk(address, data):
        chunk = directory / f"write-{address:x}-{len(commands)}.bin"
        chunk.write_bytes(data)
        commands.append(f"restore {chunk} binary &mram_data")
        issue_request(commands, 2, address, len(data))

    # Invalidate the old boot search window and write the body. Stage the
    # entire new window with its IMAGE_DEF marker suppressed. The last write
    # publishes that marker only after all other image bytes passed verification.
    marker = check_image(image)
    write_chunk(0, bytes(BOOT_SEARCH_SIZE))
    for address in range(BOOT_SEARCH_SIZE, len(image), TRANSFER_CAPACITY):
        write_chunk(address, image[address:address + TRANSFER_CAPACITY])
    window = bytearray(image[:BOOT_SEARCH_SIZE])
    window[marker:marker + 4] = bytes(4)
    write_chunk(0, window)
    write_chunk(marker, image[marker:marker + 4])

    # Independent readback after writing the complete image and clearing WEL.
    readback_pieces = []
    for address in range(0, len(image), TRANSFER_CAPACITY):
        length = min(TRANSFER_CAPACITY, len(image) - address)
        issue_request(commands, 1, address, length)
        piece = directory / f"read-{address:x}.bin"
        commands.append(f"dump binary memory {piece} &mram_data ((char *)&mram_data + {length})")
        readback_pieces.append(piece)
    commands.extend(["delete breakpoints", "disconnect", "quit 0"])
    script = directory / "program.gdb"
    script.write_text("\n".join(commands) + "\n")
    return script, readback_pieces


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--programmer", type=Path, required=True, help="mram_programmer.elf")
    parser.add_argument("--image", type=Path, required=True, help="bleps_wheel.bin")
    parser.add_argument("--gdb", default="arm-none-eabi-gdb")
    parser.add_argument("--port", type=int, default=3333, help="local OpenOCD GDB port")
    parser.add_argument("--readback", type=Path, help="save the verified MRAM image")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    try:
        validate_programmer(args.programmer)
        image = args.image.read_bytes()
        check_image(image)
        with tempfile.TemporaryDirectory(prefix="bleps-mram-", dir="/tmp") as temp:
            script, pieces = build_command_file(Path(temp), image, args.port)
            result = subprocess.run(
                [args.gdb, "-q", "-nx", "-batch", str(args.programmer), "-x", str(script)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                timeout=180, check=False,
            )
            if result.returncode:
                sys.stderr.write(result.stdout)
                return 1
            readback = b"".join(piece.read_bytes() for piece in pieces)
        if readback != image:
            raise ValueError("full MRAM readback differs from the requested image")
        if args.readback:
            args.readback.write_bytes(readback)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"MRAM programming failed: {error}", file=sys.stderr)
        return 1
    digest = hashlib.sha256(readback).hexdigest()
    print(f"Verified {len(readback)} bytes, SHA-256 {digest}. Power cycle to boot.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
