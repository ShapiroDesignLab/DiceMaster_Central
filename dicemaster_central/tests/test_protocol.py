#!/usr/bin/env python3
"""
Test script for protocol encoding/decoding validation
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dicemaster_central.media_typing.protocol import *
from dicemaster_central.constants import MessageType, Rotation, ImageFormat, ImageResolution, ErrorCode

def normalize_payload_for_comparison(payload):
    """Remove DMA padding and alignment padding from payload for comparison purposes"""
    if len(payload) < 5:  # Must have at least header
        return payload
    
    # Extract the actual payload length from header bytes 3-4
    payload_len = (payload[3] << 8) | payload[4]
    
    # The actual payload should be from bytes 5 to 5+payload_len
    # Everything after that is padding
    expected_end = 5 + payload_len
    if expected_end <= len(payload):
        return payload[:expected_end]
    
    # If something is wrong, just remove the final 4-byte DMA padding
    if len(payload) >= 4 and payload[-4:] == b'\x00\x00\x00\x00':
        return payload[:-4]
    return payload

def test_text_batch_message():
    """Test TextBatchMessage encoding/decoding with detailed validation"""
    print("Testing TextBatchMessage...")
    
    # Create original message with comprehensive test data
    original = TextBatchMessage(
        screen_id=0,
        bg_color=0x1234,
        texts=[
            (10, 20, 1, 0x5678, "Hello"),
            (30, 40, 2, 0x9ABC, "World!"),
            (100, 200, 3, 0xDEF0, "Unicode: ñáéíóú"),
            (0, 0, 0, 0xFFFF, ""),  # Empty string test
            (65535, 65535, 255, 0x0000, "Max values")  # Test maximum values
        ],
        rotation=Rotation.ROTATION_270
    )
    
    # Test encoding - should return the complete message in payload
    # Note: encode() is already called in constructor, no need to call again  
    assert len(original.payload) > 0, "Encoded message should have payload"
    
    # Decode the message
    decoded = TextBatchMessage.decode(original.payload)
    
    # Test equality using __eq__ method
    assert original == decoded, "Original and decoded messages should be equal using __eq__"
    
    # Validate individual fields for more detailed error reporting if needed
    assert decoded.msg_type == original.msg_type, "Message type mismatch: {} != {}".format(decoded.msg_type, original.msg_type)
    assert decoded.screen_id == original.screen_id, "Screen ID mismatch: {} != {}".format(decoded.screen_id, original.screen_id)
    assert decoded.bg_color == original.bg_color, "BG color mismatch: {} != {}".format(decoded.bg_color, original.bg_color)
    assert decoded.rotation == original.rotation, "Rotation mismatch: {} != {}".format(decoded.rotation, original.rotation)
    assert decoded.texts == original.texts, "Texts mismatch: {} != {}".format(decoded.texts, original.texts)
    
    # Test that different messages are not equal
    different_msg = TextBatchMessage(
        screen_id=0,
        bg_color=0x0000,  # Different color
        texts=[(10, 20, 1, 0x5678, "Hello")],
        rotation=Rotation.ROTATION_270
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
        screen_id=0,
        image_id=255,
        image_format=ImageFormat.JPEG,
        resolution=ImageResolution.SQ480,
        delay_time=255,
        total_size=16777215,  # Maximum 24-bit value
        num_chunks=255,
        chunk_0_data=chunk_0_data,
        rotation=Rotation.ROTATION_180
    )
    
    # Test encoding - should return the complete message in payload
    # Note: encode() is already called in constructor, no need to call again
    assert len(original.payload) > 0, "Encoded message should have payload"
    
    # Decode the message
    decoded = ImageStartMessage.decode(original.payload)

    # Test equality using __eq__ method
    print(f"DEBUG: Original screen_id={original.screen_id}, msg_type={original.msg_type}")
    print(f"DEBUG: Decoded screen_id={decoded.screen_id}, msg_type={decoded.msg_type}")
    print(f"DEBUG: Original payload length={len(original.payload)}, first 20 bytes: {original.payload[:20].hex()}")
    print(f"DEBUG: Decoded payload length={len(decoded.payload)}, first 20 bytes: {decoded.payload[:20].hex()}")
    
    # Normalize payloads for comparison by removing DMA padding
    orig_normalized = normalize_payload_for_comparison(original.payload)
    decoded_normalized = normalize_payload_for_comparison(decoded.payload)
    print(f"DEBUG: Normalized original length={len(orig_normalized)}, decoded length={len(decoded_normalized)}")
    print(f"DEBUG: Payloads equal after normalization: {orig_normalized == decoded_normalized}")
    
    # Test that normalized payloads are equal (this validates round-trip encoding/decoding)
    assert orig_normalized == decoded_normalized, "Normalized payloads should be equal after round-trip"
    
    # Validate individual fields for more detailed error reporting
    assert decoded.msg_type == original.msg_type, "Message type mismatch"
    assert decoded.screen_id == original.screen_id, "Screen ID mismatch"
    assert decoded.image_id == original.image_id, "Image ID mismatch: {} != {}".format(decoded.image_id, original.image_id)
    assert decoded.image_format == original.image_format, "Image format mismatch: {} != {}".format(decoded.image_format, original.image_format)
    assert decoded.resolution == original.resolution, "Resolution mismatch: {} != {}".format(decoded.resolution, original.resolution)
    assert decoded.delay_time == original.delay_time, "Delay time mismatch: {} != {}".format(decoded.delay_time, original.delay_time)
    assert decoded.total_size == original.total_size, "Total size mismatch: {} != {}".format(decoded.total_size, original.total_size)
    assert decoded.num_chunks == original.num_chunks, "Num chunks mismatch: {} != {}".format(decoded.num_chunks, original.num_chunks)
    assert decoded.chunk_0_data == original.chunk_0_data, "Chunk 0 data mismatch: {} != {}".format(decoded.chunk_0_data, original.chunk_0_data)
    assert decoded.rotation == original.rotation, "Rotation mismatch: {} != {}".format(decoded.rotation, original.rotation)
    
    # Test that different messages are not equal
    different_msg = ImageStartMessage(
        screen_id=0,
        image_id=128,  # Different ID
        image_format=ImageFormat.RGB565,
        resolution=ImageResolution.SQ240,
        delay_time=255,
        total_size=16777215,
        num_chunks=255,
        chunk_0_data=b"Different chunk data",
        rotation=Rotation.ROTATION_180
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
        (b"Y" * 8000, 16777215)  # Large chunk at maximum location but within 8KB limit
    ]
    
    for i, (chunk_data, start_loc) in enumerate(test_cases):
        original = ImageChunkMessage(
            screen_id=0,
            image_id=i + 1,
            chunk_id=i + 10,
            start_location=start_loc,
            chunk_data=chunk_data
        )
        
        # Test encoding
        # Note: encode() is already called in constructor, no need to call again
        assert len(original.payload) > 0, "Case {}: Encoded message should have payload".format(i)
        
        # Decode the message
        decoded = ImageChunkMessage.decode(original.payload)
        
        # Test equality using __eq__ method
        assert original == decoded, f"Case {i}: Original and decoded messages should be equal using __eq__"
        
        # Validate individual fields for more detailed error reporting
        assert decoded.msg_type == original.msg_type, "Case {}: Message type mismatch".format(i)
        assert decoded.screen_id == original.screen_id, "Case {}: Screen ID mismatch".format(i)
        assert decoded.image_id == original.image_id, "Case {}: Image ID mismatch: {} != {}".format(i, decoded.image_id, original.image_id)
        assert decoded.chunk_id == original.chunk_id, "Case {}: Chunk ID mismatch: {} != {}".format(i, decoded.chunk_id, original.chunk_id)
        assert decoded.start_location == original.start_location, "Case {}: Start location mismatch: {} != {}".format(i, decoded.start_location, original.start_location)
        assert decoded.chunk_data == original.chunk_data, "Case {}: Chunk data mismatch: length {} != {}".format(i, len(decoded.chunk_data), len(original.chunk_data))
    
    # Test that different messages are not equal
    msg1 = ImageChunkMessage(0, 1, 1, 0, b"data1")
    msg2 = ImageChunkMessage(0, 1, 1, 0, b"data2")  # Different data
    assert msg1 != msg2, "Messages with different chunk data should not be equal"
    
    print("  ✓ ImageChunkMessage validation successful")
    return True

def test_backlight_messages():
    """Test BacklightOnMessage and BacklightOffMessage encoding/decoding"""
    print("Testing Backlight messages...")
    
    # Test BacklightOnMessage
    original_on = BacklightOnMessage(screen_id=0)
    # Note: encode() is already called in constructor, no need to call again
    assert len(original_on.payload) > 0, "BacklightOn: Encoded message should have payload"
    
    # Debug the payload structure
    print(f"DEBUG BacklightOn: payload length={len(original_on.payload)}, content: {original_on.payload.hex()}")
    print(f"DEBUG BacklightOn: header={original_on.payload[:5].hex()}, content_payload={original_on.payload[5:].hex()}")
    
    # Test decode with fixed decode method that handles payload length properly
    decoded_on = BacklightOnMessage.decode(original_on.payload)
    
    # Test equality using __eq__ method
    assert original_on == decoded_on, "BacklightOn: Original and decoded messages should be equal using __eq__"
    
    assert decoded_on.msg_type == original_on.msg_type, "BacklightOn: Message type mismatch"
    assert decoded_on.screen_id == original_on.screen_id, "BacklightOn: Screen ID mismatch"
    
    # Test BacklightOffMessage
    original_off = BacklightOffMessage(screen_id=0)
    # Note: encode() is already called in constructor, no need to call again
    assert len(original_off.payload) > 0, "BacklightOff: Encoded message should have payload"
    
    decoded_off = BacklightOffMessage.decode(original_off.payload)
    
    # Test equality using __eq__ method
    assert original_off == decoded_off, "BacklightOff: Original and decoded messages should be equal using __eq__"
    
    assert decoded_off.msg_type == original_off.msg_type, "BacklightOff: Message type mismatch"
    assert decoded_off.screen_id == original_off.screen_id, "BacklightOff: Screen ID mismatch"
    
    # Test that different message types are not equal
    assert original_on != original_off, "BacklightOn and BacklightOff should not be equal"
    print("  ✓ Backlight messages validation successful")
    return True

def test_payload_integrity():
    """Test that payloads are bit-perfect after round-trip"""
    print("Testing payload integrity...")
    
    # Test with binary data that might have encoding issues
    binary_data = bytes(range(256))  # All possible byte values
    
    chunk_msg = ImageChunkMessage(
        screen_id=0,
        image_id=1,
        chunk_id=1,
        start_location=0,
        chunk_data=binary_data
    )
    
    # Test encoding
    # Note: encode() is already called in constructor, no need to call again
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
        screen_id=0,
        bg_color=0x1234,
        texts=[(10, 20, 1, 0x5678, "Hello")],
        rotation=Rotation.ROTATION_0
    )
    
    msg2 = TextBatchMessage(
        screen_id=0,
        bg_color=0x1234,
        texts=[(10, 20, 1, 0x5678, "Hello")],
        rotation=Rotation.ROTATION_0
    )
    
    assert msg1 == msg2, "Identical messages should be equal"
    
    # Test that messages with different content are not equal
    msg3 = TextBatchMessage(
        screen_id=0,
        bg_color=0x0000,  # Different background color
        texts=[(10, 20, 1, 0x5678, "Hello")],
        rotation=Rotation.ROTATION_0
    )
    
    assert msg1 != msg3, "Messages with different content should not be equal"
    
    # Test that messages with different screen IDs are not equal  
    msg4 = TextBatchMessage(
        screen_id=1,  # Different screen ID
        bg_color=0x1234,
        texts=[(10, 20, 1, 0x5678, "Hello")],
        rotation=Rotation.ROTATION_0
    )
    
    assert msg1 != msg4, "Messages with different screen IDs should not be equal"
    
    # Test equality with different message types
    # Note: Ping and Screen Response messages are not implemented in current protocol
    # Using BacklightOnMessage as a different message type for comparison
    backlight_msg = BacklightOnMessage(screen_id=0)
    assert msg1 != backlight_msg, "Messages of different types should not be equal"
    
    # Test equality with non-ProtocolMessage objects
    assert msg1 != "not a message", "ProtocolMessage should not equal non-ProtocolMessage objects"
    assert msg1 != 42, "ProtocolMessage should not equal numbers"
    assert msg1 is not None, "ProtocolMessage should not equal None"
    
    # Test ImageStartMessage equality
    img1 = ImageStartMessage(0, 1, ImageFormat.JPEG, ImageResolution.SQ240, 100, 1024, 4, b"chunk0data", Rotation.ROTATION_0)
    img2 = ImageStartMessage(0, 1, ImageFormat.JPEG, ImageResolution.SQ240, 100, 1024, 4, b"chunk0data", Rotation.ROTATION_0)
    img3 = ImageStartMessage(0, 2, ImageFormat.JPEG, ImageResolution.SQ240, 100, 1024, 4, b"chunk0data", Rotation.ROTATION_0)  # Different image_id

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
    
    print("\n=== Test Results ===")
    print("Passed: {}/{}".format(success_count, total_count))
    print(f"Success Rate: {success_count/total_count*100:.1f}%")
    
    if success_count == total_count:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed!")
        return 1

if __name__ == "__main__":
    exit(main())
