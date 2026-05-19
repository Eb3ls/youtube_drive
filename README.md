# YouTube Drive

Proof-of-concept that uses YouTube as unlimited cloud storage. Encodes arbitrary files into video format, uploads them as private videos, and retrieves and decodes them back to the original file.

> **Disclaimer:** This project is for educational and research purposes only. Using YouTube as a file storage system likely violates YouTube's Terms of Service. The author is not responsible for any account bans, data loss, or other consequences. Use at your own risk.

## Features

- AES-EAX encryption before upload
- Zstandard compression to minimize file size
- Reed-Solomon error correction to handle YouTube's video compression artifacts
- PyQt6 GUI for upload, download, and delete
- Playwright for automated browser interaction with YouTube Studio

## How it works

Files go through a multi-stage pipeline before upload:

1. **Compression** — zstandard
2. **Encryption** — AES-EAX with a locally generated key
3. **Error correction** — Reed-Solomon codes added to the data stream
4. **Video encoding** — binary data converted to black/white pixel blocks, rendered to MP4 via ffmpeg
5. **Upload** — video uploaded to YouTube as a private video

Retrieval works in reverse: download, extract frames, decode blocks, correct errors, decrypt, decompress.

## Requirements

- Python 3.8+
- FFmpeg installed and available in PATH

## Installation

```bash
pip install -r requirements.txt
playwright install firefox
```

## Usage

```bash
python app.py
```

A Firefox window will open. Log in to YouTube Studio when prompted — the session is saved locally in `yt_cookies.json` for future runs.

> **Keep `aes_key.bin` safe.** It is generated automatically on first run and used to encrypt all your files. If you lose it, uploaded files become unrecoverable.

> **`yt_cookies.json`** stores your YouTube session in plain text. It is gitignored — never share or commit this file.

## Limitations

- The file list only shows videos visible in the current YouTube Studio page — accounts with many videos may not see all files.
- Encoding large files is slow (ffmpeg with `veryslow` preset).
- Depends on YouTube Studio's DOM structure — UI changes may break automation.

## Author

Leonardo Berselli
