from abc import ABC, abstractmethod

class BaseInterface(ABC):
    """Abstract Base Class for defining user interfaces (e.g., CLI, GUI)."""
    
    @abstractmethod
    def display_message(self, message: str) -> None:
        """Displays a message to the user."""
        pass
    
    @abstractmethod
    def get_input(self, prompt: str) -> str:
        """Gets input from the user."""
        pass