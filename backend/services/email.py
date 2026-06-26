from abc import ABC, abstractmethod

class EmailProviderBase(ABC):
    @abstractmethod
    def authenticate(self):
        pass

    @abstractmethod
    def list_emails(self, folder: str, max_results: int):
        pass

    @abstractmethod
    def read_email(self, thread_id: str):
        pass

    @abstractmethod
    def search_emails(self, query: str, max_results: int):
        pass

    @abstractmethod
    def draft_email(self, to: str, subject: str, body: str):
        pass

    @abstractmethod
    def send_email(self, draft_id: str):
        pass

class GmailProvider(EmailProviderBase):
    def __init__(self):
        # Setup Gmail OAuth with scope 'https://www.googleapis.com/auth/gmail.modify'
        pass

    def authenticate(self):
        return True

    def list_emails(self, folder: str, max_results: int):
        return []

    def read_email(self, thread_id: str):
        return {"id": thread_id, "messages": []}

    def search_emails(self, query: str, max_results: int):
        return []

    def draft_email(self, to: str, subject: str, body: str):
        return "draft_123"

    def send_email(self, draft_id: str):
        return True
