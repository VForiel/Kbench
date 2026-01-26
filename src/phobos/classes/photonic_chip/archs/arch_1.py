from ..arch import _Arch as Arch
from ....utils import Singleton

class Arch1(Arch, metaclass=Singleton):
    def __init__(self):
        super().__init__(
            name="Mach-Zehnder Interferometer",
            id="MZI-T12",
            n_inputs=1,
            n_outputs=1,
            topas=(1,2),
            number=1
        )
