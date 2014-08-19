from pyqode.qt.QtCore import QObject, QTimer, Signal, Qt
from pyqode.qt.QtWidgets import QAction
from pyqode.qt.QtGui import QTextCursor
from pyqode.core.api import Mode, TextHelper, TextDecoration


class Definition(object):
    """
    Symbol definition: name, line and column
    """
    def __init__(self, line, column, name):
        #: Line number
        self.line = line
        #: Column number
        self.column = column
        self.name = name

    def __str__(self):
        if self.line and self.column:
            return "%s (%s, %s)" % (self.name, self.line, self.column)
        return self.name

    def __repr__(self):
        return "Definition(%r, %r, %r)" % (self.line, self.column, self.name)


class GoToDefinitionMode(Mode, QObject):
    """
    Goes to the assignments (using jedi.Script.goto_assignments). If there are
    more than one assignments, an input dialog is used to ask the user to
    choose the desired assignment.

    This mode will emit :attr:`pyqode.python.GoToAssignmentsMode.outOfDocument`
    if the definition can not be reached in the current document. IDEs will
    typically open a new editor tab and go to the definition.
    """
    #: Signal emitted when a word is clicked. The parameter is a
    #: QTextCursor with the clicked word set as the selected text.
    word_clicked = Signal(QTextCursor)

    def __init__(self):
        QObject.__init__(self)
        Mode.__init__(self)
        self._previous_cursor_start = -1
        self._previous_cursor_end = -1
        self._definition = None
        self._deco = None
        self._pending = False
        self.action_goto = QAction("Go to assignments", self)
        self.action_goto.setShortcut('F3')
        self.action_goto.triggered.connect(self.request_goto)
        self.word_clicked.connect(self.request_goto)

    def on_state_changed(self, state):
        """
        Connects/disconnects slots to/from signals when the mode state
        changed.
        """
        if state:
            self.editor.mouse_moved.connect(self._on_mouse_moved)
            self.editor.mouse_pressed.connect(self._on_mouse_pressed)
            self.editor.add_action(self.action_goto)
        else:
            self.editor.mouse_moved.disconnect(self._on_mouse_moved)
            self.editor.mouse_pressed.disconnect(self._on_mouse_pressed)
            self.editor.remove_action(self.action_goto)

    def _select_word_under_mouse_cursor(self):
        """ Selects the word under the mouse cursor. """
        cursor = TextHelper(self.editor).word_under_mouse_cursor()
        if (self._previous_cursor_start != cursor.selectionStart() and
                self._previous_cursor_end != cursor.selectionEnd()):
            self._remove_decoration()
            self._add_decoration(cursor)
        self._previous_cursor_start = cursor.selectionStart()
        self._previous_cursor_end = cursor.selectionEnd()

    def _on_mouse_moved(self, event):
        """ mouse moved callback """
        if event.modifiers() & Qt.ControlModifier:
            self._select_word_under_mouse_cursor()
        else:
            self._remove_decoration()
            self.editor.set_mouse_cursor(Qt.IBeamCursor)
            self._previous_cursor_start = -1
            self._previous_cursor_end = -1

    def _on_mouse_pressed(self, event):
        """ mouse pressed callback """
        if event.button() == 1 and self._deco:
            cursor = TextHelper(self.editor).word_under_mouse_cursor()
            if cursor and cursor.selectedText():
                self.word_clicked.emit(cursor)

    def select_word(self, cursor):
        symbol = cursor.selectedText()
        analyser = self.editor.outline_mode
        node = analyser.root_node.find(symbol)
        if node and node.line != cursor.block().blockNumber():
            self._definition = node
            if self._deco is None:
                if cursor.selectedText():
                    self._deco = TextDecoration(cursor)
                    self._deco.set_foreground(Qt.blue)
                    self._deco.set_as_underlined()
                    self.editor.decorations.append(self._deco)
                    return True
        return False

    def _add_decoration(self, cursor):
        """
        Adds a decoration for the word under ``cursor``.
        """
        if self.select_word(cursor):
            self.editor.set_mouse_cursor(Qt.PointingHandCursor)
        else:
            self.editor.set_mouse_cursor(Qt.IBeamCursor)

    def _remove_decoration(self):
        """
        Removes the word under cursor's decoration
        """
        if self._deco is not None:
            self.editor.decorations.remove(self._deco)
            self._deco = None

    def request_goto(self, tc=None):
        """
        Request a go to assignment.

        :param tc: Text cursor which contains the text that we must look for
                   its assignment. Can be None to go to the text that is under
                   the text cursor.
        :type tc: QtGui.QTextCursor
        """
        if not tc:
            tc = TextHelper(self.editor).word_under_cursor(
                select_whole_word=True)
        if not self._definition or isinstance(self.sender(), QAction):
            self.select_word(tc)
        QTimer.singleShot(100, self._goto_def)

    def _goto_def(self):
        line = self._definition.line
        col = self._definition.column
        TextHelper(self.editor).goto_line(line, move=True, column=col)
