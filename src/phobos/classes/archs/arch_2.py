from ..photonic_chip import _Arch as Arch
from ..utils import Singleton

class Arch2(Arch, metaclass=Singleton):
    def __init__(self):
        super().__init__(
            name="Phase Shifter Solo",
            id="PM-T11",
            n_inputs=1,
            n_outputs=1,
            topas=(3,),
            number=2
        )
