from abc import ABC, abstractmethod

class Migrater(ABC):

    @abstractmethod
    def push(self):
        raise NotImplementedError()
    
    @abstractmethod
    def pull(self):
        raise NotImplementedError()