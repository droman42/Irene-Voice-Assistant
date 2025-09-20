"""
Test logging rotation functionality
"""

import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import pytest

from irene.utils.logging import setup_logging, _rotate_log_file
from irene.config.models import LogLevel


class TestLogRotation:
    """Test log file rotation functionality"""
    
    def test_rotate_log_file_creates_timestamped_backup(self):
        """Test that existing log file is moved with timestamp"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            log_file = temp_path / "test.log"
            
            # Create a test log file with some content
            log_file.write_text("Previous log content\n")
            assert log_file.exists()
            
            # Call rotation function
            _rotate_log_file(log_file)
            
            # Original file should no longer exist
            assert not log_file.exists()
            
            # Find the rotated file
            rotated_files = list(temp_path.glob("test_*.log"))
            assert len(rotated_files) == 1
            
            rotated_file = rotated_files[0]
            # Check that the name follows the expected pattern
            assert rotated_file.name.startswith("test_")
            assert rotated_file.name.endswith(".log")
            
            # Check content is preserved
            assert rotated_file.read_text() == "Previous log content\n"
    
    def test_rotate_log_file_no_file_exists(self):
        """Test that rotation does nothing when no file exists"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            log_file = temp_path / "nonexistent.log"
            
            assert not log_file.exists()
            
            # Should not raise an error
            _rotate_log_file(log_file)
            
            # Still should not exist
            assert not log_file.exists()
            
            # No rotated files should be created
            rotated_files = list(temp_path.glob("nonexistent_*.log"))
            assert len(rotated_files) == 0
    
    def test_setup_logging_rotates_existing_file(self):
        """Test that setup_logging rotates existing log file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            log_file = temp_path / "irene.log"
            
            # Create existing log file
            log_file.write_text("Old log entry\n")
            assert log_file.exists()
            
            # Setup logging which should rotate the file
            setup_logging(
                level=LogLevel.INFO,
                log_file=log_file,
                enable_console=False
            )
            
            # Original file should exist (new file created)
            assert log_file.exists()
            
            # But it should be empty/new (not contain old content)
            current_content = log_file.read_text()
            assert "Old log entry" not in current_content
            
            # There should be a rotated file with the old content
            rotated_files = list(temp_path.glob("irene_*.log"))
            assert len(rotated_files) == 1
            
            rotated_file = rotated_files[0]
            assert rotated_file.read_text() == "Old log entry\n"
    
    def test_timestamp_format_in_rotated_filename(self):
        """Test that rotated filename has correct timestamp format"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            log_file = temp_path / "test.log"
            
            # Create a test log file
            log_file.write_text("test content")
            
            # Get current time before rotation
            before_rotation = datetime.now()
            
            # Rotate the file
            _rotate_log_file(log_file)
            
            # Get current time after rotation
            after_rotation = datetime.now()
            
            # Find rotated file
            rotated_files = list(temp_path.glob("test_*.log"))
            assert len(rotated_files) == 1
            
            rotated_file = rotated_files[0]
            filename = rotated_file.name
            
            # Extract timestamp from filename: test_YYYYMMDD_HHMMSS.log
            timestamp_part = filename[5:-4]  # Remove "test_" and ".log"
            
            # Verify timestamp format
            assert len(timestamp_part) == 15  # YYYYMMDD_HHMMSS
            assert timestamp_part[8] == "_"  # Underscore separator
            
            # Parse the timestamp
            try:
                parsed_time = datetime.strptime(timestamp_part, "%Y%m%d_%H%M%S")
                # Timestamp should be between before and after rotation times (with some tolerance)
                # Remove microseconds from comparison since our timestamp format doesn't include them
                before_no_micro = before_rotation.replace(microsecond=0)
                after_no_micro = after_rotation.replace(microsecond=0)
                assert before_no_micro <= parsed_time <= after_no_micro or parsed_time == before_no_micro
            except ValueError:
                pytest.fail(f"Invalid timestamp format in filename: {timestamp_part}")


if __name__ == "__main__":
    pytest.main([__file__])
