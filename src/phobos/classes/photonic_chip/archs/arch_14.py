from ..arch import _Arch as Arch
from ....utils import Singleton

class Arch14(Arch, metaclass=Singleton):
    def __init__(self):
        super().__init__(
            name="Phase Actuator Solo",
            id="PM-T3",
            n_inputs=1,
            n_outputs=1,
            topas=(16,),
            number=14
        )
