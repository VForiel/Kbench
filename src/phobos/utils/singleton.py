
class Singleton(type):
    """
    Metaclass to implement the Singleton pattern.
    
    Ensures that a class has only one instance.
    The instance is created on the first call, and subsequent calls return the same instance.
    Arguments passed to subsequent calls are IGNORED.
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

    def _reset_instance(cls):
        """
        Force destruction of the singleton instance.
        
        Use this if you need to re-initialize the object (e.g. after config change).
        """
        if cls in cls._instances:
            del cls._instances[cls]
