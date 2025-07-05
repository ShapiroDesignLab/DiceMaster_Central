#!/usr/bin/env python3
"""
Test script for protocol encoding/decoding validation
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DiceMaster_Central.protocol import *
from DiceMaster_Central.constants import MessageType, Rotation, ImageFormat, ImageResolution

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
    
    # Encode and decode
    encoded = original.encode()
    decoded = decode_message(encoded)
    
    # Validate header fields
    assert decoded.msg_type == original.msg_type, f"Message type mismatch: {decoded.msg_type} != {original.msg_type}"
    assert decoded.msg_id == original.msg_id, f"Message ID mismatch: {decoded.msg_id} != {original.msg_id}"
    
    # Validate payload fields
    assert decoded.bg_color == original.bg_color, f"BG color mismatch: {decoded.bg_color} != {original.bg_color}"
    assert decoded.font_color == original.font_color, f"Font color mismatch: {decoded.font_color} != {original.font_color}"
    assert decoded.rotation == original.rotation, f"Rotation mismatch: {decoded.rotation} != {original.rotation}"
    assert len(decoded.texts) == len(original.texts), f"Text count mismatch: {len(decoded.texts)} != {len(original.texts)}"
    
    # Validate each text entry
    for i, (orig_text, dec_text) in enumerate(zip(original.texts, decoded.texts)):
        assert orig_text == dec_text, f"Text {i} mismatch: {dec_text} != {orig_text}"
    
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
    
    # Encode and decode
    encoded = original.encode()
    decoded = decode_message(encoded)
    
    # Validate all fields
    assert decoded.msg_type == original.msg_type, f"Message type mismatch"
    assert decoded.msg_id == original.msg_id, f"Message ID mismatch"
    assert decoded.image_id == original.image_id, f"Image ID mismatch: {decoded.image_id} != {original.image_id}"
    assert decoded.image_format == original.image_format, f"Image format mismatch: {decoded.image_format} != {original.image_format}"
    assert decoded.resolution == original.resolution, f"Resolution mismatch: {decoded.resolution} != {original.resolution}"
    assert decoded.delay_time == original.delay_time, f"Delay time mismatch: {decoded.delay_time} != {original.delay_time}"
    assert decoded.total_size == original.total_size, f"Total size mismatch: {decoded.total_size} != {original.total_size}"
    assert decoded.num_chunks == original.num_chunks, f"Num chunks mismatch: {decoded.num_chunks} != {original.num_chunks}"
    assert decoded.rotation == original.rotation, f"Rotation mismatch: {decoded.rotation} != {original.rotation}"
    
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
        (b"Y" * 65535, 16777215)  # Maximum size chunk at maximum location
    ]
    
    for i, (chunk_data, start_loc) in enumerate(test_cases):
        original = ImageChunkMessage(
            image_id=i + 1,
            chunk_id=i + 10,
            start_location=start_loc,
            chunk_data=chunk_data,
            msg_id=200 + i
        )
        
        # Encode and decode
        encoded = original.encode()
        decoded = decode_message(encoded)
        
        # Validate all fields
        assert decoded.msg_type == original.msg_type, f"Case {i}: Message type mismatch"
        assert decoded.msg_id == original.msg_id, f"Case {i}: Message ID mismatch"
        assert decoded.image_id == original.image_id, f"Case {i}: Image ID mismatch: {decoded.image_id} != {original.image_id}"
        assert decoded.chunk_id == original.chunk_id, f"Case {i}: Chunk ID mismatch: {decoded.chunk_id} != {original.chunk_id}"
        assert decoded.start_location == original.start_location, f"Case {i}: Start location mismatch: {decoded.start_location} != {original.start_location}"
        assert decoded.chunk_data == original.chunk_data, f"Case {i}: Chunk data mismatch: length {len(decoded.chunk_data)} != {len(original.chunk_data)}"
    
    print("  ✓ ImageChunkMessage validation successful")
    return True

def test_image_end_message():
    """Test ImageEndMessage encoding/decoding with detailed validation"""
    print("Testing ImageEndMessage...")
    
    original = ImageEndMessage(image_id=255, msg_id=45)
    
    # Encode and decode
    encoded = original.encode()
    decoded = decode_message(encoded)
    
    # Validate all fields
    assert decoded.msg_type == original.msg_type, f"Message type mismatch"
    assert decoded.msg_id == original.msg_id, f"Message ID mismatch"
    assert decoded.image_id == original.image_id, f"Image ID mismatch: {decoded.image_id} != {original.image_id}"
    
    print("  ✓ ImageEndMessage validation successful")
    return True

def test_backlight_messages():
    """Test BacklightOnMessage and BacklightOffMessage encoding/decoding"""
    print("Testing Backlight messages...")
    
    # Test BacklightOnMessage
    original_on = BacklightOnMessage(msg_id=100)
    encoded_on = original_on.encode()
    decoded_on = decode_message(encoded_on)
    
    assert decoded_on.msg_type == original_on.msg_type, f"BacklightOn: Message type mismatch"
    assert decoded_on.msg_id == original_on.msg_id, f"BacklightOn: Message ID mismatch"
    assert len(decoded_on.payload) == 0, f"BacklightOn: Should have no payload"
    
    # Test BacklightOffMessage
    original_off = BacklightOffMessage(msg_id=101)
    encoded_off = original_off.encode()
    decoded_off = decode_message(encoded_off)
    
    assert decoded_off.msg_type == original_off.msg_type, f"BacklightOff: Message type mismatch"
    assert decoded_off.msg_id == original_off.msg_id, f"BacklightOff: Message ID mismatch"
    assert len(decoded_off.payload) == 0, f"BacklightOff: Should have no payload"
    
    print("  ✓ Backlight messages validation successful")
    return True

def test_ping_messages():
    """Test PingRequestMessage and PingResponseMessage encoding/decoding"""
    print("Testing Ping messages...")
    
    # Test PingRequestMessage
    original_req = PingRequestMessage(msg_id=150)
    encoded_req = original_req.encode()
    decoded_req = decode_message(encoded_req)
    
    assert decoded_req.msg_type == original_req.msg_type, f"PingRequest: Message type mismatch"
    assert decoded_req.msg_id == original_req.msg_id, f"PingRequest: Message ID mismatch"
    assert len(decoded_req.payload) == 0, f"PingRequest: Should have no payload"
    
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
        
        encoded_resp = original_resp.encode()
        decoded_resp = decode_message(encoded_resp)
        
        assert decoded_resp.msg_type == original_resp.msg_type, f"PingResponse: Message type mismatch"
        assert decoded_resp.msg_id == original_resp.msg_id, f"PingResponse: Message ID mismatch"
        assert decoded_resp.status_code == original_resp.status_code, f"PingResponse: Status code mismatch: {decoded_resp.status_code} != {original_resp.status_code}"
        assert decoded_resp.status_string == original_resp.status_string, f"PingResponse: Status string mismatch: '{decoded_resp.status_string}' != '{original_resp.status_string}'"
    
    print("  ✓ Ping messages validation successful")
    return True

def test_ack_message():
    """Test AckMessage encoding/decoding with detailed validation"""
    print("Testing AckMessage...")
    
    test_cases = [0, 1, 127, 255]  # Various message IDs to acknowledge
    
    for ack_msg_id in test_cases:
        original = AckMessage(ack_msg_id=ack_msg_id, msg_id=200)
        
        # Encode and decode
        encoded = original.encode()
        decoded = decode_message(encoded)
        
        # Validate all fields
        assert decoded.msg_type == original.msg_type, f"ACK {ack_msg_id}: Message type mismatch"
        assert decoded.msg_id == original.msg_id, f"ACK {ack_msg_id}: Message ID mismatch"
        assert decoded.ack_msg_id == original.ack_msg_id, f"ACK {ack_msg_id}: Ack message ID mismatch: {decoded.ack_msg_id} != {original.ack_msg_id}"
    
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
        
        # Encode and decode
        encoded = original.encode()
        decoded = decode_message(encoded)
        
        # Validate all fields
        assert decoded.msg_type == original.msg_type, f"Error ({error_msg_id}, {error_code}): Message type mismatch"
        assert decoded.msg_id == original.msg_id, f"Error ({error_msg_id}, {error_code}): Message ID mismatch"
        assert decoded.error_msg_id == original.error_msg_id, f"Error ({error_msg_id}, {error_code}): Error message ID mismatch: {decoded.error_msg_id} != {original.error_msg_id}"
        assert decoded.error_code == original.error_code, f"Error ({error_msg_id}, {error_code}): Error code mismatch: {decoded.error_code} != {original.error_code}"
    
    print("  ✓ ErrorMessage validation successful")
    return True

def test_edge_cases():
    """Test edge cases and error conditions"""
    print("Testing edge cases...")
    
    # Test invalid SOF
    try:
        bad_data = bytearray([0x00, 0x01, 0x02, 0x00, 0x00])  # Wrong SOF
        decode_message(bad_data)
        assert False, "Should have failed with invalid SOF"
    except ValueError as e:
        assert "Invalid SOF" in str(e)
    
    # Test insufficient data
    try:
        bad_data = bytearray([0x7E, 0x01])  # Too short
        decode_message(bad_data)
        assert False, "Should have failed with insufficient data"
    except ValueError as e:
        assert "Insufficient data" in str(e)
    
    # Test unknown message type
    try:
        bad_data = bytearray([0x7E, 0xFF, 0x00, 0x00, 0x00])  # Unknown type
        decode_message(bad_data)
        assert False, "Should have failed with unknown message type"
    except ValueError as e:
        assert "Unknown message type" in str(e)
    
    print("  ✓ Edge cases validation successful")
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
    
    encoded = chunk_msg.encode()
    decoded = decode_message(encoded)
    
    # Verify every byte is identical
    assert decoded.chunk_data == chunk_msg.chunk_data, "Binary data corruption detected"
    assert len(decoded.chunk_data) == len(chunk_msg.chunk_data), "Length mismatch in binary data"
    
    for i, (orig, dec) in enumerate(zip(chunk_msg.chunk_data, decoded.chunk_data)):
        assert orig == dec, f"Byte {i} mismatch: {dec} != {orig}"
    
    print("  ✓ Payload integrity validation successful")
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
        test_edge_cases,
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
