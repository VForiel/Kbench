from ..photonic_chip import _Arch as Arch
from ..utils import Singleton

class Arch4(Arch, metaclass=Singleton):
    def __init__(self):
        super().__init__(
            name="1x2 MMI Solo",
            id="MMI1x2-T9",
            n_inputs=1,
            n_outputs=2,
            topas=(),
            number=4
        )
