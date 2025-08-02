#!/usr/bin/env python3
"""
Test script for protocol encoding/decoding validation
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dicemaster_central.media_typing.protocol import *
from DiceMaster_Central.config.constants import MessageType, Rotation, ImageFormat, ImageResolution, ErrorCode

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
    
    # Test with maximum values and embedded chunk data
    chunk_0_data = b"This is embedded chunk 0 data for testing"
    original = ImageStartMessage(
        image_id=255,
        image_format=ImageFormat.JPEG,
        resolution=ImageResolution.SQ480,
        delay_time=255,
        total_size=16777215,  # Maximum 24-bit value
        num_chunks=255,
        chunk_0_data=chunk_0_data,
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
    assert decoded.chunk_0_data == original.chunk_0_data, f"Chunk 0 data mismatch: {decoded.chunk_0_data} != {original.chunk_0_data}"
    assert decoded.rotation == original.rotation, f"Rotation mismatch: {decoded.rotation} != {original.rotation}"
    
    # Test that different messages are not equal
    different_msg = ImageStartMessage(
        image_id=128,  # Different ID
        image_format=ImageFormat.RGB565,
        resolution=ImageResolution.SQ240,
        delay_time=255,
        total_size=16777215,
        num_chunks=255,
        chunk_0_data=b"Different chunk data",
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
    """Test PingRequestMessage and ScreenResponse encoding/decoding"""
    print("Testing Ping messages...")
    
    # Test PingRequestMessage
    original_req = PingRequestMessage(msg_id=150)
    original_req.encode()
    assert len(original_req.payload) > 0, "PingRequest: Encoded message should have payload"
    
    decoded_req = PingRequestMessage.decode(original_req.payload)
    
    # Test equality using __eq__ method
    assert original_req == decoded_req, "PingRequest: Original and decoded messages should be equal using __eq__"
    
    assert decoded_req.msg_type == original_req.msg_type, "PingRequest: Message type mismatch"
    assert decoded_req.msg_id == original_req.msg_id, "PingRequest: Message ID mismatch"
    
    # Test ScreenResponse with various error codes
    test_responses = [
        (ErrorCode.SUCCESS, 151),
        (ErrorCode.UNKNOWN_MSG_TYPE, 152),
        (ErrorCode.INVALID_FORMAT, 153),
        (ErrorCode.OUT_OF_MEMORY, 154),
        (ErrorCode.INTERNAL_ERROR, 155)
    ]
    
    for error_code, msg_id in test_responses:
        original_resp = ScreenResponse(
            status_code=error_code,
            msg_id=msg_id
        )
        
        original_resp.encode()
        assert len(original_resp.payload) > 0, "ScreenResponse: Encoded message should have payload"
        
        decoded_resp = ScreenResponse.decode(original_resp.payload)
        
        # Test equality using __eq__ method
        assert original_resp == decoded_resp, f"ScreenResponse: Original and decoded messages should be equal using __eq__ for ({error_code.name}, {msg_id})"
        
        assert decoded_resp.msg_id == original_resp.msg_id, "ScreenResponse: Message ID mismatch"
        assert decoded_resp.status_code == original_resp.status_code, f"ScreenResponse: Status code mismatch: {decoded_resp.status_code} != {original_resp.status_code}"
    
    # Test that different screen responses are not equal
    resp1 = ScreenResponse(ErrorCode.SUCCESS, msg_id=151)
    resp2 = ScreenResponse(ErrorCode.UNKNOWN_MSG_TYPE, msg_id=151)  # Different status code
    assert resp1 != resp2, "Screen responses with different status codes should not be equal"
    
    print("  ✓ Ping messages validation successful")
    return True

def test_screen_response_as_ack():
    """Test ScreenResponse as acknowledgment message"""
    print("Testing ScreenResponse as ACK...")
    
    test_cases = [0, 1, 127, 255]  # Various message IDs to acknowledge
    
    for msg_id in test_cases:
        # Create ACK response using ScreenResponse with SUCCESS status
        original = ScreenResponse(status_code=ErrorCode.SUCCESS, msg_id=msg_id)
        
        # Test encoding
        original.encode()
        assert len(original.payload) > 0, f"ACK {msg_id}: Encoded message should have payload"
        
        # Decode the message
        decoded = ScreenResponse.decode(original.payload)
        
        # Test equality using __eq__ method
        assert original == decoded, f"ACK {msg_id}: Original and decoded messages should be equal using __eq__"
        
        # Validate individual fields for more detailed error reporting
        assert decoded.msg_id == original.msg_id, f"ACK {msg_id}: Message ID mismatch: {decoded.msg_id} != {original.msg_id}"
        assert decoded.status_code == ErrorCode.SUCCESS, f"ACK {msg_id}: Status code should be SUCCESS for ACK"
    
    # Test that different ACK messages are not equal
    ack1 = ScreenResponse(status_code=ErrorCode.SUCCESS, msg_id=1)
    ack2 = ScreenResponse(status_code=ErrorCode.SUCCESS, msg_id=2)  # Different msg_id
    assert ack1 != ack2, "ACK messages with different msg_id should not be equal"
    
    print("  ✓ ScreenResponse as ACK validation successful")
    return True

def test_screen_response_as_error():
    """Test ScreenResponse as error message"""
    print("Testing ScreenResponse as Error...")
    
    test_cases = [
        (ErrorCode.UNKNOWN_MSG_TYPE, 42),
        (ErrorCode.INVALID_FORMAT, 100),
        (ErrorCode.OUT_OF_MEMORY, 255),
        (ErrorCode.INTERNAL_ERROR, 128)
    ]
    
    for error_code, msg_id in test_cases:
        original = ScreenResponse(status_code=error_code, msg_id=msg_id)
        
        # Test encoding
        original.encode()
        assert len(original.payload) > 0, f"Error ({error_code.name}, {msg_id}): Encoded message should have payload"
        
        # Decode the message
        decoded = ScreenResponse.decode(original.payload)
        
        # Test equality using __eq__ method
        assert original == decoded, f"Error ({error_code.name}, {msg_id}): Original and decoded messages should be equal using __eq__"
        
        # Validate individual fields for more detailed error reporting
        assert decoded.msg_id == original.msg_id, f"Error ({error_code.name}, {msg_id}): Message ID mismatch: {decoded.msg_id} != {original.msg_id}"
        assert decoded.status_code == original.status_code, f"Error ({error_code.name}, {msg_id}): Error code mismatch: {decoded.status_code} != {original.status_code}"
    
    # Test that different error messages are not equal
    err1 = ScreenResponse(status_code=ErrorCode.UNKNOWN_MSG_TYPE, msg_id=250)
    err2 = ScreenResponse(status_code=ErrorCode.INVALID_FORMAT, msg_id=250)  # Different error code
    assert err1 != err2, "Error messages with different error codes should not be equal"
    
    print("  ✓ ScreenResponse as Error validation successful")
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
    img1 = ImageStartMessage(1, ImageFormat.JPEG, ImageResolution.SQ240, 100, 1024, 4, b"chunk0data", Rotation.ROTATION_0, 1)
    img2 = ImageStartMessage(1, ImageFormat.JPEG, ImageResolution.SQ240, 100, 1024, 4, b"chunk0data", Rotation.ROTATION_0, 1)
    img3 = ImageStartMessage(2, ImageFormat.JPEG, ImageResolution.SQ240, 100, 1024, 4, b"chunk0data", Rotation.ROTATION_0, 1)  # Different image_id

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
        # test_image_end_message,  # Removed - images are auto-invalidated after timeout
        test_backlight_messages,
        test_ping_messages,
        test_screen_response_as_ack,
        test_screen_response_as_error,
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
