import machine
import time

# # Use "LED" for Pico W or 25 for regular Pico
# led = machine.Pin("LED", machine.Pin.OUT)

# print("Starting blink test...")
# for i in range(5):
#     led.toggle()
#     print(f"Blink {i+1}")
#     time.sleep(0.5)
# print("Done!")


# commend mpremote: 
# mpremote reset (reboot the board)
# mpremote fs cp test.py :main.py (push the code to the board)
# mpremote run test.py (run the code)


servo_pin = machine.Pin(0)
servo = machine.PWM(servo_pin)
servo.freq(50) # Standard servo frequency is 50Hz
angle = 0
# Helper function to move the servo
def set_servo_angle(angle):
    # Map an angle (0 to 180) to a PWM duty cycle for an SG90 servo
    # Many SG90 servos actually need a wider range (0.5ms to 2.5ms) 
    # to achieve a full 180 degrees of rotation.
    # 0.5ms = ~1638, 2.5ms = ~8192 out of 65535
    min_duty = 1638  
    max_duty = 8192
    duty = int(min_duty + (angle / 180.0) * (max_duty - min_duty))
    servo.duty_u16(duty)

print("Starting servo test...")
# Loop back and forth 3 times
for _ in range(3):
    print("Moving to 90 degrees (Release)")
    set_servo_angle(90)
    time.sleep(2)  # Wait for it to reach 90
    
    print("Moving to 0 degrees (Locked)")
    set_servo_angle(0)
    time.sleep(2)  # Wait for it to reach 0

print("Test complete. Servo should be locked at 0.")
time.sleep(1) # Give it final time to settle before the program ends and cuts the signal