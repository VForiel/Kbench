import numpy as np
# import matplotlib.pyplot as plt
# import matplotlib.animation as animation
# from matplotlib.patches import Circle
# import astropy.units as u


def atmo_screen_kolmogorov(size, physical_size, r0, L0, fc=25, correc=1.0):
    """
    Generate a Kolmogorov-Von Karman type atmospheric phase screen.
    
    Parameters
    ----------
    size : int
        Screen size in pixels (size x size)
    physical_size : float
        Physical extent of the screen in meters
    r0 : float
        Fried parameter in meters (at a reference wavelength)
    L0 : float
        Outer scale in meters
    fc : float, optional
        Cutoff frequency for AO correction (in cycles across the screen)
    correc : float, optional
        Amplitude correction factor up to fc
        
    Returns
    -------
    ndarray
        Phase screen in radians (size x size)
    """
    # Random phase generation
    phs = 2 * np.pi * (np.random.rand(size, size) - 0.5)
    
    # Spatial frequency grid
    xx, yy = np.meshgrid(np.arange(size) - size/2, np.arange(size) - size/2)
    rr = np.hypot(yy, xx)
    rr = np.fft.fftshift(rr)
    rr[0, 0] = 1.0  # Avoid division by zero
    
    # Von Karman power spectrum
    modul = (rr**2 + (physical_size/L0)**2)**(-11/12.)
    
    # Apply AO correction
    in_fc = (rr < fc * physical_size / physical_size)  # fc cycles across screen
    modul[in_fc] /= correc
    
    # Screen generation via inverse Fourier transform
    screen = np.fft.ifft2(modul * np.exp(1j * phs)) * size**2
    screen *= np.sqrt(2 * 0.0228) * (physical_size / r0)**(5/6.)
    
    # Normalization
    screen = screen.real
    screen -= screen.mean()
    
    return screen


