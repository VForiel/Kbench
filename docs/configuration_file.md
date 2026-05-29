# Configuration File

The configuration file is a YAML file that contains the settings for the PHOBos software. It is used to define the hardware connections and the position of the different elements.

File example:

```yaml
mask:
  slots:          # Virtual slots
    foo:          # Name of the mask
      a: 42.0     # angle in degree
      x: 10000    # x position in ticks
      y: 15000    # y position in ticks
    bar:
      a: 60.5
      x: 0
      y: 0

filter:
  slots:          # Virtual slots
    qux:          # Name of the filter
      slot: 1     # Physical slots

flip_mount:
  port: /dev/ttyUSBFlipMount
  stabilization_time: 0.5
```

Virtual slots allows to abstract the physical slots of the wheels and create as many slots as you want according to the scenario. For example, you can create a virtual slot "dot" that corresponds to the physical slot 1 of the mask wheel, and a slot "shifted_dot" that is also in the physical slot 1 but with a different position of the zabers.

The `flip_mount` section defines the serial port and settling time used by `phobos.FlipMount`.