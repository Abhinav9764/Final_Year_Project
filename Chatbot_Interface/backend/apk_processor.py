"""
Chatbot_Interface/backend/apk_processor.py
==========================================
APK Processing Pipeline for VM-ERA

- Extract classes.dex from APK files
- Generate visual fingerprint (128x128 grayscale image) from DEX bytecode
- Extract permissions and security flags using androguard
"""
from __future__ import annotations
import logging
import zipfile
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# High-risk Android permissions (security flags)
HIGH_RISK_PERMISSIONS = {
    # Dangerous permissions (Android 10+)
    "android.permission.READ_CONTACTS": {"severity": "high", "category": "privacy"},
    "android.permission.WRITE_CONTACTS": {"severity": "high", "category": "privacy"},
    "android.permission.READ_CALL_LOG": {"severity": "critical", "category": "privacy"},
    "android.permission.WRITE_CALL_LOG": {"severity": "critical", "category": "privacy"},
    "android.permission.READ_SMS": {"severity": "critical", "category": "privacy"},
    "android.permission.WRITE_SMS": {"severity": "critical", "category": "privacy"},
    "android.permission.RECEIVE_SMS": {"severity": "high", "category": "privacy"},
    "android.permission.SEND_SMS": {"severity": "critical", "category": "financial"},
    "android.permission.READ_EXTERNAL_STORAGE": {"severity": "medium", "category": "storage"},
    "android.permission.WRITE_EXTERNAL_STORAGE": {"severity": "medium", "category": "storage"},
    "android.permission.CAMERA": {"severity": "high", "category": "privacy"},
    "android.permission.RECORD_AUDIO": {"severity": "high", "category": "privacy"},
    "android.permission.ACCESS_FINE_LOCATION": {"severity": "high", "category": "privacy"},
    "android.permission.ACCESS_COARSE_LOCATION": {"severity": "medium", "category": "privacy"},
    "android.permission.READ_PHONE_STATE": {"severity": "high", "category": "device"},
    "android.permission.CALL_PHONE": {"severity": "high", "category": "financial"},
    "android.permission.PROCESS_OUTGOING_CALLS": {"severity": "high", "category": "privacy"},
    "android.permission.ANSWER_PHONE_CALLS": {"severity": "medium", "category": "device"},
    "android.permission.READ_CALENDAR": {"severity": "medium", "category": "privacy"},
    "android.permission.WRITE_CALENDAR": {"severity": "medium", "category": "privacy"},
    "android.permission.GET_ACCOUNTS": {"severity": "medium", "category": "privacy"},
    "android.permission.BODY_SENSORS": {"severity": "high", "category": "privacy"},

    # System-level permissions
    "android.permission.SYSTEM_ALERT_WINDOW": {"severity": "critical", "category": "system"},
    "android.permission.BIND_ACCESSIBILITY_SERVICE": {"severity": "critical", "category": "system"},
    "android.permission.BIND_DEVICE_ADMIN": {"severity": "critical", "category": "system"},
    "android.permission.DEVICE_POWER": {"severity": "critical", "category": "system"},
    "android.permission.FACTORY_TEST": {"severity": "critical", "category": "system"},
    "android.permission.MASTER_CLEAR": {"severity": "critical", "category": "system"},
    "android.permission.REBOOT": {"severity": "critical", "category": "system"},
    "android.permission.SHUTDOWN": {"severity": "high", "category": "system"},

    # Network/Communication
    "android.permission.INTERNET": {"severity": "low", "category": "network"},
    "android.permission.ACCESS_NETWORK_STATE": {"severity": "low", "category": "network"},
    "android.permission.ACCESS_WIFI_STATE": {"severity": "low", "category": "network"},
    "android.permission.CHANGE_WIFI_STATE": {"severity": "medium", "category": "network"},
    "android.permission.BLUETOOTH": {"severity": "low", "category": "network"},
    "android.permission.BLUETOOTH_ADMIN": {"severity": "medium", "category": "network"},
    "android.permission.BLUETOOTH_CONNECT": {"severity": "medium", "category": "network"},
    "android.permission.BLUETOOTH_SCAN": {"severity": "medium", "category": "network"},

    # App operations
    "android.permission.INSTALL_PACKAGES": {"severity": "critical", "category": "system"},
    "android.permission.DELETE_PACKAGES": {"severity": "critical", "category": "system"},
    "android.permission.CLEAR_APP_CACHE": {"severity": "high", "category": "system"},
    "android.permission.GET_TASKS": {"severity": "medium", "category": "privacy"},
    "android.permission.REORDER_TASKS": {"severity": "medium", "category": "system"},
    "android.permission.RUNNING_PROCESS_INFO": {"severity": "medium", "category": "privacy"},

    # Broadcast receivers
    "android.permission.RECEIVE_BOOT_COMPLETED": {"severity": "medium", "category": "persistence"},
    "android.permission.RECEIVE_WAP_PUSH": {"severity": "medium", "category": "network"},
    "android.permission.RECEIVE_MMS": {"severity": "high", "category": "privacy"},
}


