from ..photonic_chip import _Arch as Arch
from ..utils import Singleton

class Arch10(Arch, metaclass=Singleton):
    def __init__(self):
        super().__init__(
            name="4-Port Nuller (4x4 MMI) Passive Crazy",
            id="N4x4-D6",
            n_inputs=4,
            n_outputs=7,
            topas=(),
            number=10
        )
