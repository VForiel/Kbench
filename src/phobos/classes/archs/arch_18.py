from ..photonic_chip import _Arch as Arch
from ..utils import Singleton

class Arch18(Arch, metaclass=Singleton):
    def __init__(self):
        super().__init__(
            name="3-Port Kernel Nuller",
            id="N3x3-D1",
            n_inputs=3,
            n_outputs=3,
            topas=(),
            number=18
        )
