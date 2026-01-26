from ..arch import _Arch as Arch
from ....utils import Singleton

class Arch11(Arch, metaclass=Singleton):
    def __init__(self):
        super().__init__(
            name="3-Port Kernel Nuller (passive)",
            id="N3x3-D5",
            n_inputs=3,
            n_outputs=3,
            topas=(),
            number=11
        )
