from ..photonic_chip import _Arch as Arch
from ..utils import Singleton

class Arch19(Arch, metaclass=Singleton):
    def __init__(self):
        super().__init__(
            name="2x2 MMI",
            id="N4x4-T2",
            n_inputs=4,
            n_outputs=4,
            topas=(),
            number=19
        )
