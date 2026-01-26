from ..arch import _Arch as Arch
from ....utils import Singleton

class Arch16(Arch, metaclass=Singleton):
    def __init__(self):
        super().__init__(
            name="Kernel Nuller 2x2 Reconfig N",
            id="N2x2-D3",
            n_inputs=4,
            n_outputs=7,
            topas=(29, 30, 31, 32),
            number=16
        )
