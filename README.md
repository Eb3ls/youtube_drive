# YouTube Drive

**YouTube Drive** is a proof-of-concept application that leverages YouTube as an unlimited cloud storage solution. It encodes arbitrary files into video format, uploads them to YouTube, and allows for retrieval and decoding back to their original state.

> **⚠️ DISCLAIMER**
> This project is for **educational and research purposes only**. Using YouTube as a file storage system likely violates YouTube's Terms of Service. The author is not responsible for any account bans, data loss, or other consequences resulting from the use of this software. Use at your own risk.

## 🚀 Features

- **Infinite Storage**: Leverages YouTube's video hosting for file storage.
- **Secure**: Files are encrypted using **AES-EAX** encryption before upload.
- **Efficient**: Uses **Zstandard** compression to minimize file size.
- **Robust**: Implements **Reed-Solomon** error correction to handle YouTube's video compression artifacts.
- **User-Friendly GUI**: Built with **PyQt6** for easy file management (upload, download, delete).
- **Automated**: Uses **Playwright** for automated browser interaction with YouTube Studio.

## 🛠️ How It Works

The application transforms files through a multi-stage pipeline:

1.  **Compression**: The input file is compressed using `zstandard`.
2.  **Encryption**: The compressed data is encrypted using AES (EAX mode) with a locally generated key.
3.  **Error Correction**: Reed-Solomon error correction codes are added to the data stream to ensure data integrity against video compression.
4.  **Video Encoding**: The binary data is converted into a visual representation (black and white blocks) and rendered into a video file (MP4) using `ffmpeg`.
5.  **Upload**: The generated video is uploaded to YouTube as a private video.

Retrieval works in reverse: downloading the video, extracting frames, decoding the visual blocks, correcting errors, decrypting, and decompressing.

## 📋 Prerequisites

- **Python 3.8+**
- **FFmpeg**: Must be installed and available in your system's PATH.
