import sys
import os
import sqlite3
import re
import webbrowser
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QLineEdit, QTableWidget, QTableWidgetItem, QTextEdit, QSizePolicy, QSplitter, QHeaderView, QAction, QMenu, QMessageBox
)
from PyQt5.QtCore import Qt, QSize, QDateTime, QSettings
from PyQt5.QtGui import QIcon, QBrush, QColor, QTextCharFormat, QTextCursor, QKeySequence, QFont, QPainter
from datetime import datetime, timedelta
from tld import get_tld

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Notational Celerity")
        self.resize(800, 600)
        self.note_selected = False
        self.notes = []  # List of dicts: {"title": str, "content": str, "modified": QDateTime}
        self.filtered_notes = []  # Indices of notes matching the search
        self.current_note_index = None  # Index in self.notes
        self.sort_column = 1  # Default sort by date modified
        self.sort_order = Qt.SortOrder.DescendingOrder
        self.init_db()
        self.init_ui()
        self.load_notes_from_db()

    def init_ui(self):
        central = QWidget()
        layout = QVBoxLayout()

        # Search bar with icon
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search or Create")
        self.search_icon_action = QAction(self)
        self.magnifier_icon = QIcon.fromTheme("edit-find")
        self.pencil_icon = QIcon.fromTheme("document-edit")
        self.back_icon = QIcon.fromTheme("go-previous")
        # Fallback to built-in icons if theme icons are missing
        if self.magnifier_icon.isNull():
            self.magnifier_icon = QIcon(":/qt-project.org/styles/commonstyle/images/dirclosed-128.png")
        if self.pencil_icon.isNull():
            self.pencil_icon = QIcon(":/qt-project.org/styles/commonstyle/images/file-128.png")
        if self.back_icon.isNull():
            self.back_icon = QIcon(":/qt-project.org/styles/commonstyle/images/left-32.png")
        self.search_icon_action.setIcon(self.magnifier_icon)
        self.search_bar.addAction(self.search_icon_action, QLineEdit.LeadingPosition)
        self.search_icon_action.triggered.connect(self.exit_note)
        self.search_bar.installEventFilter(self)

        # Clear ('x') icon on the right
        self.clear_icon_action = QAction(self)
        self.clear_icon = QIcon.fromTheme("edit-clear")
        if self.clear_icon.isNull():
            self.clear_icon = QIcon(":/qt-project.org/styles/commonstyle/images/standardbutton-clear-32.png")
        self.clear_icon_action.setIcon(self.clear_icon)
        self.clear_icon_action.triggered.connect(self.clear_search_bar)
        self.clear_icon_action.setVisible(False)
        self.search_bar.addAction(self.clear_icon_action, QLineEdit.TrailingPosition)
        self.search_bar.textChanged.connect(self.update_clear_icon_visibility)
        self.search_bar.textChanged.connect(self.on_search_text_changed)

        layout.addWidget(self.search_bar)

        # Vertical splitter for notes list and editor
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Notes list as a table with 'Title' and 'Date Modified'
        self.notes_table = QTableWidget(0, 2)
        self.notes_table.setHorizontalHeaderLabels(["Title", "Date Modified"])
        header = self.notes_table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(1, QHeaderView.Stretch)
            # Left-align header labels for each column
            model = self.notes_table.model()
            if model is not None:
                model.setHeaderData(0, Qt.Orientation.Horizontal, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, Qt.ItemDataRole.TextAlignmentRole)
                model.setHeaderData(1, Qt.Orientation.Horizontal, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, Qt.ItemDataRole.TextAlignmentRole)
            # Restore persistent column sizes
            settings = self.get_settings()
            size0 = settings.value("notes_table/col0_width", 250, type=int)
            size1 = settings.value("notes_table/col1_width", 200, type=int)
            header.resizeSection(0, size0)
            header.resizeSection(1, size1)
            header.sectionResized.connect(self.save_notes_table_column_sizes)
            header.setSortIndicator(self.sort_column, self.sort_order)
            header.setSortIndicatorShown(True)
            header.sectionClicked.connect(self.handle_header_clicked)
        self.notes_table.setSelectionBehavior(self.notes_table.SelectRows)
        self.notes_table.setEditTriggers(self.notes_table.NoEditTriggers)
        self.notes_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.notes_table.setMinimumHeight(100)
        self.notes_table.itemSelectionChanged.connect(self.on_note_selected)
        self.notes_table.doubleClicked.connect(self.edit_selected_note)
        self.notes_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.notes_table.customContextMenuRequested.connect(self.show_notes_table_context_menu)
        self.notes_table.installEventFilter(self)
        vheader = self.notes_table.verticalHeader()
        if vheader is not None:
            vheader.setVisible(False)
        splitter.addWidget(self.notes_table)

        self.note_editor = NoteEdit(link_handler=self.handle_note_link)
        self.note_editor.textChanged.connect(self.auto_save_note)
        # Set tab stop width to 4 spaces
        self.note_editor.setTabStopDistance(4 * self.note_editor.fontMetrics().horizontalAdvance(' '))
        # Initialize editor as disabled (no note selected at startup)
        self.note_editor.setEnabled(False)
        self.note_editor.setReadOnly(True)
        splitter.addWidget(self.note_editor)

        splitter.setSizes([200, 400])  # Initial sizes
        layout.addWidget(splitter)

        central.setLayout(layout)
        self.setCentralWidget(central)

        # Enable rich text formatting shortcuts
        bold_action = QAction(self)
        bold_action.setShortcut(QKeySequence.Bold)
        bold_action.triggered.connect(self.set_bold)
        self.addAction(bold_action)

        italic_action = QAction(self)
        italic_action.setShortcut(QKeySequence.Italic)
        italic_action.triggered.connect(self.set_italic)
        self.addAction(italic_action)

        strike_action = QAction(self)
        strike_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        strike_action.triggered.connect(self.set_strikethrough)
        self.addAction(strike_action)

        underline_action = QAction(self)
        underline_action.setShortcut(QKeySequence.Underline)
        underline_action.triggered.connect(self.set_underline)
        self.addAction(underline_action)

        # Arrow key text size controls
        increase_size_up_action = QAction(self)
        increase_size_up_action.setShortcut(QKeySequence("Ctrl+."))
        increase_size_up_action.triggered.connect(self.increase_text_size)
        self.addAction(increase_size_up_action)

        decrease_size_down_action = QAction(self)
        decrease_size_down_action.setShortcut(QKeySequence("Ctrl+,"))
        decrease_size_down_action.triggered.connect(self.decrease_text_size)
        self.addAction(decrease_size_down_action)

        # Heading level shortcuts
        h1_action = QAction(self)
        h1_action.setShortcut(QKeySequence("Ctrl+1"))
        h1_action.triggered.connect(lambda: self.set_heading_level(1))
        self.addAction(h1_action)

        h2_action = QAction(self)
        h2_action.setShortcut(QKeySequence("Ctrl+2"))
        h2_action.triggered.connect(lambda: self.set_heading_level(2))
        self.addAction(h2_action)

        h3_action = QAction(self)
        h3_action.setShortcut(QKeySequence("Ctrl+3"))
        h3_action.triggered.connect(lambda: self.set_heading_level(3))
        self.addAction(h3_action)

        h4_action = QAction(self)
        h4_action.setShortcut(QKeySequence("Ctrl+4"))
        h4_action.triggered.connect(lambda: self.set_heading_level(4))
        self.addAction(h4_action)

        h5_action = QAction(self)
        h5_action.setShortcut(QKeySequence("Ctrl+5"))
        h5_action.triggered.connect(lambda: self.set_heading_level(5))
        self.addAction(h5_action)

        h6_action = QAction(self)
        h6_action.setShortcut(QKeySequence("Ctrl+6"))
        h6_action.triggered.connect(lambda: self.set_heading_level(6))
        self.addAction(h6_action)

        # Normal text shortcut
        normal_text_action = QAction(self)
        normal_text_action.setShortcut(QKeySequence("Ctrl+0"))
        normal_text_action.triggered.connect(self.set_normal_text)
        self.addAction(normal_text_action)

        # List item shortcut
        list_item_action = QAction(self)
        list_item_action.setShortcut(QKeySequence("Ctrl+L"))
        list_item_action.triggered.connect(self.toggle_list_item)
        self.addAction(list_item_action)

        # Create menu bar with help
        menubar = self.menuBar()
        if menubar:
            help_menu = menubar.addMenu("Help")
            if help_menu:
                help_menu.addAction("Create Tutorial Note", self.show_help)

    def on_note_selected(self):
        selected = self.notes_table.selectedItems()
        if selected:
            row = self.notes_table.currentRow()
            if row >= 0 and row < len(self.filtered_notes):
                self.current_note_index = self.filtered_notes[row]
                note = self.notes[self.current_note_index]
                # For empty or minimal content notes, start with clean editor
                content = note["content"].strip()
                if not content or content in ["", "<p></p>", "<p><br></p>"]:
                    self.note_editor.clear()
                    self.note_editor.setPlainText("")
                else:
                    # Load content with rendered links
                    rendered_content = self.render_links(note["content"])
                    self.note_editor.setHtml(rendered_content)
                self.note_editor.setEnabled(True)
                self.note_editor.setReadOnly(False)
                self.note_selected = True
                self.update_search_icon()
                # Save the currently open note's title to QSettings
                settings = self.get_settings()
                settings.setValue("last_open_note_title", note["title"])
        else:
            self.current_note_index = None
            self.note_editor.clear()
            self.note_editor.setReadOnly(True)  # Only set read-only when no note is selected
            self.note_editor.setEnabled(False)  # Disable the editor when no note is selected
            self.note_selected = False
            self.update_search_icon()
            # Remove last open note from QSettings
            settings = self.get_settings()
            settings.remove("last_open_note_title")

    def update_search_icon(self):
        if self.note_selected:
            self.search_icon_action.setIcon(self.pencil_icon)
        else:
            self.search_icon_action.setIcon(self.magnifier_icon)

    def eventFilter(self, obj, event):
        if obj == self.search_bar and self.note_selected:
            if event.type() == event.Enter:
                self.search_icon_action.setIcon(self.back_icon)
            elif event.type() == event.Leave:
                self.search_icon_action.setIcon(self.pencil_icon)
        elif hasattr(self, 'notes_table') and obj == self.notes_table and event.type() == event.KeyPress:
            # Prevent table from intercepting Shift+Tab when editor has focus
            if (event.key() == Qt.Key.Key_Tab and event.modifiers() == Qt.KeyboardModifier.ShiftModifier and 
                hasattr(self, 'note_editor') and self.note_editor.hasFocus()):
                return True  # Consume the event
        return super().eventFilter(obj, event)

    def exit_note(self):
        if self.note_selected:
            self.notes_table.clearSelection()
            self.note_editor.clear()
            self.note_editor.setReadOnly(True)
            self.note_editor.setEnabled(False)  # Disable the editor
            self.note_selected = False
            self.current_note_index = None
            self.update_search_icon()

    def update_clear_icon_visibility(self, text):
        self.clear_icon_action.setVisible(len(text) > 0)

    def clear_search_bar(self):
        self.search_bar.clear()

    def on_search_text_changed(self, text):
        # If user starts typing in search bar while a note is open, exit the note
        if text and self.note_selected:
            self.notes_table.clearSelection()
            self.note_editor.clear()
            self.note_editor.setReadOnly(True)
            self.note_editor.setEnabled(False)
            self.note_selected = False
            self.current_note_index = None
            self.update_search_icon()
        
        self.filter_notes(text)
        self.update_notes_table()
        if not text and not self.note_selected:
            self.notes_table.clearSelection()

    def filter_notes(self, text):
        text = text.strip().lower()
        self.filtered_notes = []
        for i, note in enumerate(self.notes):
            if text in note["title"].lower() or text in note["content"].lower():
                self.filtered_notes.append(i)
        if not text:
            self.filtered_notes = list(range(len(self.notes)))

    def update_notes_table(self):
        self.sort_notes()
        self.notes_table.setRowCount(len(self.filtered_notes))
        for row, note_idx in enumerate(self.filtered_notes):
            note = self.notes[note_idx]
            title_item = QTableWidgetItem(note["title"])
            date_str = self.format_note_date(note["modified"])
            date_item = QTableWidgetItem(date_str)
            self.notes_table.setItem(row, 0, title_item)
            self.notes_table.setItem(row, 1, date_item)

    def edit_selected_note(self):
        # Already handled by on_note_selected
        pass

    def auto_save_note(self):
        if self.current_note_index is not None and not self.note_editor.isReadOnly():
            content = self.note_editor.toHtml()
            note = self.notes[self.current_note_index]
            if note["content"] != content:
                note["content"] = content
                note["modified"] = QDateTime.currentDateTime()
                self.save_note_to_db(note)
                self.update_notes_table()

    def keyPressEvent(self, event):
        # If Enter is pressed in search bar and no note is selected
        if self.search_bar.hasFocus() and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            text = self.search_bar.text().strip()
            if text and not self.note_selected:
                # Check if a note with this title exists
                for idx, note in enumerate(self.notes):
                    if note["title"].strip().lower() == text.lower():
                        # Select and open the existing note
                        self.filter_notes(text)
                        self.update_notes_table()
                        # Find the row in filtered_notes
                        for row, note_idx in enumerate(self.filtered_notes):
                            if self.notes[note_idx]["title"].strip().lower() == text.lower():
                                self.notes_table.selectRow(row)
                                break
                        return
                # Otherwise, create a new note
                self.create_note(text)
            return
        
        # Handle Tab and Shift+Tab in note editor
        if self.note_editor.hasFocus():
            cursor = self.note_editor.textCursor()
            if event.key() == Qt.Key.Key_Tab:
                if cursor.hasSelection():
                    self.indent_selection(cursor)
                else:
                    cursor.insertText("    ")  # 4 spaces
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Backtab:
                if cursor.hasSelection():
                    self.outdent_selection(cursor)
                else:
                    # Handle single line outdent
                    cursor.movePosition(QTextCursor.StartOfLine)
                    line = cursor.block().text()
                    if line.startswith("    "):
                        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 4)
                        cursor.removeSelectedText()
                event.accept()
                return
        
        super().keyPressEvent(event)

    def create_note(self, title):
        # Create note with empty content
        note = {"title": title, "content": "", "modified": QDateTime.currentDateTime()}
        self.notes.insert(0, note)
        self.save_note_to_db(note)
        self.filter_notes(self.search_bar.text())
        self.update_notes_table()
        # Select the new note and set up editor for editing
        self.notes_table.selectRow(0)
        # Manually set up editor state for new note
        self.current_note_index = self.filtered_notes[0]
        self.note_editor.clear()
        self.note_editor.setPlainText("")
        self.note_editor.setEnabled(True)
        self.note_editor.setReadOnly(False)
        self.note_selected = True
        self.update_search_icon()

    def show_notes_table_context_menu(self, pos):
        row = self.notes_table.rowAt(pos.y())
        if row >= 0 and row < len(self.filtered_notes):
            menu = QMenu(self)
            rename_action = menu.addAction("Rename Note")
            delete_action = menu.addAction("Delete Note")
            viewport = self.notes_table.viewport()
            if viewport is not None:
                global_pos = viewport.mapToGlobal(pos)
                action = menu.exec_(global_pos)
                idx = self.filtered_notes[row]
                if action == rename_action:
                    # Make the title cell editable
                    self.notes_table.setEditTriggers(self.notes_table.EditKeyPressed | self.notes_table.SelectedClicked | self.notes_table.DoubleClicked)
                    item = self.notes_table.item(row, 0)
                    self.notes_table.editItem(item)
                    # Connect to editing finished
                    self.notes_table.itemChanged.connect(lambda changed_item, r=row, i=idx: self.rename_note(changed_item, r, i))
                elif action == delete_action:
                    note = self.notes[idx]
                    reply = QMessageBox.question(self, "Delete Note", f'Delete the note titled "{note['title']}"?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if reply == QMessageBox.Yes:
                        self.delete_note_from_db(note)
                        del self.notes[idx]
                        self.filter_notes(self.search_bar.text())
                        self.update_notes_table()
                        self.notes_table.clearSelection()
                        self.note_editor.clear()
                        self.note_editor.setReadOnly(True)
                        self.note_editor.setEnabled(False)
                        self.note_selected = False
                        self.current_note_index = None
                        self.update_search_icon()

    def rename_note(self, changed_item, row, idx):
        # Only handle title column
        if changed_item.column() != 0:
            return
        new_title = changed_item.text().strip()
        if not new_title:
            # Revert to old title if empty
            changed_item.setText(self.notes[idx]["title"])
            return
        # Check for duplicate titles
        for i, note in enumerate(self.notes):
            if i != idx and note["title"].strip().lower() == new_title.lower():
                changed_item.setText(self.notes[idx]["title"])
                return
        old_title = self.notes[idx]["title"]
        self.notes[idx]["title"] = new_title
        self.save_note_to_db(self.notes[idx])
        # If title changed, update DB (delete old, save new)
        if old_title != new_title:
            self.delete_note_from_db({"title": old_title})
        # Restore edit triggers
        self.notes_table.setEditTriggers(self.notes_table.NoEditTriggers)
        # Disconnect to avoid repeated triggers
        self.notes_table.itemChanged.disconnect()
        self.filter_notes(self.search_bar.text())
        self.update_notes_table()

    def get_data_dir(self):
        # Cross-platform app data directory
        from pathlib import Path
        if sys.platform == "win32":
            base = os.getenv("APPDATA", str(Path.home()))
        elif sys.platform == "darwin":
            base = os.path.join(str(Path.home()), "Library", "Application Support")
        else:
            base = os.getenv("XDG_DATA_HOME", os.path.join(str(Path.home()), ".local", "share"))
        data_dir = os.path.join(base, "Notational Celerity")
        os.makedirs(data_dir, exist_ok=True)
        return data_dir

    def get_db_path(self):
        return os.path.join(self.get_data_dir(), "notes.db")

    def get_settings(self):
        return QSettings("Notational Celerity", "Notational Celerity")

    def init_db(self):
        self.conn = sqlite3.connect(self.get_db_path())
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                modified TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def load_notes_from_db(self):
        self.notes = []
        for row in self.conn.execute("SELECT title, content, modified FROM notes ORDER BY modified DESC"):
            self.notes.append({
                "title": row[0],
                "content": row[1],
                "modified": QDateTime.fromString(row[2], "yyyy-MM-dd HH:mm:ss")
            })
        self.filter_notes(self.search_bar.text())
        self.update_notes_table()
        # Restore last open note if available
        settings = self.get_settings()
        last_title = settings.value("last_open_note_title", "")
        if last_title:
            for row, note_idx in enumerate(self.filtered_notes):
                if self.notes[note_idx]["title"] == last_title:
                    self.notes_table.selectRow(row)
                    self.on_note_selected()
                    break

    def save_note_to_db(self, note):
        # Insert or update note by title (for simplicity, titles are unique)
        c = self.conn.cursor()
        c.execute("SELECT id FROM notes WHERE title=?", (note["title"],))
        row = c.fetchone()
        if row:
            c.execute("UPDATE notes SET content=?, modified=? WHERE id=?", (note["content"], note["modified"].toString("yyyy-MM-dd HH:mm:ss"), row[0]))
        else:
            c.execute("INSERT INTO notes (title, content, modified) VALUES (?, ?, ?)", (note["title"], note["content"], note["modified"].toString("yyyy-MM-dd HH:mm:ss")))
        self.conn.commit()

    def delete_note_from_db(self, note):
        c = self.conn.cursor()
        c.execute("DELETE FROM notes WHERE title=?", (note["title"],))
        self.conn.commit()

    def save_notes_table_column_sizes(self, logicalIndex, oldSize, newSize):
        if logicalIndex in (0, 1):
            settings = self.get_settings()
            settings.setValue(f"notes_table/col{logicalIndex}_width", newSize)

    def format_note_date(self, qdatetime):
        dt = qdatetime.toPyDateTime()
        now = datetime.now()
        today = now.date()
        note_date = dt.date()
        if note_date == today:
            return f"Today at {dt.strftime('%I:%M %p').lstrip('0')}"
        elif note_date == today - timedelta(days=1):
            return f"Yesterday at {dt.strftime('%I:%M %p').lstrip('0')}"
        else:
            return dt.strftime("%b %d, %Y")

    def handle_header_clicked(self, logicalIndex):
        if logicalIndex not in (0, 1):
            return
        if self.sort_column == logicalIndex:
            # Toggle sort order
            self.sort_order = Qt.SortOrder.AscendingOrder if self.sort_order == Qt.SortOrder.DescendingOrder else Qt.SortOrder.DescendingOrder
        else:
            self.sort_column = logicalIndex
            self.sort_order = Qt.SortOrder.AscendingOrder if logicalIndex == 0 else Qt.SortOrder.DescendingOrder
        header = self.notes_table.horizontalHeader()
        if header is not None:
            header.setSortIndicator(self.sort_column, self.sort_order)
        self.sort_notes()
        self.update_notes_table()

    def sort_notes(self):
        reverse = self.sort_order == Qt.SortOrder.DescendingOrder
        if self.sort_column == 0:
            # Sort by title
            self.filtered_notes.sort(key=lambda idx: self.notes[idx]["title"].lower(), reverse=reverse)
        elif self.sort_column == 1:
            # Sort by date modified
            self.filtered_notes.sort(key=lambda idx: self.notes[idx]["modified"].toPyDateTime(), reverse=reverse)

    def set_bold(self):
        cursor = self.note_editor.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Bold if not cursor.charFormat().fontWeight() == QFont.Bold else QFont.Normal)
        cursor.mergeCharFormat(fmt)
        self.note_editor.mergeCurrentCharFormat(fmt)

    def set_italic(self):
        cursor = self.note_editor.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontItalic(not cursor.charFormat().fontItalic())
        cursor.mergeCharFormat(fmt)
        self.note_editor.mergeCurrentCharFormat(fmt)

    def set_strikethrough(self):
        cursor = self.note_editor.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(not cursor.charFormat().fontStrikeOut())
        cursor.mergeCharFormat(fmt)
        self.note_editor.mergeCurrentCharFormat(fmt)

    def set_underline(self):
        cursor = self.note_editor.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not cursor.charFormat().fontUnderline())
        cursor.mergeCharFormat(fmt)
        self.note_editor.mergeCurrentCharFormat(fmt)

    def indent_selection(self, cursor):
        """Indent selected lines by 4 spaces"""
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        
        # Get the document
        doc = cursor.document()
        
        # Find the first and last blocks in the selection
        start_block = doc.findBlock(start)
        end_block = doc.findBlock(end)
        
        # If end is at the beginning of a block, don't include that block
        if end == end_block.position():
            end_block = end_block.previous()
        
        # Indent each line
        block = start_block
        while block.isValid() and block.position() <= end_block.position():
            cursor.setPosition(block.position())
            cursor.insertText("    ")  # 4 spaces
            block = block.next()
        
        # Restore selection
        cursor.setPosition(start)
        cursor.setPosition(end + 4 * (end_block.blockNumber() - start_block.blockNumber() + 1), QTextCursor.KeepAnchor)

    def outdent_selection(self, cursor):
        # Outdent each selected line
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        cursor.setPosition(start)
        while cursor.position() < end:
            cursor.movePosition(QTextCursor.StartOfLine)
            line = cursor.block().text()
            if line.startswith("    "):  # Check for 4 spaces
                cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 4)
                cursor.removeSelectedText()
                end -= 4
            cursor.movePosition(QTextCursor.EndOfLine)
            cursor.movePosition(QTextCursor.NextCharacter)

    def handle_note_link(self, href):
        if href.startswith('note:'):
            title = href[5:]
            # Find and open the existing note
            for idx, note in enumerate(self.notes):
                if note["title"] == title:
                    # Select and open the note
                    self.filter_notes("")
                    self.update_notes_table()
                    for row, note_idx in enumerate(self.filtered_notes):
                        if self.notes[note_idx]["title"] == title:
                            self.notes_table.selectRow(row)
                            self.on_note_selected()
                            break
                    return
        else:
            # Handle web URLs
            if self.is_web_url(href):
                # Ensure URL has protocol
                if not href.startswith(('http://', 'https://')):
                    href = 'https://' + href
                webbrowser.open(href)

    def render_links(self, html):
        # Convert [[title]] to clickable links, keeping brackets visible and clickable
        def link_replacer(match):
            title = match.group(1)
            if self.is_web_url(title):
                return f'<a href="{title}">{title}</a>'
            else:
                # Only create links for existing notes
                note_exists = any(note["title"] == title for note in self.notes)
                if note_exists:
                    # Don't create links to the current note (avoid self-referencing)
                    if self.current_note_index is not None and self.notes[self.current_note_index]["title"] == title:
                        return f'[[{title}]]'  # Keep as plain text for current note
                    else:
                        return f'<a href="note:{title}">{title}</a>'
                else:
                    # Keep non-existent note titles as plain text
                    return f'[[{title}]]'
        return re.sub(r'\[\[([^\]]+)\]\]', link_replacer, html)

    def is_web_url(self, text):
        # Must contain at least one dot to be considered a URL
        if '.' not in text:
            return False
        try:
            # Add protocol if missing
            if not text.startswith(('http://', 'https://')):
                text = 'https://' + text
            get_tld(text, fail_silently=True)
            return True
        except:
            return False

    def show_help(self):
        # Create or find the help note
        help_title = "How to Use Notational Celerity"
        help_content = """<h1>How to Use Notational Celerity</h1>

<h2>Basic Usage</h2>

<p><strong>Search and Create Notes:</strong></p>
<ul>
<li>Type in the search bar to find existing notes</li>
<li>Press Enter to create a new note with that title</li>
<li>Notes are automatically saved as you type</li>
<li>Tip: You can also find words inside of your notes</li>
</ul>

<p><strong>Navigation:</strong></p>
<ul>
<li>Click on any note in the list to open it</li>
<li>Use the back arrow (←) in the search bar to exit a note</li>
<li>Click the brush icon to clear the search</li>
</ul>

<h2>Text Formatting Shortcuts</h2>

<p><strong>Bold:</strong> Ctrl+B<br>
<strong>Italic:</strong> Ctrl+I<br>
<strong>Underline:</strong> Ctrl+U<br>
<strong>Strikethrough:</strong> Ctrl+Shift+S</p>

<p><strong>Text Size:</strong><br>
<strong>Increase:</strong> Ctrl+.<br>
<strong>Decrease:</strong> Ctrl+,<br>
<strong>Normal:</strong> Ctrl+0</p>

<p><strong>Headings:</strong><br>
<strong>H1:</strong> Ctrl+1<br>
<strong>H2:</strong> Ctrl+2<br>
<strong>H3:</strong> Ctrl+3<br>
<strong>H4:</strong> Ctrl+4<br>
<strong>H5:</strong> Ctrl+5<br>
<strong>H6:</strong> Ctrl+6</p>

<p><strong>Indent:</strong> Tab<br>
<strong>Add Bullet Point:</strong> Ctrl+L</p>

<h2>Note Linking</h2>

<p><strong>Internal Links:</strong></p>
<ul>
<li>Type [[Note Title]] to create a link to another note</li>
<li>Only existing notes become clickable links</li>
<li>Non-existent note titles remain as plain text</li>
<li>Click on any link to navigate to that note</li>
</ul>

<p><strong>Web Links:</strong></p>
<ul>
<li>Type [[Your URL]] to create a web link</li>
<li>Click to open in your default browser</li>
<li>Accepted URL formats: http://, https://, ftp://, mailto:// etc.;</li>
<li>although just the domain name is enough (e.g. example.com)</li>
</ul>

<h2>Note Management</h2>

<p><strong>Right-click on a note in the list for:</strong></p>
<ul>
<li>Rename Note: Double-click the title or use context menu</li>
<li>Delete Note: Confirmation dialog will appear</li>
</ul>

<p><strong>Sorting:</strong></p>
<ul>
<li>Click column headers to sort by Title or Date Modified</li>
<li>Click again to reverse sort order</li>
</ul>

<h2>Tips</h2>

<ul>
<li>Notes are automatically saved to your system's app data directory</li>
<li>The app remembers your column widths and sort preferences</li>
<li>All formatting is preserved when you save notes</li>
<li>Links are only clickable for existing notes and valid URLs</li>
</ul>

<h2>Data Location</h2>

<p>Your notes are stored in:</p>
<ul>
<li><strong>macOS:</strong> ~/Library/Application Support/Notational Celerity/</li>
<li><strong>Windows:</strong> %APPDATA%/Notational Celerity/</li>
<li><strong>Linux:</strong> ~/.local/share/Notational Celerity/</li>
</ul>"""

        # Check if help note already exists
        help_note_index = None
        for i, note in enumerate(self.notes):
            if note["title"] == help_title:
                help_note_index = i
                break

        if help_note_index is not None:
            # Update existing help note
            self.notes[help_note_index]["content"] = help_content
            self.notes[help_note_index]["modified"] = QDateTime.currentDateTime()
            self.save_note_to_db(self.notes[help_note_index])
        else:
            # Create new help note
            help_note = {"title": help_title, "content": help_content, "modified": QDateTime.currentDateTime()}
            self.notes.insert(0, help_note)
            self.save_note_to_db(help_note)
            help_note_index = 0

        # Select and display the help note
        self.filter_notes("")
        self.update_notes_table()
        # Find the help note in filtered_notes
        for row, note_idx in enumerate(self.filtered_notes):
            if self.notes[note_idx]["title"] == help_title:
                self.notes_table.selectRow(row)
                self.on_note_selected()  # Update the editor to show the help note
                break

    def increase_text_size(self):
        cursor = self.note_editor.textCursor()
        current_size = cursor.charFormat().font().pointSize()
        if current_size == -1:  # Default size
            current_size = 12
        new_size = min(current_size + 2, 72)  # Max size of 72pt
        fmt = QTextCharFormat()
        font = fmt.font()
        font.setPointSize(new_size)
        fmt.setFont(font)
        cursor.mergeCharFormat(fmt)
        self.note_editor.mergeCurrentCharFormat(fmt)

    def decrease_text_size(self):
        cursor = self.note_editor.textCursor()
        current_size = cursor.charFormat().font().pointSize()
        if current_size == -1:  # Default size
            current_size = 12
        new_size = max(current_size - 2, 6)  # Min size of 6pt
        fmt = QTextCharFormat()
        font = fmt.font()
        font.setPointSize(new_size)
        fmt.setFont(font)
        cursor.mergeCharFormat(fmt)
        self.note_editor.mergeCurrentCharFormat(fmt)

    def set_heading_level(self, level):
        cursor = self.note_editor.textCursor()
        if cursor.hasSelection():
            # Apply heading to selected text
            fmt = QTextCharFormat()
            font = fmt.font()
            # Set font size based on heading level
            sizes = {1: 24, 2: 20, 3: 16, 4: 14, 5: 12, 6: 10}
            font.setPointSize(sizes.get(level, 12))
            font.setBold(True)
            fmt.setFont(font)
            cursor.mergeCharFormat(fmt)
        else:
            # Apply heading to current line
            cursor.select(QTextCursor.LineUnderCursor)
            fmt = QTextCharFormat()
            font = fmt.font()
            sizes = {1: 24, 2: 20, 3: 16, 4: 14, 5: 12, 6: 10}
            font.setPointSize(sizes.get(level, 12))
            font.setBold(True)
            fmt.setFont(font)
            cursor.mergeCharFormat(fmt)
            cursor.clearSelection()

    def set_normal_text(self):
        cursor = self.note_editor.textCursor()
        fmt = QTextCharFormat()
        font = fmt.font()
        font.setPointSize(12)  # Default size
        font.setBold(False)
        font.setItalic(False)
        font.setUnderline(False)
        font.setStrikeOut(False)
        fmt.setFont(font)
        cursor.mergeCharFormat(fmt)
        self.note_editor.mergeCurrentCharFormat(fmt)

    def toggle_list_item(self):
        cursor = self.note_editor.textCursor()
        cursor.select(QTextCursor.LineUnderCursor)
        line_text = cursor.selectedText()
        
        # Check if line already starts with a bullet
        if line_text.startswith("    • "):
            # Remove bullet and indentation
            new_text = line_text[6:]  # Remove "    • " prefix
        elif line_text.startswith("• "):
            # Remove bullet only
            new_text = line_text[2:]  # Remove "• " prefix
        else:
            # Add bullet with one level of indentation
            new_text = "    • " + line_text.lstrip()
        
        cursor.insertText(new_text)
        cursor.clearSelection()

