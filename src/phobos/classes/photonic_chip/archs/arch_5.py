from ..photonic_chip import _Arch as Arch
from ..utils import Singleton

class Arch5(Arch, metaclass=Singleton):
    def __init__(self):
        super().__init__(
            name="4-Port Nuller Reconfig",
            id="N4x4-D8",
            n_inputs=4,
            n_outputs=7,
            topas=(4,5,6,7,8,9,10,11,12,13,14,15,16),
            number=5
        )
