from ..arch import _Arch as Arch
from ....utils import Singleton

class Arch7(Arch, metaclass=Singleton):
    def __init__(self):
        super().__init__(
            name="4-Port Nuller (passive) - FT",
            id="N4x4-D7",
            n_inputs=4,
            n_outputs=7,
            topas=(21,22,23,24),
            number=7
        )
