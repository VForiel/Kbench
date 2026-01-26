from ..photonic_chip import _Arch as Arch
from ..utils import Singleton

class Arch8(Arch, metaclass=Singleton):
    def __init__(self):
        super().__init__(
            name="Mach-Zender Interferometer",
            id="MZI-T7",
            n_inputs=1,
            n_outputs=1,
            topas=(4,5),
            number=8
        )
