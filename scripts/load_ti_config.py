# load_ti_config.py (MODIFIED)

from temporal_interference.ti_manager import TIManager
import traceback
import logging

if __name__ == '__main__':
    # Parameter for user modification.
    # This path should point to your JSON configuration file.
    path_file_config: str = 'config/ti_config.json'

    try:
        # 1. Initialize the manager with the specified configuration file.
        manager = TIManager(config_path=path_file_config)

        # 2. Verify successful loading by accessing and printing system data.
        print("\n--- Loaded TI System Infrastructure ---")
        if not manager.ti_systems:
            print("No TI systems were loaded from the configuration.")
        else:
            # Iterate over .items() to get system_key and system object
            for system_key, system in manager.ti_systems.items():
                
                print(f"\n==============================================")
                print(f"System Key: '{system_key}' (Region: '{system.region}')")
                print(f"  Total Channels: {len(system.channels)}")
                print(f"==============================================")
                
                if not system.channels:
                    print("  (No channels configured for this system)")
                    continue
                    
                # Iterate over the system's channels dictionary
                for channel_key, channel in system.channels.items():
                    print(f"\n  --- Channel Key: '{channel_key}' ---")
                    print(f"    Channel ID (str):    '{channel.channel_id}'")
                    print(f"    Physical Wavegen CH: {channel.wavegen_channel}")
                    
                    # --- Access generator from the channel ---
                    gen = channel.generator
                    if gen:
                        print(f"    Waveform Generator:")
                        try:
                            # Attempt to access properties assumed to be set by the factory.
                            print(f"      Model:    {gen.model}")
                            print(f"      Resource: {gen.resource_id}")
                        except AttributeError:
                            # Fallback if properties are not named as assumed
                            print(f"      Type:     {type(gen).__name__}")
                            print(f"      (Could not retrieve .model or .resource_id attributes)")
                    else:
                        print(f"    Waveform Generator: Not Assigned")

                    print(f"    Electrode Pair:")
                    # --- Access electrode pair from the channel ---
                    electrode_pair_obj = channel.pair
                    if electrode_pair_obj:
                        try:
                            electrode_list = electrode_pair_obj.electrodes
                            if len(electrode_list) == 2:
                                e1, e2 = electrode_list
                                print(f"      Electrode A: ID={e1.id}, Name='{e1.name}'")
                                print(f"      Electrode B: ID={e2.id}, Name='{e2.name}'")
                            else:
                                print(f"      (Invalid electrode pair: {len(electrode_list)} electrodes found)")
                        except AttributeError:
                            print("      (Could not find 'get_electrodes' method on pair object)")
                        except Exception as e:
                             print(f"      (Error accessing electrodes: {e})")
                    else:
                        print("    (No electrode pair assigned to this channel)")

        print("\n------------------------------")
        print("Initialization complete.")


    except FileNotFoundError:
        print(f"Error: Configuration file not found at '{path_file_config}'")
    except KeyError as e:
        print(f"Error: Missing expected key in configuration file: {e}")
    except ValueError as e:
        print(f"Error: Failed to initialize system: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        traceback.print_exc()