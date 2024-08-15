import subprocess
import sys

def set_system_time(new_time):
    # Disable time synchronization
    subprocess.run(['sudo', 'timedatectl', 'set-ntp', 'false'], check=True)
    
    try:
        # Update system time
        subprocess.run(['sudo', 'date', '-s', new_time], check=True)
        print(f"System time updated to: {new_time}")
    except Exception as e:
        print(f"Error updating system time: {e}")
    finally:
        # Re-enable time synchronization
        subprocess.run(['sudo', 'timedatectl', 'set-ntp', 'true'], check=True)
        print("Time synchronization re-enabled.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: sudo python3 update_time.py 'YYYY-MM-DD HH:MM:SS'")
        sys.exit(1)
    
    new_time = sys.argv[1]
    set_system_time(new_time)