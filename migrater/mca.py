from io import BufferedReader, BufferedWriter
import itertools
from typing import NamedTuple
import zlib
from itertools import islice, chain, repeat

MCA_CHUNK_LENGTH = 32
MCA_CHUNKS = MCA_CHUNK_LENGTH**2
MCA_CHUNKS_4 = MCA_CHUNKS * 4
MCA_SECTOR = 4096

type ChunkXY = tuple[int, int]
type ChunkOffset = int
type ChunkSectors = int
type ChunkSize = int
type ChunkTimestamp = int
type ChunkCompressionType = int
type ChunkCompressedData = bytes
MCAHeaderEntry = NamedTuple(
    "MCAHeaderEntry",
    [
        ("chunk_offset", "ChunkOffset"),
        ("chunk_sectors", "ChunkSectors"),
        ("chunk_timestamp", "ChunkTimestamp"),
    ],
)


class MCACompressor:
    def __init__(self, mca_f: BufferedReader, *, lazy=False):
        self._mca_f = mca_f
        self._mca_data: bytes | None = None
        self._header: dict[ChunkXY, MCAHeaderEntry] | None = None
        self._buffer = bytearray()
        if not lazy:
            self._mca_data = mca_f.read()

    def _read_bytes(self, offset: int, size: int) -> bytes:
        if self._mca_data:
            return self._mca_data[offset : offset + size]
        else:
            self._mca_f.seek(offset)
            bs = self._mca_f.read(size)
            return bs

    def _read_header(self):
        if not self._header:

            def get_x_y(idx: int) -> ChunkXY:
                return (idx % MCA_CHUNK_LENGTH, idx // MCA_CHUNK_LENGTH)

            def get_offset_sectors(bs: bytes) -> tuple[ChunkOffset, ChunkSectors]:
                return (
                    int.from_bytes(bs[0:3], byteorder="big"),
                    int.from_bytes(bs[3:4], byteorder="big"),
                )

            def get_timestamp(bs: bytes) -> ChunkTimestamp:
                return int.from_bytes(bs, byteorder="big")

            header_bs = self._read_bytes(0, MCA_CHUNKS_4 * 2)
            self._header = {}
            for idx, (loc_bs, time_bs) in enumerate(
                (
                    header_bs[i : i + 4],
                    header_bs[MCA_CHUNKS_4 + i : MCA_CHUNKS_4 + i + 4],
                )
                for i in range(0, MCA_CHUNKS_4, 4)
            ):
                chunk_xy = get_x_y(idx)
                offset, sectors = get_offset_sectors(loc_bs)
                timestamp = get_timestamp(time_bs)
                if all([offset, sectors, timestamp]):
                    self._header[chunk_xy] = MCAHeaderEntry(offset, sectors, timestamp)
                else:
                    assert not any([offset, sectors, timestamp]), (
                        f"{chunk_xy=}; {offset, sectors, timestamp=}"
                    )
        return self._header

    def _convert_to(self, target_compression_type: int, mca_f: BufferedWriter):
        def get_chunk(
            offset: ChunkOffset, sectors: ChunkSectors
        ) -> tuple[ChunkSize, ChunkCompressionType, ChunkCompressedData]:
            bs = self._read_bytes(offset * MCA_SECTOR, sectors * MCA_SECTOR)
            size = int.from_bytes(bs[0:4], byteorder="big")
            compression_type = int.from_bytes(bs[4:5], byteorder="big")
            compressed_data = bs[5 : 4 + size]
            return (size, compression_type, compressed_data)

        header = self._read_header()
        new_header_loc_buffer = bytearray()
        new_header_time_buffer = bytearray()
        new_chunks_buffer = bytearray()
        for z, x in itertools.product(range(MCA_CHUNK_LENGTH), range(MCA_CHUNK_LENGTH)):
            chunk_xy = x, z
            header_entry = header.get(chunk_xy, MCAHeaderEntry(0, 0, 0))
            is_chunk_exists = all(header_entry)

            # recard the head location of current chunk data
            head_loc = len(new_chunks_buffer)
            assert head_loc % MCA_SECTOR == 0

            if is_chunk_exists:
                # prepare converted data
                _, compression_type, original_data = get_chunk(
                    header_entry.chunk_offset, header_entry.chunk_sectors
                )
                if compression_type == target_compression_type:
                    converted_data = original_data
                else:
                    if compression_type == 2 and target_compression_type == 3:
                        converted_data = zlib.decompress(original_data)
                    elif compression_type == 3 and target_compression_type == 2:
                        converted_data = zlib.compress(original_data)
                    else:
                        raise Exception(f"unaccepted converting compose: {compression_type=} and {target_compression_type=}")
                converted_length = len(converted_data)

                # filling chunk length and compression type
                # `+1` here for:
                # > The following byte indicates the compression scheme used for chunk data, and
                # > the remaining (length-1) bytes are the compressed chunk data.
                new_chunks_buffer.extend((converted_length + 1).to_bytes(4, "big"))
                new_chunks_buffer.extend(target_compression_type.to_bytes(1, "big"))

                # filling decompressed chunk data
                sector_aligned_length = (converted_length + MCA_SECTOR - 1) & ~(
                    MCA_SECTOR - 1
                )
                target_length = sector_aligned_length - 5
                new_chunks_buffer.extend(
                    bytes(islice(chain(converted_data, repeat(0)), target_length))
                )
            else:
                sector_aligned_length = 0

            # filling header
            head_sectors_loc = (head_loc + MCA_CHUNKS_4 * 2) // MCA_SECTOR
            sectors = sector_aligned_length // MCA_SECTOR
            new_header_loc_buffer.extend(head_sectors_loc.to_bytes(3, "big"))
            new_header_loc_buffer.extend(sectors.to_bytes(1, "big"))
            new_header_time_buffer.extend(
                header_entry.chunk_timestamp.to_bytes(4, "big")
            )

        mca_f.write(new_header_loc_buffer)
        mca_f.write(new_header_time_buffer)
        mca_f.write(new_chunks_buffer)

    def decompress_to(self, mca_f: BufferedWriter):
        self._convert_to(3, mca_f)

    def compress_to(self, mca_f: BufferedWriter):
        self._convert_to(2, mca_f)

if __name__ == "__main__":
    mca_path = "/Users/authing/Desktop/ha-mc-server/migrater/r.-1.0.1-21-4.mca"
    # mca_path = "/Users/authing/Desktop/ha-mc-server/migrater/r.0.0.1-15-2.mca"
    # with (
    #     open(mca_path, "rb") as mca_f,
    #     open(mca_path + ".decompressed", "wb") as mca_f2,
    # ):
    #     decompress = MCACompressor(mca_f)
    #     decompress.decompress_to(mca_f2)
    with (
        open(mca_path + ".decompressed", "rb") as mca_f,
        open(mca_path + ".2", "wb") as mca_f2,
    ):
        decompress = MCACompressor(mca_f)
        decompress.compress_to(mca_f2)