class NoteEdit(QTextEdit):
    def __init__(self, parent=None, link_handler=None):
        super().__init__(parent)
        self.link_handler = link_handler
        self.placeholder_text = "No Note Selected"

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Tab:
            cursor = self.textCursor()
            if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                # Shift+Tab - outdent
                if cursor.hasSelection():
                    # Outdent selection
                    start = cursor.selectionStart()
                    end = cursor.selectionEnd()
                    cursor.setPosition(start)
                    while cursor.position() < end:
                        cursor.movePosition(QTextCursor.StartOfLine)
                        line = cursor.block().text()
                        if line.startswith("    "):  # Check for 4 spaces
                            cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 4)
                            cursor.removeSelectedText()
                            end -= 4
                        cursor.movePosition(QTextCursor.EndOfLine)
                        cursor.movePosition(QTextCursor.NextCharacter)
                else:
                    # Single line outdent
                    cursor.movePosition(QTextCursor.StartOfLine)
                    line = cursor.block().text()
                    if line.startswith("    "):
                        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 4)
                        cursor.removeSelectedText()
                event.accept()
                return
            else:
                # Tab - indent
                cursor = self.textCursor()
                if cursor.hasSelection():
                    # Indent selection
                    start = cursor.selectionStart()
                    end = cursor.selectionEnd()
                    doc = cursor.document()
                    if doc is not None:
                        start_block = doc.findBlock(start)
                        end_block = doc.findBlock(end)
                        if end == end_block.position():
                            end_block = end_block.previous()
                        block = start_block
                        while block.isValid() and block.position() <= end_block.position():
                            cursor.setPosition(block.position())
                            cursor.insertText("    ")  # 4 spaces
                            block = block.next()
                        cursor.setPosition(start)
                        cursor.setPosition(end + 4 * (end_block.blockNumber() - start_block.blockNumber() + 1), QTextCursor.KeepAnchor)
                else:
                    cursor.insertText("    ")  # 4 spaces
                event.accept()
                return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        # Show placeholder text when document is empty and widget is disabled
        document = self.document()
        viewport = self.viewport()
        if document and viewport and document.isEmpty() and not self.isEnabled():
            painter = QPainter(viewport)
            painter.save()
            painter.setPen(self.palette().color(self.palette().PlaceholderText))
            # Create a larger font for the placeholder text
            placeholder_font = self.font()
            placeholder_font.setPointSize(16)  # Increase from default to 16pt
            painter.setFont(placeholder_font)
            rect = viewport.rect()
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.placeholder_text)
            painter.restore()

    def mouseReleaseEvent(self, event):
        cursor = self.cursorForPosition(event.pos())
        anchor = cursor.charFormat().anchorHref()
        if anchor:
            if self.link_handler:
                self.link_handler(anchor)
            return  # Do not call super to prevent placing cursor in link
        super().mouseReleaseEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_()) 