def get_delays(
    n_telescopes=4,
    telescope_diameter=1.8,
    telescope_positions=None,
    r0=0.8,
    L0=25.0,
    wavelength=1.65e-6,
    wind_speed=10.0,
    wind_direction=45.0,
    screen_size=512,
    screen_physical_size=None,
    time_step=0.1,
    n_steps=100,
    demo=False
):
    """
    Calculate atmospheric phase delays for multiple telescopes.
    
    The atmosphere follows a Kolmogorov-Von Karman model that evolves in time 
    by moving with a given wind speed and direction (frozen flow turbulence model).
    
    Parameters
    ----------
    n_telescopes : int, optional
        Number of telescopes (default: 4)
    telescope_diameter : float, optional
        Telescope diameter in meters (default: 1.8 m)
    telescope_positions : ndarray, optional
        Telescope positions in meters, array of shape (n_telescopes, 2).
        If None, uses a square configuration. (default: None)
    r0 : float, optional
        Fried parameter in meters at reference wavelength 1.55 μm.
        Typical values at 1.55 μm: 0.5 m (poor), 0.8 m (average), 1.0 m (good), 1.5 m (excellent)
        (default: 0.8)
    L0 : float, optional
        Outer scale of turbulence in meters (default: 25.0)
    wavelength : float, optional
        Observation wavelength in meters (default: 1.65e-6, H-band)
    wind_speed : float, optional
        Wind speed in m/s (default: 10.0)
    wind_direction : float, optional
        Wind direction in degrees (0° = East, 90° = North) (default: 45.0)
    screen_size : int, optional
        Phase screen size in pixels (default: 512)
    screen_physical_size : float, optional
        Physical screen size in meters. If None, automatically calculated
        from telescope positions and diameter with 20% margin (default: None)
    time_step : float, optional
        Time step in seconds (default: 0.1)
    n_steps : int, optional
        Number of time steps to calculate (default: 100)
    demo : bool, optional
        If True, displays an animation of atmospheric evolution 
        (default: False)
        
    Returns
    -------
    delays : ndarray
        Phase delays for each telescope in nanometers.
        Shape: (n_steps, n_telescopes)
    times : ndarray
        Corresponding times in seconds. Shape: (n_steps,)
        
    Examples
    --------
    >>> # Simple configuration with 4 telescopes
    >>> delays, times = get_delays(n_telescopes=4, demo=True)
    
    >>> # Custom configuration
    >>> positions = np.array([[0, 0], [10, 0], [10, 10], [0, 10]])
    >>> delays, times = get_delays(
    ...     telescope_positions=positions,
    ...     wind_speed=15.0,
    ...     wind_direction=30.0,
    ...     demo=False
    ... )
    """
    # Telescope position configuration
    if telescope_positions is None:
        # Default square configuration
        baseline = 20.0  # 20 meters between telescopes
        if n_telescopes == 4:
            telescope_positions = np.array([
                [-baseline/2, -baseline/2],
                [baseline/2, -baseline/2],
                [baseline/2, baseline/2],
                [-baseline/2, baseline/2]
            ])
        elif n_telescopes == 3:
            # Equilateral triangle
            angle = np.array([0, 120, 240]) * np.pi / 180
            telescope_positions = baseline * np.column_stack([
                np.cos(angle),
                np.sin(angle)
            ])
        else:
            # Circle
            angle = np.linspace(0, 2*np.pi, n_telescopes, endpoint=False)
            telescope_positions = baseline * np.column_stack([
                np.cos(angle),
                np.sin(angle)
            ])
    else:
        n_telescopes = len(telescope_positions)
    
    # Center telescope positions around origin for proper display
    telescope_positions = telescope_positions - np.mean(telescope_positions, axis=0)
    
    # Auto-calculate screen_physical_size if not provided
    if screen_physical_size is None:
        # Find bounding box of all telescopes
        min_x = np.min(telescope_positions[:, 0]) - telescope_diameter/2
        max_x = np.max(telescope_positions[:, 0]) + telescope_diameter/2
        min_y = np.min(telescope_positions[:, 1]) - telescope_diameter/2
        max_y = np.max(telescope_positions[:, 1]) + telescope_diameter/2
        
        # Take the maximum extent and add 20% margin
        extent_x = max_x - min_x
        extent_y = max_y - min_y
        screen_physical_size = max(extent_x, extent_y) * 1.2
        
        # Ensure minimum size (for single telescope or very small arrays)
        screen_physical_size = max(screen_physical_size, telescope_diameter * 3)
        
        if demo:
            print(f"Auto-calculated screen size: {screen_physical_size:.1f} m")
    
    # Scale r0 to observation wavelength
    # r0(λ) = r0(1.55μm) * (λ/1.55μm)^(6/5)
    r0_obs = r0 * (wavelength / 1.55e-6)**(6/5)
    
    # Generate initial phase screen
    phase_screen = atmo_screen_kolmogorov(
        screen_size, 
        screen_physical_size, 
        r0_obs, 
        L0
    )
    
    # Double the screen to allow scrolling
    phase_screen_large = np.tile(phase_screen, (2, 2))
    
    # Convert wind to pixels per time step
    pixel_scale = screen_physical_size / screen_size  # meters per pixel
    wind_direction_rad = wind_direction * np.pi / 180
    wind_vx = wind_speed * np.cos(wind_direction_rad)
    wind_vy = wind_speed * np.sin(wind_direction_rad)
    
    # Displacement in pixels per time step
    dx_per_step = wind_vx * time_step / pixel_scale
    dy_per_step = wind_vy * time_step / pixel_scale
    
    # Calculate telescope positions in pixels
    center_x = screen_size / 2
    center_y = screen_size / 2
    tel_pos_pix = telescope_positions / pixel_scale
    tel_pos_pix[:, 0] += center_x
    tel_pos_pix[:, 1] += center_y
    
    # Telescope radius in pixels
    tel_radius_pix = telescope_diameter / 2 / pixel_scale
    
    # Storage for results
    delays = np.zeros((n_steps, n_telescopes))
    times = np.arange(n_steps) * time_step
    
    # Pre-calculate all delays (ALWAYS run this)
    # This ensures we have data to return even if we don't show the animation
    current_offset_x = 0.0
    current_offset_y = 0.0
    
    for step in range(n_steps):
        # Update screen position
        current_offset_x += dx_per_step
        current_offset_y += dy_per_step
        
        # Modulo to stay within large screen
        offset_x_int = int(current_offset_x) % screen_size
        offset_y_int = int(current_offset_y) % screen_size
        
        # Extract visible region
        current_screen = phase_screen_large[
            offset_x_int:offset_x_int+screen_size,
            offset_y_int:offset_y_int+screen_size
        ]
        
        # Calculate phase delays for each telescope
        for i in range(n_telescopes):
            # Create circular mask for telescope
            y_grid, x_grid = np.ogrid[:screen_size, :screen_size]
            mask = ((x_grid - tel_pos_pix[i, 0])**2 + 
                   (y_grid - tel_pos_pix[i, 1])**2 <= tel_radius_pix**2)
            
            # Calculate mean phase over telescope
            if np.any(mask):
                phase_mean_rad = np.mean(current_screen[mask])
                # Convert to nanometers (OPD)
                # OPD = (phi / 2pi) * lambda
                delays[step, i] = phase_mean_rad * wavelength / (2 * np.pi) * 1e9
            else:
                delays[step, i] = 0.0

    # Animation if demo mode
    if demo:
        import matplotlib.pyplot as plt
        import matplotlib.animation as animation
        from matplotlib.patches import Circle
        
        # Fixed layout info
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        
        # Prepare figure for phase screen
        im = ax1.imshow(
            phase_screen, 
            extent=[0, screen_physical_size, 0, screen_physical_size],
            origin='lower',
            cmap='RdBu_r',
            vmin=-3*np.std(phase_screen),
            vmax=3*np.std(phase_screen),
            zorder=1
        )
        ax1.set_xlabel('Position X (m)')
        ax1.set_ylabel('Position Y (m)')
        ax1.set_title('Atmospheric Phase Screen')
        plt.colorbar(im, ax=ax1, label='Phase (rad)')
        
        # Add circles for telescopes
        tel_circles = []
        for i in range(n_telescopes):
            pos_x = telescope_positions[i, 0] + screen_physical_size/2
            pos_y = telescope_positions[i, 1] + screen_physical_size/2
            circle = Circle(
                (pos_x, pos_y), 
                telescope_diameter/2, 
                fill=False, 
                edgecolor='lime', 
                linewidth=2,
                zorder=3,
                label=f'Tel {i+1}' if i == 0 else ''
            )
            ax1.add_patch(circle)
            tel_circles.append(circle)

        # Add global title
        fig.suptitle(
            f'Atmospheric Turbulence Simulation\nλ = {wavelength*1e6:.2f} μm, r0 = {r0:.2f} m, Wind = {wind_speed:.1f} m/s',
            fontsize=12, fontweight='bold'
        )
        
        # Prepare figure for delays
        colors = plt.cm.tab10(np.linspace(0, 1, n_telescopes))
        lines = []
        for i in range(n_telescopes):
            line, = ax2.plot([], [], '-o', color=colors[i], 
                           label=f'Telescope {i+1}', markersize=2, alpha=0.7)
            lines.append(line)
        
        ax2.set_xlabel('Time (s)')
        ax2.set_ylabel('Phase Delay (nm)')
        ax2.set_title('Phase Delays per Telescope')
        ax2.legend(loc='upper right', fontsize='small')
        ax2.grid(True, alpha=0.3)
        
        # Set limits
        delay_min = np.min(delays)
        delay_max = np.max(delays)
        margin = (delay_max - delay_min) * 0.1 if delay_max > delay_min else 1.0
        ax2.set_ylim(delay_min - margin, delay_max + margin)
        ax2.set_xlim(0, times[-1])
        
        def update_frame(frame):
            # Reconstruct screen position
            # frame is 0-indexed step
            # step k in loop corresponds to delays[k]
            # Offset was updated at start of loop: (k+1)*dx
            
            off_x = (frame + 1) * dx_per_step
            off_y = (frame + 1) * dy_per_step
            
            off_x_int = int(off_x) % screen_size
            off_y_int = int(off_y) % screen_size
            
            current_vis_screen = phase_screen_large[
                off_x_int:off_x_int+screen_size,
                off_y_int:off_y_int+screen_size
            ]
            
            # Update display
            im.set_data(current_vis_screen)
            
            # Update delay curves
            for i in range(n_telescopes):
                lines[i].set_data(times[:frame+1], delays[:frame+1, i])
            
            return [im] + lines + tel_circles
        
        anim = animation.FuncAnimation(
            fig, update_frame, frames=n_steps,
            interval=min(50, max(1, int(time_step*1000))), 
            blit=False, repeat=True
        )
        
        print("Displaying animation... (Close window to continue)")
        try:
            plt.show()
        except Exception as e:
            print(f"Animation display warning: {e}")
        
    return delays, times


