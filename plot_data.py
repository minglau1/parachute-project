import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import sys
import os

def plot_flight_data(csv_file=None):
    # --- 1. GUI FILE PICKER (If no file specified) ---
    if csv_file is None or not os.path.exists(csv_file):
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw() # Hide the main tkinter window
            print("Select your flight data CSV file...")
            csv_file = filedialog.askopenfilename(
                title="Select Flight Data CSV",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not csv_file:
                print("No file selected. Exiting.")
                return
        except ImportError:
            print(f"Error: Could not find '{csv_file}' and Tkinter is not installed for the file picker.")
            return

    try:
        print(f"Loading data from {csv_file}...")
        df = pd.read_csv(csv_file)
        
        if df.empty:
            print("Error: The flight data file is completely empty!")
            print("Please make sure you have run the flight computer and collected data before plotting.")
            return

        has_new_cols = 'Temp(C)' in df.columns
        
        # --- 2. RELATIVE ALTITUDE ZEROING ---
        # Average the first 10 readings to find the "Launchpad Altitude" and zero it out!
        ground_altitude = df['R.Altitude(m)'].head(10).mean()
        df['Relative_Alt(m)'] = df['R.Altitude(m)'] - ground_altitude
        
        # --- Derived Metrics (Analytics) ---
        df['Smoothed_Alt'] = df['Relative_Alt(m)'].rolling(window=5, min_periods=1).mean()
        df['Velocity(m/s)'] = df['Smoothed_Alt'].diff() / df['Time(s)'].diff()
        df['Velocity(m/s)'] = df['Velocity(m/s)'].fillna(0)
        
        # Identify key events
        max_alt = df['Relative_Alt(m)'].max()
        apogee_idx = df['Relative_Alt(m)'].idxmax()
        apogee_time = df.loc[apogee_idx, 'Time(s)']
        max_g = df['G-Force(G)'].max()
        
        deployment_time = None
        for index, row in df.iterrows():
            event = str(row['Event']).strip()
            if event and event != 'nan' and 'DEPLOYED' in event:
                deployment_time = row['Time(s)']
                break
                
        # Calculate Descent Rate
        descent_rate = 0
        if deployment_time is not None:
            post_deploy_data = df[df['Time(s)'] > deployment_time]
            if not post_deploy_data.empty:
                descent_rate = abs(post_deploy_data['Velocity(m/s)'].mean())

        # --- Plot Setup ---
        num_plots = 4 if has_new_cols else 3
        # Use a modern style if available
        plt.style.use('ggplot')
        fig, axes = plt.subplots(num_plots, 1, figsize=(12, 3.5 * num_plots), sharex=True)
        fig.canvas.manager.set_window_title('Rocket Flight Telemetry Dashboard')
        
        ax1, ax2, ax3 = axes[0], axes[1], axes[2]
        ax4 = axes[3] if has_new_cols else None

        # Helper function to shade flight phases
        def shade_flight_phases(ax):
            # Ascent Phase (Start to Apogee)
            ax.axvspan(0, apogee_time, color='skyblue', alpha=0.2, label='Ascent Phase' if ax==ax1 else "")
            if deployment_time:
                # Coast/Freefall Phase (Apogee to Deployment)
                ax.axvspan(apogee_time, deployment_time, color='salmon', alpha=0.2, label='Freefall' if ax==ax1 else "")
                # Descent Phase (Deployment to End)
                end_time = df['Time(s)'].max()
                ax.axvspan(deployment_time, end_time, color='lightgreen', alpha=0.2, label='Descent (Parachute)' if ax==ax1 else "")

        # --- 1. Plot Altitude ---
        shade_flight_phases(ax1)
        ax1.plot(df['Time(s)'], df['Relative_Alt(m)'], 'b-', linewidth=2.5, label='Relative Altitude')
        ax1.set_ylabel('Relative Altitude (m)', color='darkblue', fontweight='bold')
        ax1.set_title(f'Rocket Flight Analysis - {os.path.basename(csv_file)}', fontsize=16, fontweight='bold')
        
        # Annotate Apogee with a cool arrow
        ax1.annotate(f'Apogee ({max_alt:.1f}m)', xy=(apogee_time, max_alt), xytext=(apogee_time + 0.5, max_alt),
                     arrowprops=dict(facecolor='red', shrink=0.05, width=2, headwidth=8),
                     fontsize=11, color='red', fontweight='bold')
                     
        if deployment_time:
            ax1.axvline(x=deployment_time, color='red', linestyle='--', linewidth=2)
            ax1.text(deployment_time, max_alt * 0.8, ' Parachute Deployed', color='red', rotation=90, fontweight='bold')

        leg1 = ax1.legend(loc='upper right', framealpha=0.9)
        if hasattr(leg1, 'set_draggable'): leg1.set_draggable(True)

        # --- Flight Statistics Text Box ---
        stats_text = (
            f"★ FLIGHT SUMMARY ★\n"
            f"Launchpad Offset: {ground_altitude:.1f} m\n"
            f"Max R.Altitude: {max_alt:.1f} m\n"
            f"Max G-Force: {max_g:.1f} G\n"
            f"Apogee Time: {apogee_time:.1f} s\n"
        )
        if deployment_time is not None:
            stats_text += f"Parachute Deployed: {deployment_time:.1f} s\n"
            stats_text += f"Avg Descent Rate: {descent_rate:.1f} m/s\n"
        if has_new_cols:
            stats_text += f"Min Temp: {df['Temp(C)'].min():.1f} °C"
            
        props = dict(boxstyle='round,pad=0.5', facecolor='ivory', edgecolor='black', alpha=0.9)
        # Use annotate instead of text so we can make it draggable!
        stats_box = ax1.annotate(stats_text, xy=(0.02, 0.95), xycoords='axes fraction',
                                 fontsize=11, verticalalignment='top', bbox=props, fontfamily='monospace')
        
        # We MUST attach the draggable object to 'fig' so Python's garbage collector doesn't delete it!
        if hasattr(stats_box, 'set_draggable'): 
            fig._draggable_box = stats_box.set_draggable(True)
        elif hasattr(stats_box, 'draggable'):
            fig._draggable_box = stats_box.draggable(True)

        # --- 2. Plot Velocity ---
        shade_flight_phases(ax2)
        ax2.plot(df['Time(s)'], df['Velocity(m/s)'], color='purple', linewidth=2, label='Vertical Velocity')
        ax2.set_ylabel('Velocity (m/s)', color='purple', fontweight='bold')
        ax2.axhline(y=0.0, color='black', linestyle='-', linewidth=1)
        if deployment_time: ax2.axvline(x=deployment_time, color='red', linestyle='--')
        leg2 = ax2.legend(loc='upper right')
        if hasattr(leg2, 'set_draggable'): leg2.set_draggable(True)

        # --- 3. Plot G-Force ---
        shade_flight_phases(ax3)
        if has_new_cols:
            ax3.plot(df['Time(s)'], df['Accel_X'], color='red', alpha=0.4, linewidth=1, label='Accel X')
            ax3.plot(df['Time(s)'], df['Accel_Y'], color='blue', alpha=0.4, linewidth=1, label='Accel Y')
            ax3.plot(df['Time(s)'], df['Accel_Z'], color='orange', alpha=0.4, linewidth=1, label='Accel Z')
            
        ax3.plot(df['Time(s)'], df['G-Force(G)'], 'g-', linewidth=2.5, label='Total G-Force')
        
        if not has_new_cols:
            ax3.set_xlabel('Time (Seconds)', fontsize=12, fontweight='bold')
        ax3.set_ylabel('G-Force (G)', color='green', fontweight='bold')
        ax3.axhline(y=1.0, color='black', linestyle=':', label='1G (Resting)')
        ax3.axhline(y=0.0, color='gray', linestyle=':', label='0G (Freefall)')
        if deployment_time: ax3.axvline(x=deployment_time, color='red', linestyle='--')
        leg3 = ax3.legend(loc='upper right')
        if hasattr(leg3, 'set_draggable'): leg3.set_draggable(True)

        # --- 4. Plot Temperature (If Available) ---
        if has_new_cols:
            shade_flight_phases(ax4)
            ax4.plot(df['Time(s)'], df['Temp(C)'], color='darkorange', linewidth=2.5, label='Temperature')
            ax4.set_xlabel('Time (Seconds)', fontsize=12, fontweight='bold')
            ax4.set_ylabel('Temp (°C)', color='darkorange', fontweight='bold')
            if deployment_time: ax4.axvline(x=deployment_time, color='red', linestyle='--')
            leg4 = ax4.legend(loc='upper right')
            if hasattr(leg4, 'set_draggable'): leg4.set_draggable(True)

        # --- Interactive Cursor & Display ---
        plt.tight_layout()
        
        # Ensure the output directory exists
        output_dir = os.path.join("flight data collection", "png")
        os.makedirs(output_dir, exist_ok=True)
        
        # Auto-save a high-res image of the flight in the specific folder
        base_name = os.path.basename(csv_file)
        name_only = os.path.splitext(base_name)[0]
        output_png = os.path.join(output_dir, f"{name_only}_report.png")
        plt.savefig(output_png, dpi=300)
        
        print("\n" + stats_text.replace('★ FLIGHT SUMMARY ★\n', '--- SUMMARY ---\n'))
        print(f"\n=> High-resolution flight report saved to: {output_png}")
        print("=> Graph generated! You can pan and zoom using the toolbar at the bottom.")
        plt.show()

    except Exception as e:
        print(f"An error occurred while plotting: {e}")

if __name__ == "__main__":
    # If the user drags and drops a CSV file onto the script, use it
    if len(sys.argv) > 1:
        plot_flight_data(sys.argv[1])
    else:
        # Launch the GUI file picker to let the user choose the flight data
        plot_flight_data(None)