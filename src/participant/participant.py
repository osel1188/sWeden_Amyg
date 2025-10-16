from dataclasses import dataclass

@dataclass
class Participant:
    """Data class for storing individual participant information."""
    id: str
    sex: str
    age: int

    def access_info(self) -> dict:
        """Returns participant information as a dictionary."""
        return {"id": self.id, "sex": self.sex, "age": self.age}