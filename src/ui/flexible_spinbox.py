# ti_gui/flexible_spinbox.py (NEW FILE)

from PySide6.QtWidgets import QDoubleSpinBox, QAbstractSpinBox
from PySide6.QtGui import QValidator, QKeyEvent
from PySide6.QtCore import Qt, QLocale

class FlexibleDoubleSpinBox(QDoubleSpinBox):
    """
    A QDoubleSpinBox that accepts both '.' and ',' as decimal separators
    regardless of the system locale.
    
    It detects the system's native separator and normalizes the
    alternate separator to the native one for validation and parsing.
    It also maps Left/Right arrow keys to decrease/increase the value.
    
    The spin buttons (steppers) are hidden.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # Do NOT force locale. Use the system's default locale.
        # self.setLocale(QLocale(QLocale.Language.C))
        
        # Detect and store the native decimal separator.
        self._separator = self.locale().decimalPoint()
        
        # Determine the alternate (non-native) separator.
        self._alternate_separator = "." if self._separator == "," else ","

        # --- MODIFIED: Hide the up/down buttons ---
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        # --- END MODIFIED ---

    def validate(self, input_text: str, pos: int) -> QValidator.State:
        """
        Validates the text, allowing the alternate separator
        by normalizing it to the native one.
        """
        # Replace the *alternate* separator with the *native* one
        text_to_validate = input_text.replace(
            self._alternate_separator, self._separator, 1
        )
        return super().validate(text_to_validate, pos)

    def valueFromText(self, text: str) -> float:
        """
        Converts text (with potential alternate separator) to a float value.
        Note: `text` is passed *without* the suffix.
        """
        # Replace the *alternate* separator with the *native* one
        normalized_text = text.replace(
            self._alternate_separator, self._separator, 1
        )
        # Call the base method which expects the native separator
        return super().valueFromText(normalized_text)

    def keyPressEvent(self, event: QKeyEvent):
        """
        Overrides keyPressEvent to allow Left/Right arrows
        to decrease/increase the value.
        """
        if event.key() == Qt.Key.Key_Right:
            self.stepBy(1)
            event.accept()
            return
        elif event.key() == Qt.Key.Key_Left:
            self.stepBy(-1)
            event.accept()
            return
        
        # Call the base implementation for all other keys
        # (e.g., Up, Down, numbers, backspace, and native separators)
        super().keyPressEvent(event)