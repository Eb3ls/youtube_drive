import os
import numpy as np
import subprocess as sp
import reedsolo
from Crypto.Cipher import AES
from zstandard import ZstdCompressor, ZstdDecompressor

# yt needs at least 32 frames to allow the upload
# this value should be adjusted based on the data size
W, H = 640, 360
BLOCK_SIZE = 2
W_BLOCKS = W // BLOCK_SIZE
H_BLOCKS = H // BLOCK_SIZE
BITS_PER_FRAME = W_BLOCKS * H_BLOCKS
BYTES_PER_FRAME = BITS_PER_FRAME // 8
# low framerate so that the video has more duration
# i think that yt has a minimum duration requirement of 1 second
# if file is small its more likely to pass the check
FPS = 6
RS_ERROR_CORRECTION_BYTES = 8
CONTAINER = "mp4"
CODEC = "libx264"
COOKIES_PATH = "youtube_cookies.json"
zstd_compressor = ZstdCompressor(level=3, write_checksum=True)
zstd_decompressor = ZstdDecompressor()


def encrypt_bytes_eax(data: bytes, key: bytes) -> bytes:
    cipher = AES.new(key, AES.MODE_EAX)
    ciphertext, tag = cipher.encrypt_and_digest(data)

    encrypted = cipher.nonce + tag + ciphertext
    total_len = len(encrypted) + 8
    encrypted = total_len.to_bytes(8, "little") + encrypted

    return encrypted


# TODO: faster interpolation and video encoding


def decrypt_bytes_eax(encrypted_data: bytes, key: bytes) -> bytes:
    total_len = int.from_bytes(encrypted_data[:8], "little")
    encrypted_data = encrypted_data[8:total_len]
    nonce = encrypted_data[:16]
    tag = encrypted_data[16:32]
    ciphertext = encrypted_data[32:]
    cipher = AES.new(key, AES.MODE_EAX, nonce=nonce)
    data = cipher.decrypt_and_verify(ciphertext, tag)
    return data


def build_file_header(filename: str, data_size: int) -> bytes:

    name, ext = os.path.splitext(os.path.basename(filename))
    ext = ext.lstrip(".")
    name_b = name.encode("utf-8")
    ext_b = ext.encode("utf-8")

    body = (
        len(name_b).to_bytes(4, "little")
        + name_b
        + len(ext_b).to_bytes(4, "little")
        + ext_b
        + data_size.to_bytes(8, "little")
        + FPS.to_bytes(1, "little")
        + W.to_bytes(2, "little")
        + H.to_bytes(2, "little")
    )

    total_len = len(body) + 4
    header = total_len.to_bytes(4, "little") + body

    return header


def parse_file_header(buf: bytes) -> dict[str, int | str]:

    if not isinstance(buf, (bytes, bytearray)):
        raise TypeError("Buffer must be bytes or bytearray")

    offset = 0
    total_len = int.from_bytes(buf[offset : offset + 4], "little")
    offset += 4

    name_len = int.from_bytes(buf[offset : offset + 4], "little")
    offset += 4
    name = buf[offset : offset + name_len].decode("utf-8")
    offset += name_len

    ext_len = int.from_bytes(buf[offset : offset + 4], "little")
    offset += 4
    ext = buf[offset : offset + ext_len].decode("utf-8")
    offset += ext_len

    data_size = int.from_bytes(buf[offset : offset + 8], "little")
    offset += 8

    fps = int.from_bytes(buf[offset : offset + 1], "little")
    offset += 1

    width = int.from_bytes(buf[offset : offset + 2], "little")
    offset += 2

    height = int.from_bytes(buf[offset : offset + 2], "little")
    offset += 2

    return {
        "total_len": total_len,
        "name": name,
        "ext": ext,
        "payload": data_size,
        "fps": fps,
        "width": width,
        "height": height,
    }


def load_raw_video(video_path: str) -> bytes:

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file {video_path} not found")

    command = [
        "ffmpeg",
        "-loglevel",
        "error",
        # input options
        "-i",
        video_path,
        # output options
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-",
    ]

    proc = sp.Popen(command, stdout=sp.PIPE, stderr=sp.DEVNULL)
    if proc.stdout is None:
        raise RuntimeError("Failed to open ffmpeg stdout pipe")

    raw_video, _ = proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError("FFmpeg failed to read video")

    return raw_video


def bytes_to_video_file(data: bytes, filename: str):

    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("Data must be bytes or bytearray")

    array = np.frombuffer(data, dtype=np.uint8)
    if array.size % (W * H * 3) != 0:
        raise ValueError("Data size is not compatible with video dimensions")

    array = array.reshape((-1, H, W, 3))

    command = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        # input options
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{W}x{H}",
        "-r",
        str(FPS),
        "-i",
        "-",
        # output options
        "-c:v",
        CODEC,
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "veryslow",
        "-crf",
        "18",
        "-movflags",
        "+faststart",
        filename,
    ]

    proc = sp.Popen(command, stdin=sp.PIPE)
    try:
        proc.communicate(input=array.tobytes())
    except Exception as e:
        print(f"Error during ffmpeg processing: {e}")

    if proc.returncode != 0:
        raise RuntimeError("FFmpeg failed to write video")

    print(f"Video saved as {filename}")