class APKProcessor:
    """
    Process APK files for malware analysis.

    Features:
    - Extract classes.dex from APK
    - Generate visual fingerprint from DEX bytecode
    - Extract permissions and security flags
    """

    def __init__(self, fingerprint_size: int = 128):
        """
        Initialize APK processor.

        Args:
            fingerprint_size: Size of the visual fingerprint (default 128x128)
        """
        self.fingerprint_size = fingerprint_size
        self._androguard_available = False

        # Try to import androguard
        try:
            from androguard.core.bytecodes.apk import APK
            self._androguard_available = True
            logger.info("Androguard available for APK analysis")
        except ImportError:
            logger.warning("Androguard not available - using fallback parsing")

    def extract_dex(self, apk_path: str) -> Optional[bytes]:
        """
        Extract classes.dex from APK file.

        Args:
            apk_path: Path to the APK file

        Returns:
            Raw bytes of classes.dex or None if extraction fails
        """
        try:
            with zipfile.ZipFile(apk_path, 'r') as apk_zip:
                # Look for classes.dex files (may be classes2.dex, classes3.dex, etc.)
                dex_files = [f for f in apk_zip.namelist() if f.startswith('classes') and f.endswith('.dex')]

                if not dex_files:
                    logger.error("No classes.dex found in APK: %s", apk_path)
                    return None

                # Read the primary classes.dex
                logger.info("Found DEX files: %s", dex_files)
                return apk_zip.read(dex_files[0])

        except zipfile.BadZipFile as e:
            logger.error("Invalid APK file (not a valid zip): %s", e)
            return None
        except Exception as e:
            logger.error("Failed to extract DEX from APK %s: %s", apk_path, e)
            return None

    def generate_visual_fingerprint(self, dex_bytes: bytes) -> Tuple[np.ndarray, Image.Image]:
        """
        Convert DEX bytecode into a visual fingerprint (grayscale image).

        This uses the standard academic approach for malware visualization:
        - Read the first N bytes of the DEX file
        - Map each byte to a pixel value (0-255)
        - Reshape into a square grayscale image

        Args:
            dex_bytes: Raw bytes from classes.dex

        Returns:
            Tuple of (numpy array, PIL Image) representing the fingerprint
        """
        total_pixels = self.fingerprint_size * self.fingerprint_size

        # Take the first N bytes (pad if necessary)
        if len(dex_bytes) < total_pixels:
            # Pad with zeros if DEX is smaller than fingerprint
            padded = np.zeros(total_pixels, dtype=np.uint8)
            padded[:len(dex_bytes)] = np.frombuffer(dex_bytes, dtype=np.uint8)
        else:
            # Take first N bytes
            padded = np.frombuffer(dex_bytes[:total_pixels], dtype=np.uint8)

        # Reshape into square image
        image_array = padded.reshape((self.fingerprint_size, self.fingerprint_size))

        # Convert to PIL Image
        image = Image.fromarray(image_array, mode='L')  # 'L' = grayscale

        logger.info(
            "Generated visual fingerprint: %dx%d from %d DEX bytes",
            self.fingerprint_size, self.fingerprint_size, len(dex_bytes)
        )

        return image_array, image

    def extract_permissions(self, apk_path: str) -> Dict[str, Any]:
        """
        Extract permissions from APK using androguard or fallback parsing.

        Args:
            apk_path: Path to the APK file

        Returns:
            Dictionary containing:
            - all_permissions: List of all permission names
            - high_risk: List of high-risk permissions with details
            - risk_score: Calculated risk score (0-100)
            - categories: Permission categories found
        """
        result = {
            "all_permissions": [],
            "high_risk": [],
            "risk_score": 0,
            "categories": set(),
            "analysis_method": "unknown"
        }

        if self._androguard_available:
            try:
                result = self._extract_permissions_androguard(apk_path)
                result["analysis_method"] = "androguard"
                return result
            except Exception as e:
                logger.warning("Androguard analysis failed: %s, using fallback", e)

        # Fallback: basic permission extraction from AndroidManifest.xml
        try:
            result = self._extract_permissions_fallback(apk_path)
            result["analysis_method"] = "fallback"
        except Exception as e:
            logger.error("Permission extraction failed: %s", e)
            result["analysis_method"] = "failed"

        return result

    def _extract_permissions_androguard(self, apk_path: str) -> Dict[str, Any]:
        """Extract permissions using androguard."""
        from androguard.core.bytecodes.apk import APK

        apk = APK(apk_path)
        permissions = apk.get_permissions()

        all_perms = list(permissions)
        high_risk = []
        categories = set()
        risk_score = 0

        for perm in all_perms:
            if perm in HIGH_RISK_PERMISSIONS:
                perm_info = HIGH_RISK_PERMISSIONS[perm]
                high_risk.append({
                    "permission": perm,
                    "severity": perm_info["severity"],
                    "category": perm_info["category"]
                })
                categories.add(perm_info["category"])

                # Calculate risk score contribution
                severity_scores = {
                    "low": 5,
                    "medium": 15,
                    "high": 30,
                    "critical": 50
                }
                risk_score += severity_scores.get(perm_info["severity"], 10)

        # Cap risk score at 100
        risk_score = min(100, risk_score)

        return {
            "all_permissions": all_perms,
            "high_risk": high_risk,
            "risk_score": risk_score,
            "categories": list(categories)
        }

    def _extract_permissions_fallback(self, apk_path: str) -> Dict[str, Any]:
        """Fallback permission extraction using regex on AndroidManifest.xml."""
        import re

        with zipfile.ZipFile(apk_path, 'r') as apk_zip:
            manifest_content = None

            # Try to find AndroidManifest.xml
            for name in apk_zip.namelist():
                if 'AndroidManifest.xml' in name:
                    try:
                        manifest_content = apk_zip.read(name).decode('utf-8', errors='ignore')
                        break
                    except Exception:
                        continue

            if manifest_content is None:
                logger.warning("Could not extract AndroidManifest.xml")
                return {
                    "all_permissions": [],
                    "high_risk": [],
                    "risk_score": 0,
                    "categories": []
                }

            # Extract permission names using regex
            perm_pattern = r'android\.permission\.[A-Z_]+'
            all_perms = list(set(re.findall(perm_pattern, manifest_content)))

            high_risk = []
            categories = set()
            risk_score = 0

            for perm in all_perms:
                if perm in HIGH_RISK_PERMISSIONS:
                    perm_info = HIGH_RISK_PERMISSIONS[perm]
                    high_risk.append({
                        "permission": perm,
                        "severity": perm_info["severity"],
                        "category": perm_info["category"]
                    })
                    categories.add(perm_info["category"])

                    severity_scores = {
                        "low": 5,
                        "medium": 15,
                        "high": 30,
                        "critical": 50
                    }
                    risk_score += severity_scores.get(perm_info["severity"], 10)

            risk_score = min(100, risk_score)

            return {
                "all_permissions": all_perms,
                "high_risk": high_risk,
                "risk_score": risk_score,
                "categories": list(categories)
            }

    def process_apk(self, apk_path: str | Path) -> Dict[str, Any]:
        """
        Full APK processing pipeline.

        Args:
            apk_path: Path to the APK file

        Returns:
            Dictionary containing:
            - fingerprint_array: numpy array of the visual fingerprint
            - fingerprint_image: PIL Image of the fingerprint
            - permissions: Permission analysis results
            - dex_size: Size of extracted DEX in bytes
        """
        apk_path = Path(apk_path)

        if not apk_path.exists():
            raise FileNotFoundError(f"APK file not found: {apk_path}")

        # Extract DEX
        dex_bytes = self.extract_dex(str(apk_path))
        if dex_bytes is None:
            raise ValueError("Failed to extract classes.dex from APK")

        # Generate visual fingerprint
        fingerprint_array, fingerprint_image = self.generate_visual_fingerprint(dex_bytes)

        # Extract permissions
        permissions = self.extract_permissions(str(apk_path))

        return {
            "fingerprint_array": fingerprint_array,
            "fingerprint_image": fingerprint_image,
            "permissions": permissions,
            "dex_size": len(dex_bytes),
            "apk_size": apk_path.stat().st_size
        }


# Convenience function for quick processing
def process_apk_file(apk_path: str | Path, fingerprint_size: int = 128) -> Dict[str, Any]:
    """
    Process an APK file and return analysis results.

    Args:
        apk_path: Path to the APK file
        fingerprint_size: Size of visual fingerprint (default 128x128)

    Returns:
        Dictionary with fingerprint, permissions, and metadata
    """
    processor = APKProcessor(fingerprint_size=fingerprint_size)
    return processor.process_apk(apk_path)
