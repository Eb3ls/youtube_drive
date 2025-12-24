import os
import numpy as np
import subprocess as sp

W, H = 256, 144
FPS = 24


def create_header(filename: str, data_size: int) -> bytes:

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


def decode_header(buf: bytes) -> dict[str, int | str]:

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


def read_video(filename: str) -> bytes:

    if not os.path.exists(filename):
        raise FileNotFoundError(f"Video file {filename} not found")

    command = [
        "ffmpeg",
        "-loglevel",
        "error",
        "-i",
        filename,
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


def data2video(data: np.ndarray, filename="output.mp4"):

    if data.ndim != 4:
        raise ValueError("Data must be a 4D numpy array")
    if data.shape[1:] != (H, W, 3):
        raise ValueError(f"Data shape must be (N, {H}, {W}, 3)")

    command = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
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
        "-c:v",
        "ffv1",
        filename,
    ]

    proc = sp.Popen(command, stdin=sp.PIPE)
    try:
        proc.communicate(input=data.tobytes())
    except Exception as e:
        print(f"Error during ffmpeg processing: {e}")

    if proc.returncode != 0:
        raise RuntimeError("FFmpeg failed to write video")

    print(f"Video saved as {filename}")


def data2file(data: bytes):
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("Data must be bytes or bytearray")

    header_len = int.from_bytes(data[0:4], "little")
    print(f"Header length: {header_len} bytes")

    header_bytes = data[0:header_len]
    try:
        header = decode_header(header_bytes)
    except TypeError as e:
        print(f"Error decoding header: {e}")
        return

    payload = int(header["payload"])
    file_data = data[header_len : header_len + payload]
    filename = f"{header['name']}_restored.{header['ext']}"

    with open(filename, "wb") as f:
        f.write(file_data)

    print(f"File saved as {filename}")


if __name__ == "__main__":
    filename = "example.txt"
    with open(filename, "rb") as f:
        data = f.read()

    data = np.frombuffer(data, dtype=np.uint8)
    header = create_header(filename, data.size)
    data = np.concatenate((np.frombuffer(header, dtype=np.uint8), data))

    # calculate number of complete 3-channel pixels
    frame_size = H * W * 3
    missing_values = frame_size - (data.size % frame_size)
    if missing_values != 0:
        # adding missing values as zeros
        data = np.concatenate((data, np.zeros(missing_values, dtype=np.uint8)))

    data_array = data.reshape((-1, H, W, 3))

    # data to video with ffmpeg
    data2video(data_array, filename="output.mkv")

    # video to file
    raw_data = read_video("output.mkv")
    data2file(raw_data)
