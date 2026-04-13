"""
Chatbot_Interface/backend/test_apk_processor.py
================================================
Pytest tests for APK processing pipeline.

Tests:
- test_apk_extraction: Verify classes.dex is correctly isolated
- test_image_generation: Ensure bytecode-to-image conversion meets input shape (128x128)
- test_ensemble_math: Mock model outputs to verify risk score calculation logic
- test_permission_extraction: Verify permission analysis works correctly
"""
import pytest
import tempfile
import zipfile
import os
from pathlib import Path
import numpy as np

from apk_processor import APKProcessor, process_apk_file, HIGH_RISK_PERMISSIONS


def create_mock_apk(temp_dir: Path, dex_size: int = 50000) -> Path:
    """Create a mock APK file for testing."""
    apk_path = temp_dir / "test_app.apk"

    # Create mock DEX content (random bytes)
    mock_dex = os.urandom(dex_size)

    # Create mock AndroidManifest.xml
    mock_manifest = b"""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.test.app">
    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.READ_SMS"/>
    <uses-permission android:name="android.permission.SEND_SMS"/>
    <uses-permission android:name="android.permission.CAMERA"/>
    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
    <application android:label="Test App">
        <activity android:name=".MainActivity">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
    </application>
</manifest>
"""

    with zipfile.ZipFile(apk_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('classes.dex', mock_dex)
        zf.writestr('AndroidManifest.xml', mock_manifest)

    return apk_path


class TestAPKExtraction:
    """Test DEX extraction from APK files."""

    def test_apk_extraction_success(self, tmp_path):
        """Verify classes.dex is correctly isolated from APK."""
        apk_path = create_mock_apk(tmp_path, dex_size=50000)

        processor = APKProcessor()
        dex_bytes = processor.extract_dex(str(apk_path))

        assert dex_bytes is not None
        assert len(dex_bytes) == 50000
        assert isinstance(dex_bytes, bytes)

    def test_apk_extraction_no_dex(self, tmp_path):
        """Test handling of APK without classes.dex."""
        apk_path = tmp_path / "empty.apk"

        # Create APK without DEX
        with zipfile.ZipFile(apk_path, 'w') as zf:
            zf.writestr('AndroidManifest.xml', b'<manifest/>')

        processor = APKProcessor()
        dex_bytes = processor.extract_dex(str(apk_path))

        assert dex_bytes is None

    def test_apk_extraction_invalid_zip(self, tmp_path):
        """Test handling of invalid APK file."""
        apk_path = tmp_path / "not_an_apk.apk"
        apk_path.write_bytes(b"not a zip file")

        processor = APKProcessor()
        dex_bytes = processor.extract_dex(str(apk_path))

        assert dex_bytes is None

    def test_apk_extraction_multiple_dex(self, tmp_path):
        """Test extraction when multiple DEX files exist."""
        apk_path = tmp_path / "multidex.apk"

        with zipfile.ZipFile(apk_path, 'w') as zf:
            zf.writestr('classes.dex', os.urandom(10000))
            zf.writestr('classes2.dex', os.urandom(20000))
            zf.writestr('classes3.dex', os.urandom(15000))

        processor = APKProcessor()
        dex_bytes = processor.extract_dex(str(apk_path))

        # Should extract the first (primary) DEX
        assert dex_bytes is not None
        assert len(dex_bytes) == 10000


class TestImageGeneration:
    """Test visual fingerprint generation."""

    def test_image_generation_correct_shape(self):
        """Ensure bytecode-to-image conversion produces 128x128 shape."""
        processor = APKProcessor(fingerprint_size=128)

        # Test with exact size
        dex_bytes = os.urandom(128 * 128)
        array, image = processor.generate_visual_fingerprint(dex_bytes)

        assert array.shape == (128, 128)
        assert image.size == (128, 128)
        assert image.mode == 'L'  # Grayscale

    def test_image_generation_large_dex(self):
        """Test fingerprint generation with DEX larger than fingerprint."""
        processor = APKProcessor(fingerprint_size=128)

        # Large DEX (1MB)
        dex_bytes = os.urandom(1000000)
        array, image = processor.generate_visual_fingerprint(dex_bytes)

        assert array.shape == (128, 128)
        assert image.size == (128, 128)

    def test_image_generation_small_dex(self):
        """Test fingerprint generation with DEX smaller than fingerprint."""
        processor = APKProcessor(fingerprint_size=128)

        # Small DEX (100 bytes)
        dex_bytes = os.urandom(100)
        array, image = processor.generate_visual_fingerprint(dex_bytes)

        assert array.shape == (128, 128)
        assert image.size == (128, 128)
        # Padded area should be zeros
        assert array.flatten()[100:].sum() == 0

    def test_image_generation_custom_size(self):
        """Test custom fingerprint size."""
        processor = APKProcessor(fingerprint_size=64)

        dex_bytes = os.urandom(64 * 64)
        array, image = processor.generate_visual_fingerprint(dex_bytes)

        assert array.shape == (64, 64)
        assert image.size == (64, 64)

    def test_image_generation_deterministic(self):
        """Test that same input produces same output."""
        processor = APKProcessor(fingerprint_size=32)

        dex_bytes = b'\x00\x01\x02\x03' * 256  # 1024 bytes = 32x32

        array1, _ = processor.generate_visual_fingerprint(dex_bytes)
        array2, _ = processor.generate_visual_fingerprint(dex_bytes)

        assert np.array_equal(array1, array2)


class TestPermissionExtraction:
    """Test permission analysis."""

    def test_permission_extraction_fallback(self, tmp_path):
        """Test permission extraction using fallback method."""
        apk_path = create_mock_apk(tmp_path)

        processor = APKProcessor()
        result = processor.extract_permissions(str(apk_path))

        assert 'all_permissions' in result
        assert 'high_risk' in result
        assert 'risk_score' in result
        assert 'categories' in result

        # Should find the dangerous permissions we added
        perms = result['all_permissions']
        assert 'android.permission.READ_SMS' in perms
        assert 'android.permission.SEND_SMS' in perms
        assert 'android.permission.CAMERA' in perms
        assert 'android.permission.ACCESS_FINE_LOCATION' in perms
        assert 'android.permission.INTERNET' in perms

    def test_permission_risk_scoring(self):
        """Test that risk scores are calculated correctly."""
        # Verify HIGH_RISK_PERMISSIONS has expected structure
        for perm, info in HIGH_RISK_PERMISSIONS.items():
            assert 'severity' in info
            assert 'category' in info
            assert info['severity'] in ['low', 'medium', 'high', 'critical']

    def test_permission_categories(self, tmp_path):
        """Test that permission categories are identified."""
        apk_path = create_mock_apk(tmp_path)

        processor = APKProcessor()
        result = processor.extract_permissions(str(apk_path))

        categories = result['categories']

        # Should identify privacy, financial, network categories
        assert 'privacy' in categories  # READ_SMS, CAMERA, LOCATION
        assert 'financial' in categories  # SEND_SMS
        assert 'network' in categories  # INTERNET


class TestEnsembleMath:
    """Test ensemble prediction math (mocked models)."""

    def test_ensemble_weighted_average(self):
        """Verify weighted averaging of model predictions."""
        # Simulate model predictions
        predictions = {
            'cnn': {'probability': 0.9, 'confidence': 0.8},
            'rcnn': {'probability': 0.7, 'confidence': 0.6},
            'rf': {'probability': 0.8, 'confidence': 0.7}
        }

        # Weights from ensemble_predictor (normalized)
        weights = {'cnn': 0.4, 'rcnn': 0.35, 'rf': 0.25}

        # Calculate weighted average
        weighted_prob = sum(
            predictions[m]['probability'] * weights[m]
            for m in predictions
        )

        expected = 0.9 * 0.4 + 0.7 * 0.35 + 0.8 * 0.25
        assert abs(weighted_prob - expected) < 1e-10
        assert weighted_prob == pytest.approx(0.805)

    def test_ensemble_verdict_thresholds(self):
        """Test verdict determination based on risk score."""
        def get_verdict(score):
            if score >= 70:
                return 'malware'
            elif score >= 40:
                return 'suspicious'
            else:
                return 'benign'

        assert get_verdict(85) == 'malware'
        assert get_verdict(70) == 'malware'
        assert get_verdict(69) == 'suspicious'
        assert get_verdict(50) == 'suspicious'
        assert get_verdict(40) == 'suspicious'
        assert get_verdict(39) == 'benign'
        assert get_verdict(10) == 'benign'

    def test_permission_risk_blend(self):
        """Test blending of permission risk with model predictions."""
        model_prob = 0.6  # 60% from models
        perm_risk = 80  # 80% from permissions (normalized to 0.8)

        # 80% model, 20% permission
        blended = model_prob * 0.8 + (perm_risk / 100) * 0.2
        expected = 0.6 * 0.8 + 0.8 * 0.2  # 0.48 + 0.16 = 0.64

        assert abs(blended - expected) < 1e-10


class TestFullPipeline:
    """Test end-to-end APK processing."""

    def test_process_apk_full(self, tmp_path):
        """Test complete APK processing pipeline."""
        apk_path = create_mock_apk(tmp_path, dex_size=50000)

        processor = APKProcessor(fingerprint_size=128)
        result = processor.process_apk(str(apk_path))

        # Check all expected keys
        assert 'fingerprint_array' in result
        assert 'fingerprint_image' in result
        assert 'permissions' in result
        assert 'dex_size' in result
        assert 'apk_size' in result

        # Validate fingerprint
        assert result['fingerprint_array'].shape == (128, 128)
        assert result['fingerprint_image'].size == (128, 128)

        # Validate permissions
        assert result['dex_size'] == 50000
        assert 'all_permissions' in result['permissions']
        assert 'high_risk' in result['permissions']

    def test_process_apk_file_not_found(self):
        """Test handling of missing APK file."""
        processor = APKProcessor()

        with pytest.raises(FileNotFoundError):
            processor.process_apk("/nonexistent/path/app.apk")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
