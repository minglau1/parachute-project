import pandas as pd
import matplotlib.pyplot as plt

def plot_flight_data(csv_file):
    try:
        print(f"Loading data from {csv_file}...")
        # Load the CSV data into a pandas DataFrame
        df = pd.read_csv(csv_file)
        
        # Create a figure with 2 subplots (one for altitude, one for G-force)
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

        # --- 1. Plot Altitude ---
        ax1.plot(df['Time(s)'], df['Altitude(m)'], 'b-', linewidth=2, label='Altitude')
        ax1.set_ylabel('Altitude (m)', color='b', fontsize=12)
        ax1.tick_params(axis='y', labelcolor='b')
        ax1.set_title('Rocket Flight Telemetry', fontsize=16)
        ax1.grid(True, linestyle='--', alpha=0.7)

        # Highlight events like Parachute Deployment or Errors
        for index, row in df.iterrows():
            event = str(row['Event']).strip()
            if event and event != 'nan':
                if 'DEPLOYED' in event:
                    ax1.axvline(x=row['Time(s)'], color='red', linestyle='--', linewidth=2)
                    ax1.text(row['Time(s)'], df['Altitude(m)'].max(), ' Parachute Deployed', color='red', rotation=90, verticalalignment='top')
                elif 'Error' in event:
                    ax1.axvline(x=row['Time(s)'], color='orange', linestyle=':', linewidth=1)

        # --- 2. Plot G-Force ---
        ax2.plot(df['Time(s)'], df['G-Force(G)'], 'g-', linewidth=2, label='G-Force')
        ax2.set_xlabel('Time (Seconds)', fontsize=12)
        ax2.set_ylabel('G-Force (G)', color='g', fontsize=12)
        ax2.tick_params(axis='y', labelcolor='g')
        ax2.grid(True, linestyle='--', alpha=0.7)
        
        # Add a baseline for 1G (normal gravity)
        ax2.axhline(y=1.0, color='black', linestyle=':', label='1G (Resting)')
        ax2.axhline(y=0.0, color='gray', linestyle=':', label='0G (Freefall)')
        ax2.legend(loc='upper right')

        # Display the graph
        plt.tight_layout()
        print("Graph generated! Close the graph window to exit.")
        plt.show()

    except FileNotFoundError:
        print(f"Error: Could not find {csv_file}. Make sure you pulled it from your Pico!")
    except Exception as e:
        print(f"An error occurred while plotting: {e}")

if __name__ == "__main__":
    # Make sure you copy flight_data.csv from the Pico to your PC folder first!
    plot_flight_data('flight_data.csv')
