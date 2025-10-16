from typing import List, Optional
from .participant import Participant

class ParticipantList:
    """A collection class to manage a list of all experiment participants."""
    def __init__(self):
        self._participants: List[Participant] = []

    def add_participant(self, participant: Participant) -> None:
        """Adds a new participant to the list."""
        if not any(p.id == participant.id for p in self._participants):
            self._participants.append(participant)
    
    def get_participant(self, participant_id: str) -> Optional[Participant]:
        """Retrieves a participant by their ID."""
        for p in self._participants:
            if p.id == participant_id:
                return p
        return None

    def delete_participant(self, participant_id: str) -> bool:
        """Deletes a participant by their ID. Returns True if successful."""
        participant = self.get_participant(participant_id)
        if participant:
            self._participants.remove(participant)
            return True
        return False
    
    def get_all_participants(self) -> List[Participant]:
        """Returns the complete list of participants."""
        return self._participants