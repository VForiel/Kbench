from ..arch import _Arch as Arch
from ....utils import Singleton

class Arch3(Arch, metaclass=Singleton):
    def __init__(self):
        super().__init__(
            name="2x2 MMI Solo",
            id="MMI2x2-T10",
            n_inputs=2,
            n_outputs=2,
            topas=(),
            number=3
        )
