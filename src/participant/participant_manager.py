import uuid
from pathlib import Path
from typing import Dict, Optional
from .participant import Participant
from .participant_list import ParticipantList

class ParticipantManager:
    """High-level manager for all participant-related data and operations."""
    def __init__(self, data_path: Path):
        self.participant_list = ParticipantList()
        self.data_path = data_path
        self.data_path.mkdir(parents=True, exist_ok=True)

    def generate_id(self) -> str:
        """Generates a unique identifier for a new participant."""
        return str(uuid.uuid4())

    def participant_to_id(self, sex: str, age: int) -> Participant:
        """Creates a new Participant object with a unique ID."""
        new_id = self.generate_id()
        participant = Participant(id=new_id, sex=sex, age=age)
        self.participant_list.add_participant(participant)
        return participant

    def path_to_images(self, participant_id: str) -> Path:
        """Returns the designated storage path for a participant's images."""
        return self.data_path / participant_id / "images"

    def get_participant_info(self, participant_id: str) -> Optional[Dict]:
        """Retrieves the information for a specific participant."""
        participant = self.participant_list.get_participant(participant_id)
        return participant.access_info() if participant else None