def bytes_to_output_file(data: bytes):
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("Data must be bytes or bytearray")

    header_len = int.from_bytes(data[0:4], "little")

    header_bytes = data[0:header_len]
    try:
        header = parse_file_header(header_bytes)
    except TypeError as e:
        print(f"Error decoding header: {e}")
        return

    payload = int(header["payload"])
    file_data = data[header_len : header_len + payload]
    filename = f"{header['name']}.{header['ext']}"

    # avoid overwriting existing files
    if os.path.exists(filename):
        base, ext = os.path.splitext(filename)
        count = 1
        while True:
            new_filename = f"{base}_{count}{ext}"
            if not os.path.exists(new_filename):
                filename = new_filename
                break
            count += 1

    # decompression
    file_data = zstd_decompressor.decompress(file_data)

    with open(filename, "wb") as f:
        f.write(file_data)


def expand_bits_to_frames(data: bytes) -> bytes:
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))

    # padding bits to make complete frames
    total_bits = len(bits)
    remainder = total_bits % BITS_PER_FRAME
    if remainder != 0:
        padding = BITS_PER_FRAME - remainder
        bits = np.concatenate((bits, np.zeros(padding, dtype=np.uint8)))

    # if we don't have enough bits for at least FPS frames, pad more
    total_bits = len(bits)
    total_frames = total_bits // BITS_PER_FRAME
    if total_frames < FPS:
        needed_frames = FPS - total_frames
        padding_bits = needed_frames * BITS_PER_FRAME
        bits = np.concatenate((bits, np.zeros(padding_bits, dtype=np.uint8)))

    bits_array = bits.reshape(-1, H_BLOCKS, W_BLOCKS, 1)

    expanded = bits_array.repeat(BLOCK_SIZE, axis=1).repeat(BLOCK_SIZE, axis=2)

    expanded = expanded * 255

    final_array = expanded.repeat(3, axis=3)

    return final_array.tobytes()


def collapse_frames_to_bits(data: bytes) -> bytes:

    array = np.frombuffer(data, dtype=np.uint8)
    array = array.reshape(-1, H, W, 3)

    gray = array.mean(axis=3)

    blocks = gray.reshape(-1, H_BLOCKS, BLOCK_SIZE, W_BLOCKS, BLOCK_SIZE)

    block_means = blocks.mean(axis=(2, 4))

    bits = (block_means > 127).astype(np.uint8)

    bytes_data = np.packbits(bits.flatten())

    return bytes_data.tobytes()


def encode_reed_solomon(rsc: reedsolo.RSCodec, data: bytes) -> bytes:
    encoded_data = rsc.encode(data)
    encoded_data = bytes(encoded_data)

    total_bytes = len(encoded_data)
    encoded_data = total_bytes.to_bytes(8, "little") + encoded_data
    total_bytes += 8

    remainder = total_bytes % BYTES_PER_FRAME
    if remainder != 0:
        padding = BYTES_PER_FRAME - remainder
        encoded_data += bytes([0] * padding)

    return encoded_data


def decode_reed_solomon(rsc: reedsolo.RSCodec, data: bytes) -> bytes:
    total_bytes = int.from_bytes(data[:8], "little")
    data = data[8 : 8 + total_bytes]
    decoded_data, _, _ = rsc.decode(data)
    return bytes(decoded_data)


def convert_file_to_video(
    filename: str, out_filename: str, key: bytes, rsc: reedsolo.RSCodec
):
    with open(filename, "rb") as f:
        data = f.read()

    # compression
    data = zstd_compressor.compress(data)

    header = build_file_header(filename, len(data))
    data = header + data
    # encryption
    data = encrypt_bytes_eax(data, key)
    # encode with Reed-Solomon
    encoded_data = encode_reed_solomon(rsc, data)
    # interpolation to video frames
    video_data = expand_bits_to_frames(encoded_data)
    # saving to video file
    bytes_to_video_file(video_data, filename=out_filename)
    print(f"Generated video file: {out_filename}")


def extract_file_from_video(video_path: str, key: bytes, rsc: reedsolo.RSCodec):
    # reading video
    raw_video = load_raw_video(video_path)
    # de-interpolation to bit stream
    recovered_stream = collapse_frames_to_bits(raw_video)
    # decode with Reed-Solomon
    decoded_data = decode_reed_solomon(rsc, recovered_stream)
    # decryption
    decrypted_data = decrypt_bytes_eax(decoded_data, key)
    # saving restored file
    bytes_to_output_file(decrypted_data)
    # deleting temporary video file
    os.remove(video_path)
