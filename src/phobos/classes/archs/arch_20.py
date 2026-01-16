from ..photonic_chip import _Arch as Arch
from ..utils import Singleton

class Arch20(Arch, metaclass=Singleton):
    def __init__(self):
        super().__init__(
            name="2x2 MMI",
            id="MMI2x2-T1",
            n_inputs=2,
            n_outputs=2,
            topas=(),
            number=20
        )
