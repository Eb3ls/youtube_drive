import os
import sys
from pathlib import Path
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QInputDialog,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)
from codec import (
    convert_file_to_video,
    RS_ERROR_CORRECTION_BYTES,
    CONTAINER,
    extract_file_from_video,
)
from yt_interface import (
    create_yt_istance,
    delete_video,
    upload_video_to_youtube,
    get_video_list,
    download_video,
)
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
import reedsolo


TRANSFER_TEXT = "Uploading to YT"


class FileTransferWindow(QMainWindow):
    def __init__(self, browser: Browser, context: BrowserContext, page: Page):
        super().__init__()
        self.setWindowTitle("File Transfer")
        self.resize(1024, 640)

        self.current_dir = Path.cwd()

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # single instances
        self.rsc = reedsolo.RSCodec(RS_ERROR_CORRECTION_BYTES)
        self.browser = browser
        self.context = context
        self.page = page
        self.key = self._load_or_create_key()
        # other
        self.left_status = QLabel("")
        self.left_list = QListWidget()
        self.left_list.itemDoubleClicked.connect(self.handle_local_double_click)
        self.left_search = QLineEdit()
        self.left_search.setPlaceholderText("Find local files")
        self.left_search.textChanged.connect(self.filter_local_list)
        self.dir_display = QLabel(str(self.current_dir))
        self.dir_display.setObjectName("pathLabel")
        self.dir_display.setWordWrap(True)
        self.dir_browse = QPushButton("Browse…")
        self.dir_browse.setObjectName("ghost")
        self.dir_browse.clicked.connect(self.choose_directory)
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self.dir_display, stretch=1)
        dir_layout.addWidget(self.dir_browse)
        self.load_local_items()
        left_header = QLabel("Local files")
        left_header.setObjectName("panelTitle")
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)
        left_layout.addWidget(left_header)
        left_layout.addLayout(dir_layout)
        left_layout.addWidget(self.left_search)
        left_layout.addWidget(self.left_list)
        left_layout.addWidget(self.left_status)
        left_widget = QFrame()
        left_widget.setObjectName("panel")
        left_widget.setLayout(left_layout)

        # yt list
        self.right_status = QLabel("")
        self.right_list = QListWidget()
        self.right_list.itemDoubleClicked.connect(self.handle_remote_double_click)
        self.right_search = QLineEdit()
        self.right_search.setPlaceholderText("Find saved files")
        self.right_search.textChanged.connect(self.filter_remote_list)
        self.load_remote_items()
        self.remove_btn = QPushButton("Delete selected")
        self.remove_btn.setObjectName("primary")
        self.remove_btn.clicked.connect(self.remove_selected_remote)
        right_header = QLabel("Remote files")
        right_header.setObjectName("panelTitle")
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(12)
        right_layout.addWidget(right_header)
        right_layout.addWidget(self.right_search)
        right_layout.addWidget(self.right_list)
        right_layout.addWidget(self.remove_btn)
        right_layout.addWidget(self.right_status)
        right_widget = QFrame()
        right_widget.setObjectName("panel")
        right_widget.setLayout(right_layout)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([450, 450])

        container = QWidget()
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(12, 12, 12, 12)
        container_layout.addWidget(splitter)
        container.setLayout(container_layout)
        self.setCentralWidget(container)
        self.apply_styles()

    def load_local_items(self):
        self.left_list.clear()
        for name in sorted(os.listdir(self.current_dir)):
            item = QListWidgetItem(name)
            self.left_list.addItem(item)
        self.filter_local_list(self.left_search.text())

    def load_remote_items(self):
        self.right_list.clear()
        try:
            titles = get_video_list(self.page)
            for title in titles:
                item = QListWidgetItem(title)
                self.right_list.addItem(item)
            self.filter_remote_list(self.right_search.text())
        except Exception as exc:
            raise Exception(f"Failed to load remote items: {exc}")

    def show_error_popup(self, message: str):
        error_dialog = QMessageBox(self)
        error_dialog.setIcon(QMessageBox.Icon.Critical)
        error_dialog.setWindowTitle("Error")
        error_dialog.setText(message)
        error_dialog.exec()

    def show_temporary_status(self, label: QLabel):
        label.setText(TRANSFER_TEXT)

    def handle_local_double_click(self, _item: QListWidgetItem):
        if _item is None:
            return
        self.process_local_file(_item.text())

    def handle_remote_double_click(self, _item: QListWidgetItem):
        if _item is None:
            return
        self.process_remote_file(_item.text())

    def remove_selected_remote(self):
        current = self.right_list.currentItem()
        if current is None:
            self.right_status.setText("No video selected")
            return

        try:
            print(f"Deleting video titled '{current.text()}' from YouTube")
            delete_video(self.page, current.text())
            self.right_status.setText("Video deleted")
        except Exception as exc:
            self.show_error_popup(f"Error: {exc}")
            return

        row = self.right_list.row(current)
        self.right_list.takeItem(row)

    def apply_styles(self):
        self.setStyleSheet(
            """
            QWidget {
                background: #0f172a;
                color: #e5e7eb;
                font-size: 14px;
                font-family: 'Segoe UI', 'Noto Sans', sans-serif;
            }
            QFrame#panel {
                background: #111827;
                border: 1px solid #1f2937;
                border-radius: 12px;
            }
            QLabel#panelTitle {
                font-size: 15px;
                font-weight: 600;
                color: #f9fafb;
            }
            QLineEdit {
                padding: 8px 10px;
                border: 1px solid #374151;
                border-radius: 8px;
                background: #111827;
                color: #e5e7eb;
            }
            QLineEdit:focus {
                border: 1px solid #60a5fa;
            }
            QPushButton {
                padding: 8px 12px;
                border-radius: 8px;
                border: 1px solid #374151;
                background: #111827;
                color: #e5e7eb;
            }
            QPushButton:hover {
                border: 1px solid #60a5fa;
                color: #f9fafb;
            }
            QPushButton:pressed {
                background: #1f2937;
            }
            QPushButton#primary {
                background: #2563eb;
                color: #ffffff;
                border: 1px solid #1d4ed8;
            }
            QPushButton#primary:hover {
                background: #1d4ed8;
            }
            QPushButton#ghost {
                padding: 6px 10px;
                background: #0f172a;
                border: 1px solid #1f2937;
                color: #cbd5e1;
            }
            QPushButton#ghost:hover {
                border: 1px solid #60a5fa;
                color: #f8fafc;
            }
            QListWidget {
                border: 1px solid #1f2937;
                border-radius: 8px;
                padding: 4px;
                background: #0b1220;
                color: #e5e7eb;
            }
            QListWidget::item {
                padding: 6px 8px;
            }
            QListWidget::item:selected {
                background: #1d4ed8;
                color: #f9fafb;
            }
            QLabel#pathLabel {
                color: #94a3b8;
                font-size: 12px;
            }
            """
        )

    def choose_directory(self):
        selected = QFileDialog.getExistingDirectory(
            self, "Select folder", str(self.current_dir)
        )
        if selected:
            self.set_current_directory(selected)

    def set_current_directory(self, path: str):
        target = Path(path).expanduser().resolve()
        if not target.is_dir():
            self.left_status.setText("Invalid path")
            return
        self.current_dir = target
        os.chdir(self.current_dir)
        self.dir_display.setText(str(self.current_dir))
        self.load_local_items()

    def filter_local_list(self, text: str):
        self._filter_list(self.left_list, text)

    def filter_remote_list(self, text: str):
        self._filter_list(self.right_list, text)

    def _filter_list(self, list_widget: QListWidget, query: str):
        needle = query.lower().strip()
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item is None:
                continue
            item.setHidden(needle not in item.text().lower())

    def process_local_file(self, filename: str):
        file_path = self.current_dir / filename
        if not file_path.is_file():
            self.left_status.setText("Select a valid file")
            return

        # ask for title
        suggested = file_path.stem
        title, ok = QInputDialog.getText(
            self,
            "Video title",
            "Insert the video title:",
            text=suggested,
        )
        title = title.strip()
        if not ok or not title:
            self.left_status.setText("Upload cancelled (no title)")
            return

        existing_titles = set()
        for i in range(self.right_list.count()):
            item = self.right_list.item(i)
            if item:
                existing_titles.add(item.text().strip())
        if title in existing_titles:
            self.show_error_popup("A video with this title already exists.")
            return

        try:
            output_path = self.current_dir / f"{title}.{CONTAINER}"
            self.left_status.setText("Encoding to video...")
            convert_file_to_video(str(file_path), str(output_path), self.key, self.rsc)
            self.left_status.setText("Uploading...")
            print(f"Uploading {output_path} to YouTube with title '{title}'")
            upload_video_to_youtube(str(output_path), self.page)
            self.left_status.setText("Upload completed")

            # removing the temporary video file
            os.remove(output_path)

            # append the new title to the remote list and apply current filter
            self.right_list.addItem(QListWidgetItem(title))
            self.filter_remote_list(self.right_search.text())
        except Exception as exc:
            self.show_error_popup(f"Error: {exc}")

    def _load_or_create_key(self) -> bytes:
        key_path = self.current_dir / "aes_key.bin"
        if key_path.exists():
            return key_path.read_bytes()
        key = os.urandom(16)
        key_path.write_bytes(key)
        return key

    def process_remote_file(self, filename: str):
        try:
            self.right_status.setText("Downloading...")
            QApplication.processEvents()
            file_path = download_video(self.page, filename, self.current_dir)

            self.right_status.setText("Decoding video...")
            QApplication.processEvents()
            extract_file_from_video(str(file_path), self.key, self.rsc)

            self.load_local_items()
            self.right_status.setText("Restore completed")
        except Exception as exc:
            self.show_error_popup(f"Error: {exc}")


def launch_transfer_gui():
    app = QApplication(sys.argv)
    with sync_playwright() as p:
        browser, context, page = create_yt_istance(p)
        window = FileTransferWindow(browser, context, page)
        window.show()
        sys.exit(app.exec())


if __name__ == "__main__":
    launch_transfer_gui()
