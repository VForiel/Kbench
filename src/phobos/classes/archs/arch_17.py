from ..photonic_chip import _Arch as Arch
from ..utils import Singleton

class Arch17(Arch, metaclass=Singleton):
    def __init__(self):
        super().__init__(
            name="Passive Kernel Nuller",
            id="N2x2-D2",
            n_inputs=4,
            n_outputs=7,
            topas=(),
            number=17
        )
