import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QPushButton, QProgressBar, QFileDialog, QWidget, QHBoxLayout, QLabel,
    QScrollArea
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QColor
import cv2

from modules.media_processor import *

# Processor status codes
STATUS_UNPROCESSED = 0
STATUS_EXIST = 1
STATUS_SUCCESS = 2
STATUS_FAIL = 3
STATUS_SKIPPED = 4

class FileProcessor(QThread):
    progress = pyqtSignal(int)
    fileProcessed = pyqtSignal(int, int)  # Emit status code instead of bool
    fileProcessing = pyqtSignal(int)  # Signal to show "Processing" status

    def __init__(self, files, input_dir, output_dir):
        super().__init__()
        self.files = files
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.is_running = True

    def run(self):
        for index, file_item in enumerate(self.files):
            if not self.is_running:
                break

            file_name = file_item.text(0)
            file_type = file_item.text(1)

            input_file_path = os.path.join(self.input_dir, file_name)
            output_file_path = self.output_dir

            # Emit signal to show processing status
            self.fileProcessing.emit(index)

            # Determine the processor based on file type
            processor = None
            if file_type == 'image':
                processor = ImageProcessor(input_file_path, output_file_path)
            elif file_type == 'video':
                processor = VideoProcessor(input_file_path, output_file_path)
            elif file_type == 'text':
                processor = TextProcessor(input_file_path, output_file_path)
            elif file_type.startswith("unsupported"):
                self.fileProcessed.emit(index, STATUS_SKIPPED)
                continue  # Skip unsupported files

            # Process the file and get the result
            if processor:
                status_code = processor.process()
                self.fileProcessed.emit(index, status_code)
                self.progress.emit(int((index + 1) / len(self.files) * 100))

    def stop(self):
        self.is_running = False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Processor")
        self.setGeometry(100, 100, 800, 600)

        # Layouts
        main_layout = QHBoxLayout()
        self.left_layout = QVBoxLayout()
        self.right_layout = QVBoxLayout()

        # Directory Choosers and Scrollable Labels
        self.input_dir_button = QPushButton("Choose Input Directory")
        self.input_dir_button.clicked.connect(self.choose_input_directory)
        self.output_dir_button = QPushButton("Choose Output Directory")
        self.output_dir_button.clicked.connect(self.choose_output_directory)

        self.input_dir_label = QLabel("None")
        self.output_dir_label = QLabel("None")

        # Scroll areas for input and output directories
        input_scroll = QScrollArea()
        input_scroll.setWidgetResizable(True)
        input_scroll.setWidget(self.input_dir_label)
        output_scroll = QScrollArea()
        output_scroll.setWidgetResizable(True)
        output_scroll.setWidget(self.output_dir_label)

        self.left_layout.addWidget(self.input_dir_button)
        self.left_layout.addWidget(QLabel("Input Directory:"))
        self.left_layout.addWidget(input_scroll)
        self.left_layout.addWidget(self.output_dir_button)
        self.left_layout.addWidget(QLabel("Output Directory:"))
        self.left_layout.addWidget(output_scroll)

        # Set fixed width for the left layout
        left_widget = QWidget()
        left_widget.setLayout(self.left_layout)
        left_widget.setFixedWidth(200)

        # File Tree
        self.file_tree = QTreeWidget()
        self.file_tree.setColumnCount(4)
        self.file_tree.setHeaderLabels(['File Name', 'Type', 'Size', 'Status'])
        self.right_layout.addWidget(self.file_tree)

        # Progress Bar and Start Button
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.right_layout.addWidget(self.progress_bar)

        self.process_button = QPushButton("Start Processing")
        self.process_button.setIcon(QIcon.fromTheme("media-playback-start"))
        self.process_button.clicked.connect(self.toggle_processing)
        self.right_layout.addWidget(self.process_button)

        # Main Layout setup
        main_layout.addWidget(left_widget)
        main_layout.addLayout(self.right_layout)

        # Central Widget
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # Variables
        self.input_dir = ""
        self.output_dir = ""
        self.files = []
        self.processor = None

    def choose_input_directory(self):
        self.input_dir = QFileDialog.getExistingDirectory(self, "Select Input Directory")
        if self.input_dir:
            self.input_dir_label.setText(self.input_dir)
        else:
            self.input_dir_label.setText("None")
        self.load_files()

    def choose_output_directory(self):
        self.output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if self.output_dir:
            self.output_dir_label.setText(self.output_dir)
        else:
            self.output_dir_label.setText("None")

    def load_files(self):
        if not self.input_dir:
            return

        self.file_tree.clear()
        self.files = []

        for file_name in os.listdir(self.input_dir):
            file_path = os.path.join(self.input_dir, file_name)
            if os.path.isfile(file_path) and not file_name.startswith('.'):  # Ignore hidden files
                file_type = self.get_file_type(file_name)
                file_size = os.path.getsize(file_path)

                item = QTreeWidgetItem([
                    file_name,
                    file_type,
                    f"{file_size} bytes",
                    "Unprocessed"
                ])
                item.setIcon(3, QIcon.fromTheme("process-stop"))  # Unprocessed icon
                self.file_tree.addTopLevelItem(item)
                self.files.append(item)

    def get_file_type(self, file_name):
        ext = file_name.split('.')[-1].lower()
        if ext in ['jpg', 'jpeg', 'png']:
            return 'image'
        elif ext in ['mp4', 'mpeg', 'gif']:  # Added GIF as a supported video format
            return 'video'
        elif ext == 'txt':
            return 'text'
        else:
            return f"unsupported ({ext})"

    def toggle_processing(self):
        if self.processor and self.processor.is_running:
            self.stop_processing()
        else:
            self.start_processing()

    def start_processing(self):
        if not self.input_dir or not self.output_dir:
            return  # Do nothing if directories are not chosen

        self.process_button.setText("Stop Processing")
        self.process_button.setIcon(QIcon.fromTheme("media-playback-pause"))

        self.processor = FileProcessor(self.files, self.input_dir, self.output_dir)
        self.processor.progress.connect(self.update_progress)
        self.processor.fileProcessing.connect(self.show_processing_status)
        self.processor.fileProcessed.connect(self.update_file_status)
        self.processor.finished.connect(self.processing_finished)
        self.processor.start()

    def stop_processing(self):
        if self.processor:
            self.processor.stop()
        self.process_button.setText("Start Processing")
        self.process_button.setIcon(QIcon.fromTheme("media-playback-start"))

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def show_processing_status(self, index):
        """Show blue 'Processing' status."""
        item = self.files[index]
        item.setText(3, "Processing")
        item.setForeground(3, QColor("blue"))  # Blue color for processing
        item.setIcon(3, QIcon.fromTheme("view-refresh"))  # Refresh icon for processing

    def update_file_status(self, index, status_code):
        item = self.files[index]
        if status_code == STATUS_SUCCESS or status_code == STATUS_EXIST:
            item.setText(3, "Processed" if status_code == STATUS_SUCCESS else "Already Exists")
            item.setForeground(3, QColor("green"))  # Green color for success or exist
            item.setIcon(3, QIcon.fromTheme("dialog-ok-apply"))  # Checkmark icon
        elif status_code == STATUS_FAIL:
            item.setText(3, "Failed")
            item.setForeground(3, QColor("red"))  # Red color for failure
            item.setIcon(3, QIcon.fromTheme("dialog-error"))  # Cross icon
        elif status_code == STATUS_SKIPPED:
            item.setText(3, "Skipped")
            item.setForeground(3, QColor("gray"))  # Gray color for skipped
            item.setIcon(3, QIcon.fromTheme("dialog-cancel"))  # Cancel icon for skipped

    def processing_finished(self):
        self.process_button.setText("Start Processing")
        self.process_button.setIcon(QIcon.fromTheme("media-playback-start"))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())