if __name__ == "__main__":
    # Example usage
    print("Kolmogorov-type atmospheric simulation for PHOBos")
    print("=" * 60)

    # Get telescope positions (example: UTs at Paranal)
    import astropy.units as u
    
    # Coordinates in (Longitude, Latitude) degrees
    r_deg = np.array([
        [-70.4048732988764, -24.627602893919807], 
        [-70.40465753243652, -24.627118902835786], 
        [-70.40439460074228, -24.62681028261176], 
        [-70.40384287956437, -24.627033500373024]
    ])
    
    # Reference (first telescope)
    ref_pos = r_deg[0]
    r_diff = r_deg - ref_pos # Differences in degrees
    
    earth_radius = 6378137 * u.m
    UTs_elevation = 2635 * u.m
    R = earth_radius + UTs_elevation
    
    # Convert differences to meters
    # x = dLon * R * cos(Lat)
    # y = dLat * R
    
    lat_rad = np.radians(ref_pos[1])
    d_lon_rad = np.radians(r_diff[:, 0])
    d_lat_rad = np.radians(r_diff[:, 1])
    
    x_pos = d_lon_rad * R * np.cos(lat_rad)
    y_pos = d_lat_rad * R
    
    # Combine into (x, y) array
    telescope_positions_m = np.column_stack([x_pos.value, y_pos.value])

    print(f"Telescope positions (center relative):\n{telescope_positions_m - np.mean(telescope_positions_m, axis=0)}")
    
    # Test with demo mode
    delays, times = get_delays(
        n_telescopes=4,
        telescope_diameter=8,
        telescope_positions=telescope_positions_m,
        r0=0.8,  # Average seeing at 1.55 μm
        L0=25.0,
        wavelength=1.55e-6,
        wind_speed=10.0,
        wind_direction=45.0,
        time_step=0.05, 
        n_steps=200,    
        demo=True
    )
    
    print(f"\nPhase delay statistics:")
    print(f"  Array shape: {delays.shape}")
    print(f"  Total duration: {times[-1]:.2f} s")
    print(f"  Global RMS: {np.std(delays):.2f} nm")
    for i in range(delays.shape[1]):
        print(f"  Telescope {i+1} - RMS: {np.std(delays[:, i]):.2f} nm")
