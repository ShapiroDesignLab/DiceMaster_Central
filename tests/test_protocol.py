#!/usr/bin/env python3
"""
Test script for protocol encoding/decoding validation
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DiceMaster_Central.media_typing.protocol import *
from DiceMaster_Central.config.constants import MessageType, Rotation, ImageFormat, ImageResolution

def test_text_batch_message():
    """Test TextBatchMessage encoding/decoding with detailed validation"""
    print("Testing TextBatchMessage...")
    
    # Create original message with comprehensive test data
    original = TextBatchMessage(
        bg_color=0x1234,
        font_color=0x5678,
        texts=[
            (10, 20, 1, "Hello"),
            (30, 40, 2, "World!"),
            (100, 200, 3, "Unicode: ñáéíóú"),
            (0, 0, 0, ""),  # Empty string test
            (65535, 65535, 255, "Max values")  # Test maximum values
        ],
        rotation=Rotation.ROTATION_270,
        msg_id=42
    )
    
    # Test encoding - should return the complete message in payload
    original.encode()
    assert len(original.payload) > 0, "Encoded message should have payload"
    
    # Decode the message
    decoded = TextBatchMessage.decode(original.payload)
    
    # Test equality using __eq__ method
    assert original == decoded, "Original and decoded messages should be equal using __eq__"
    
    # Validate individual fields for more detailed error reporting if needed
    assert decoded.msg_type == original.msg_type, f"Message type mismatch: {decoded.msg_type} != {original.msg_type}"
    assert decoded.msg_id == original.msg_id, f"Message ID mismatch: {decoded.msg_id} != {original.msg_id}"
    assert decoded.bg_color == original.bg_color, f"BG color mismatch: {decoded.bg_color} != {original.bg_color}"
    assert decoded.font_color == original.font_color, f"Font color mismatch: {decoded.font_color} != {original.font_color}"
    assert decoded.rotation == original.rotation, f"Rotation mismatch: {decoded.rotation} != {original.rotation}"
    assert decoded.texts == original.texts, f"Texts mismatch: {decoded.texts} != {original.texts}"
    
    # Test that different messages are not equal
    different_msg = TextBatchMessage(
        bg_color=0x0000,  # Different color
        font_color=0x5678,
        texts=[(10, 20, 1, "Hello")],
        rotation=Rotation.ROTATION_270,
        msg_id=42
    )
    assert original != different_msg, "Different messages should not be equal"
    
    print("  ✓ TextBatchMessage validation successful")
    return True

def test_image_start_message():
    """Test ImageStartMessage encoding/decoding with detailed validation"""
    print("Testing ImageStartMessage...")
    
    # Test with maximum values
    original = ImageStartMessage(
        image_id=255,
        image_format=ImageFormat.BMP,
        resolution=ImageResolution.RES_640x480,
        delay_time=255,
        total_size=16777215,  # Maximum 24-bit value
        num_chunks=255,
        rotation=Rotation.ROTATION_180,
        msg_id=123
    )
    
    # Test encoding - should return the complete message in payload
    original.encode()
    assert len(original.payload) > 0, "Encoded message should have payload"
    
    # Decode the message
    decoded = ImageStartMessage.decode(original.payload)

    # Test equality using __eq__ method
    assert original == decoded, "Original and decoded messages should be equal using __eq__"
    
    # Validate individual fields for more detailed error reporting
    assert decoded.msg_type == original.msg_type, f"Message type mismatch"
    assert decoded.msg_id == original.msg_id, f"Message ID mismatch"
    assert decoded.image_id == original.image_id, f"Image ID mismatch: {decoded.image_id} != {original.image_id}"
    assert decoded.image_format == original.image_format, f"Image format mismatch: {decoded.image_format} != {original.image_format}"
    assert decoded.resolution == original.resolution, f"Resolution mismatch: {decoded.resolution} != {original.resolution}"
    assert decoded.delay_time == original.delay_time, f"Delay time mismatch: {decoded.delay_time} != {original.delay_time}"
    assert decoded.total_size == original.total_size, f"Total size mismatch: {decoded.total_size} != {original.total_size}"
    assert decoded.num_chunks == original.num_chunks, f"Num chunks mismatch: {decoded.num_chunks} != {original.num_chunks}"
    assert decoded.rotation == original.rotation, f"Rotation mismatch: {decoded.rotation} != {original.rotation}"
    
    # Test that different messages are not equal
    different_msg = ImageStartMessage(
        image_id=128,  # Different ID
        image_format=ImageFormat.BMP,
        resolution=ImageResolution.RES_640x480,
        delay_time=255,
        total_size=16777215,
        num_chunks=255,
        rotation=Rotation.ROTATION_180,
        msg_id=123
    )
    assert original != different_msg, "Different messages should not be equal"
    
    print("  ✓ ImageStartMessage validation successful")
    return True

def test_image_chunk_message():
    """Test ImageChunkMessage encoding/decoding with detailed validation"""
    print("Testing ImageChunkMessage...")
    
    # Test with various chunk data sizes
    test_cases = [
        (b"", 0),  # Empty chunk
        (b"small", 100),  # Small chunk
        (b"X" * 1000, 50000),  # Medium chunk
        (b"Y" * 32768, 16777215)  # Large chunk at maximum location
    ]
    
    for i, (chunk_data, start_loc) in enumerate(test_cases):
        original = ImageChunkMessage(
            image_id=i + 1,
            chunk_id=i + 10,
            start_location=start_loc,
            chunk_data=chunk_data,
            msg_id=200 + i
        )
        
        # Test encoding
        original.encode()
        assert len(original.payload) > 0, f"Case {i}: Encoded message should have payload"
        
        # Decode the message
        decoded = ImageChunkMessage.decode(original.payload)
        
        # Test equality using __eq__ method
        assert original == decoded, f"Case {i}: Original and decoded messages should be equal using __eq__"
        
        # Validate individual fields for more detailed error reporting
        assert decoded.msg_type == original.msg_type, f"Case {i}: Message type mismatch"
        assert decoded.msg_id == original.msg_id, f"Case {i}: Message ID mismatch"
        assert decoded.image_id == original.image_id, f"Case {i}: Image ID mismatch: {decoded.image_id} != {original.image_id}"
        assert decoded.chunk_id == original.chunk_id, f"Case {i}: Chunk ID mismatch: {decoded.chunk_id} != {original.chunk_id}"
        assert decoded.start_location == original.start_location, f"Case {i}: Start location mismatch: {decoded.start_location} != {original.start_location}"
        assert decoded.chunk_data == original.chunk_data, f"Case {i}: Chunk data mismatch: length {len(decoded.chunk_data)} != {len(original.chunk_data)}"
    
    # Test that different messages are not equal
    msg1 = ImageChunkMessage(1, 1, 0, b"data1", msg_id=1)
    msg2 = ImageChunkMessage(1, 1, 0, b"data2", msg_id=1)  # Different data
    assert msg1 != msg2, "Messages with different chunk data should not be equal"
    
    print("  ✓ ImageChunkMessage validation successful")
    return True

def test_image_end_message():
    """Test ImageEndMessage encoding/decoding with detailed validation"""
    print("Testing ImageEndMessage...")
    
    original = ImageEndMessage(image_id=255, msg_id=45)
    
    # Test encoding
    original.encode()
    assert len(original.payload) > 0, "Encoded message should have payload"
    
    # Decode the message
    decoded = ImageEndMessage.decode(original.payload)
    
    # Test equality using __eq__ method
    assert original == decoded, "Original and decoded messages should be equal using __eq__"
    
    # Validate individual fields for more detailed error reporting
    assert decoded.msg_type == original.msg_type, f"Message type mismatch"
    assert decoded.msg_id == original.msg_id, f"Message ID mismatch"
    assert decoded.image_id == original.image_id, f"Image ID mismatch: {decoded.image_id} != {original.image_id}"
    
    # Test that different messages are not equal
    different_msg = ImageEndMessage(image_id=128, msg_id=45)  # Different image_id
    assert original != different_msg, "Messages with different image_id should not be equal"
    
    print("  ✓ ImageEndMessage validation successful")
    return True

def test_backlight_messages():
    """Test BacklightOnMessage and BacklightOffMessage encoding/decoding"""
    print("Testing Backlight messages...")
    
    # Test BacklightOnMessage
    original_on = BacklightOnMessage(msg_id=100)
    original_on.encode()
    assert len(original_on.payload) > 0, "BacklightOn: Encoded message should have payload"
    
    decoded_on = BacklightOnMessage.decode(original_on.payload)
    
    # Test equality using __eq__ method
    assert original_on == decoded_on, "BacklightOn: Original and decoded messages should be equal using __eq__"
    
    assert decoded_on.msg_type == original_on.msg_type, f"BacklightOn: Message type mismatch"
    assert decoded_on.msg_id == original_on.msg_id, f"BacklightOn: Message ID mismatch"
    
    # Test BacklightOffMessage
    original_off = BacklightOffMessage(msg_id=101)
    original_off.encode()
    assert len(original_off.payload) > 0, "BacklightOff: Encoded message should have payload"
    
    decoded_off = BacklightOffMessage.decode(original_off.payload)
    
    # Test equality using __eq__ method
    assert original_off == decoded_off, "BacklightOff: Original and decoded messages should be equal using __eq__"
    
    assert decoded_off.msg_type == original_off.msg_type, f"BacklightOff: Message type mismatch"
    assert decoded_off.msg_id == original_off.msg_id, f"BacklightOff: Message ID mismatch"
    
    # Test that different message types are not equal
    assert original_on != original_off, "BacklightOn and BacklightOff should not be equal"
    
    print("  ✓ Backlight messages validation successful")
    return True

def test_ping_messages():
    """Test PingRequestMessage and PingResponseMessage encoding/decoding"""
    print("Testing Ping messages...")
    
    # Test PingRequestMessage
    original_req = PingRequestMessage(msg_id=150)
    original_req.encode()
    assert len(original_req.payload) > 0, "PingRequest: Encoded message should have payload"
    
    decoded_req = PingRequestMessage.decode(original_req.payload)
    
    # Test equality using __eq__ method
    assert original_req == decoded_req, "PingRequest: Original and decoded messages should be equal using __eq__"
    
    assert decoded_req.msg_type == original_req.msg_type, f"PingRequest: Message type mismatch"
    assert decoded_req.msg_id == original_req.msg_id, f"PingRequest: Message ID mismatch"
    
    # Test PingResponseMessage with various status strings
    test_responses = [
        (0, "OK"),
        (1, "Warning: Low Memory"),
        (2, "Error: Display Failure"),
        (255, ""),  # Empty status string
        (128, "Unicode test: ñáéíóú")
    ]
    
    for status_code, status_string in test_responses:
        original_resp = PingResponseMessage(
            status_code=status_code,
            status_string=status_string,
            msg_id=151
        )
        
        original_resp.encode()
        assert len(original_resp.payload) > 0, f"PingResponse: Encoded message should have payload"
        
        decoded_resp = PingResponseMessage.decode(original_resp.payload)
        
        # Test equality using __eq__ method
        assert original_resp == decoded_resp, f"PingResponse: Original and decoded messages should be equal using __eq__ for ({status_code}, '{status_string}')"
        
        assert decoded_resp.msg_type == original_resp.msg_type, f"PingResponse: Message type mismatch"
        assert decoded_resp.msg_id == original_resp.msg_id, f"PingResponse: Message ID mismatch"
        assert decoded_resp.status_code == original_resp.status_code, f"PingResponse: Status code mismatch: {decoded_resp.status_code} != {original_resp.status_code}"
        assert decoded_resp.status_string == original_resp.status_string, f"PingResponse: Status string mismatch: '{decoded_resp.status_string}' != '{original_resp.status_string}'"
    
    # Test that different ping responses are not equal
    resp1 = PingResponseMessage(0, "OK", msg_id=151)
    resp2 = PingResponseMessage(1, "OK", msg_id=151)  # Different status code
    assert resp1 != resp2, "Ping responses with different status codes should not be equal"
    
    print("  ✓ Ping messages validation successful")
    return True

def test_ack_message():
    """Test AckMessage encoding/decoding with detailed validation"""
    print("Testing AckMessage...")
    
    test_cases = [0, 1, 127, 255]  # Various message IDs to acknowledge
    
    for ack_msg_id in test_cases:
        original = AckMessage(ack_msg_id=ack_msg_id, msg_id=200)
        
        # Test encoding
        original.encode()
        assert len(original.payload) > 0, f"ACK {ack_msg_id}: Encoded message should have payload"
        
        # Decode the message
        decoded = AckMessage.decode(original.payload)
        
        # Test equality using __eq__ method
        assert original == decoded, f"ACK {ack_msg_id}: Original and decoded messages should be equal using __eq__"
        
        # Validate individual fields for more detailed error reporting
        assert decoded.msg_type == original.msg_type, f"ACK {ack_msg_id}: Message type mismatch"
        assert decoded.msg_id == original.msg_id, f"ACK {ack_msg_id}: Message ID mismatch"
        assert decoded.ack_msg_id == original.ack_msg_id, f"ACK {ack_msg_id}: Ack message ID mismatch: {decoded.ack_msg_id} != {original.ack_msg_id}"
    
    # Test that different ACK messages are not equal
    ack1 = AckMessage(ack_msg_id=1, msg_id=200)
    ack2 = AckMessage(ack_msg_id=2, msg_id=200)  # Different ack_msg_id
    assert ack1 != ack2, "ACK messages with different ack_msg_id should not be equal"
    
    print("  ✓ AckMessage validation successful")
    return True

def test_error_message():
    """Test ErrorMessage encoding/decoding with detailed validation"""
    print("Testing ErrorMessage...")
    
    test_cases = [
        (0, 0),      # No error
        (42, 1),     # General error
        (255, 255),  # Maximum values
        (100, 128)   # Mid-range values
    ]
    
    for error_msg_id, error_code in test_cases:
        original = ErrorMessage(
            error_msg_id=error_msg_id,
            error_code=error_code,
            msg_id=250
        )
        
        # Test encoding
        original.encode()
        assert len(original.payload) > 0, f"Error ({error_msg_id}, {error_code}): Encoded message should have payload"
        
        # Decode the message
        decoded = ErrorMessage.decode(original.payload)
        
        # Test equality using __eq__ method
        assert original == decoded, f"Error ({error_msg_id}, {error_code}): Original and decoded messages should be equal using __eq__"
        
        # Validate individual fields for more detailed error reporting
        assert decoded.msg_type == original.msg_type, f"Error ({error_msg_id}, {error_code}): Message type mismatch"
        assert decoded.msg_id == original.msg_id, f"Error ({error_msg_id}, {error_code}): Message ID mismatch"
        assert decoded.error_msg_id == original.error_msg_id, f"Error ({error_msg_id}, {error_code}): Error message ID mismatch: {decoded.error_msg_id} != {original.error_msg_id}"
        assert decoded.error_code == original.error_code, f"Error ({error_msg_id}, {error_code}): Error code mismatch: {decoded.error_code} != {original.error_code}"
    
    # Test that different error messages are not equal
    err1 = ErrorMessage(error_msg_id=1, error_code=1, msg_id=250)
    err2 = ErrorMessage(error_msg_id=1, error_code=2, msg_id=250)  # Different error code
    assert err1 != err2, "Error messages with different error codes should not be equal"
    
    print("  ✓ ErrorMessage validation successful")
    return True

def test_payload_integrity():
    """Test that payloads are bit-perfect after round-trip"""
    print("Testing payload integrity...")
    
    # Test with binary data that might have encoding issues
    binary_data = bytes(range(256))  # All possible byte values
    
    chunk_msg = ImageChunkMessage(
        image_id=1,
        chunk_id=1,
        start_location=0,
        chunk_data=binary_data,
        msg_id=1
    )
    
    # Test encoding
    chunk_msg.encode()
    assert len(chunk_msg.payload) > 0, "Encoded message should have payload"
    
    # Decode the message
    decoded = ImageChunkMessage.decode(chunk_msg.payload)
    
    # Test equality using __eq__ method
    assert chunk_msg == decoded, "Original and decoded messages should be equal using __eq__"
    
    # Verify every byte is identical
    assert decoded.chunk_data == chunk_msg.chunk_data, "Binary data corruption detected"
    assert len(decoded.chunk_data) == len(chunk_msg.chunk_data), "Length mismatch in binary data"
    
    for i, (orig, dec) in enumerate(zip(chunk_msg.chunk_data, decoded.chunk_data)):
        assert orig == dec, f"Byte {i} mismatch: {dec} != {orig}"
    
    print("  ✓ Payload integrity validation successful")
    return True

def test_equality_system():
    """Test the __eq__ system comprehensively"""
    print("Testing equality system...")
    
    # Test that identical messages are equal
    msg1 = TextBatchMessage(
        bg_color=0x1234,
        font_color=0x5678,
        texts=[(10, 20, 1, "Hello")],
        rotation=Rotation.ROTATION_0,
        msg_id=42
    )
    
    msg2 = TextBatchMessage(
        bg_color=0x1234,
        font_color=0x5678,
        texts=[(10, 20, 1, "Hello")],
        rotation=Rotation.ROTATION_0,
        msg_id=42
    )
    
    assert msg1 == msg2, "Identical messages should be equal"
    
    # Test that messages with different content are not equal
    msg3 = TextBatchMessage(
        bg_color=0x0000,  # Different background color
        font_color=0x5678,
        texts=[(10, 20, 1, "Hello")],
        rotation=Rotation.ROTATION_0,
        msg_id=42
    )
    
    assert msg1 != msg3, "Messages with different content should not be equal"
    
    # Test that messages with different message IDs are not equal
    msg4 = TextBatchMessage(
        bg_color=0x1234,
        font_color=0x5678,
        texts=[(10, 20, 1, "Hello")],
        rotation=Rotation.ROTATION_0,
        msg_id=99  # Different message ID
    )
    
    assert msg1 != msg4, "Messages with different message IDs should not be equal"
    
    # Test equality with different message types
    ping_msg = PingRequestMessage(msg_id=42)
    assert msg1 != ping_msg, "Messages of different types should not be equal"
    
    # Test equality with non-ProtocolMessage objects
    assert msg1 != "not a message", "ProtocolMessage should not equal non-ProtocolMessage objects"
    assert msg1 != 42, "ProtocolMessage should not equal numbers"
    assert msg1 != None, "ProtocolMessage should not equal None"
    
    # Test ImageStartMessage equality
    img1 = ImageStartMessage(1, ImageFormat.BMP, ImageResolution.RES_240x240, 100, 1024, 4, Rotation.ROTATION_0, 1)
    img2 = ImageStartMessage(1, ImageFormat.BMP, ImageResolution.RES_240x240, 100, 1024, 4, Rotation.ROTATION_0, 1)
    img3 = ImageStartMessage(2, ImageFormat.BMP, ImageResolution.RES_240x240, 100, 1024, 4, Rotation.ROTATION_0, 1)  # Different image_id
    
    assert img1 == img2, "Identical ImageStartMessages should be equal"
    assert img1 != img3, "ImageStartMessages with different image_id should not be equal"
    
    print("  ✓ Equality system validation successful")
    return True

def main():
    """Run protocol validation tests"""
    print("=== Protocol Encoding/Decoding Validation ===\n")
    
    test_functions = [
        test_text_batch_message,
        test_image_start_message,
        test_image_chunk_message,
        test_image_end_message,
        test_backlight_messages,
        test_ping_messages,
        test_ack_message,
        test_error_message,
        test_equality_system,
        test_payload_integrity
    ]
    
    success_count = 0
    total_count = len(test_functions)
    
    for test_func in test_functions:
        try:
            if test_func():
                success_count += 1
        except Exception as e:
            print(f"  ✗ {test_func.__name__} failed with exception: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n=== Test Results ===")
    print(f"Passed: {success_count}/{total_count}")
    print(f"Success Rate: {success_count/total_count*100:.1f}%")
    
    if success_count == total_count:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed!")
        return 1

if __name__ == "__main__":
    exit(main())
