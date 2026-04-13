"""
Chatbot_Interface/backend/verify_gpu.py
========================================
GPU Verification Script for VM-ERA

Verifies that TensorFlow successfully binds to NVIDIA GPU within the virtual environment.
Run this after setting up the virtual environment to confirm GPU acceleration is available.

Usage:
    python verify_gpu.py
"""
from __future__ import annotations
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def check_python_version() -> bool:
    """Check Python version compatibility."""
    version = sys.version_info
    logger.info(f"Python version: {version.major}.{version.minor}.{version.micro}")

    # TensorFlow 2.10.1 supports Python 3.7-3.10
    if version.major == 3 and 7 <= version.minor <= 10:
        logger.info("Python version is compatible with TensorFlow 2.10.1")
        return True
    else:
        logger.warning("Python version may not be compatible with TensorFlow 2.10.1")
        return False


def check_tensorflow() -> bool:
    """Check TensorFlow installation and GPU binding."""
    try:
        import tensorflow as tf
        logger.info(f"TensorFlow version: {tf.__version__}")
        return True
    except ImportError as e:
        logger.error(f"TensorFlow not installed: {e}")
        return False


def check_cuda() -> dict:
    """Check CUDA availability and configuration."""
    results = {
        'cuda_available': False,
        'gpu_devices': [],
        'mixed_precision': False,
        'errors': []
    }

    try:
        import tensorflow as tf

        # List physical GPUs
        gpus = tf.config.list_physical_devices('GPU')
        results['gpu_devices'] = [str(gpu) for gpu in gpus]
        results['cuda_available'] = len(gpus) > 0

        if gpus:
            logger.info(f"CUDA available: {len(gpus)} GPU(s) detected")
            for i, gpu in enumerate(gpus):
                logger.info(f"  GPU {i}: {gpu}")
        else:
            logger.warning("No GPU devices found - TensorFlow will use CPU")
            results['errors'].append("No GPU devices detected")

        # Check logical GPUs (for multi-GPU strategy)
        logical_gpus = tf.config.list_logical_devices('GPU')
        if logical_gpus:
            logger.info(f"Logical GPUs: {len(logical_gpus)}")

        # Try to enable mixed precision
        try:
            from tensorflow.keras import mixed_precision
            policy = mixed_precision.global_policy()
            logger.info(f"Current mixed precision policy: {policy}")

            # Enable mixed_float16 for faster inference
            mixed_precision.set_global_policy('mixed_float16')
            logger.info("Mixed precision enabled (mixed_float16)")
            results['mixed_precision'] = True

        except Exception as e:
            logger.warning(f"Could not enable mixed precision: {e}")
            results['errors'].append(f"Mixed precision error: {e}")

        # Test GPU memory growth
        try:
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
            logger.info("GPU memory growth enabled")
        except Exception as e:
            logger.warning(f"Could not set memory growth: {e}")

    except ImportError as e:
        results['errors'].append(f"TensorFlow import error: {e}")
    except Exception as e:
        results['errors'].append(f"Unexpected error: {e}")

    return results


def check_protobuf() -> bool:
    """Check protobuf version (must be <3.20 for TF 2.10.1 on Windows)."""
    try:
        import google.protobuf
        version = google.protobuf.__version__
        logger.info(f"protobuf version: {version}")

        # Parse version
        major_version = int(version.split('.')[0])
        minor_version = int(version.split('.')[1])

        if major_version < 3 or (major_version == 3 and minor_version < 20):
            logger.info("protobuf version is compatible with TensorFlow 2.10.1")
            return True
        else:
            logger.warning(
                f"protobuf {version} may cause issues with TensorFlow 2.10.1 on Windows. "
                "Consider downgrading: pip install 'protobuf<3.20'"
            )
            return False

    except ImportError:
        logger.warning("protobuf not installed")
        return False


def run_benchmark() -> dict:
    """Run a simple GPU benchmark."""
    results = {
        'success': False,
        'duration_ms': 0,
        'device': 'unknown'
    }

    try:
        import tensorflow as tf
        import time

        # Check device
        devices = tf.config.list_physical_devices('GPU')
        results['device'] = 'GPU' if devices else 'CPU'

        # Create random tensors
        logger.info("Running matrix multiplication benchmark...")
        a = tf.random.normal([1000, 1000])
        b = tf.random.normal([1000, 1000])

        # Warm-up
        _ = tf.matmul(a, b)

        # Timed run
        start = time.time()
        for _ in range(10):
            c = tf.matmul(a, b)
        end = time.time()

        results['duration_ms'] = (end - start) * 1000 / 10
        results['success'] = True

        logger.info(
            f"Benchmark complete on {results['device']}: "
            f"{results['duration_ms']:.2f}ms per matmul (1000x1000)"
        )

    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        results['error'] = str(e)

    return results


def run_full_debug() -> dict:
    """Run full GPU verification."""
    report = {
        'overall_status': 'unknown',
        'checks': []
    }

    # Python version
    py_ok = check_python_version()
    report['checks'].append({
        'name': 'Python version',
        'status': 'ok' if py_ok else 'warning',
        'message': f'{sys.version_info.major}.{sys.version_info.minor}'
    })

    # TensorFlow
    tf_ok = check_tensorflow()
    report['checks'].append({
        'name': 'TensorFlow',
        'status': 'ok' if tf_ok else 'error',
        'message': 'Installed' if tf_ok else 'Not installed'
    })

    if not tf_ok:
        report['overall_status'] = 'error'
        return report

    # CUDA/GPU
    cuda_results = check_cuda()
    gpu_status = 'ok' if cuda_results['cuda_available'] else 'warning'
    report['checks'].append({
        'name': 'CUDA GPU',
        'status': gpu_status,
        'message': f"{len(cuda_results['gpu_devices'])} device(s)" if cuda_results['gpu_devices'] else 'No GPU detected',
        'details': cuda_results
    })

    # protobuf
    pb_ok = check_protobuf()
    report['checks'].append({
        'name': 'protobuf',
        'status': 'ok' if pb_ok else 'warning',
        'message': 'Compatible' if pb_ok else 'May need downgrade'
    })

    # Benchmark
    bench_results = run_benchmark()
    report['checks'].append({
        'name': 'GPU Benchmark',
        'status': 'ok' if bench_results['success'] else 'error',
        'message': f"{bench_results['duration_ms']:.2f}ms ({bench_results['device']})"
    })

    # Overall status
    errors = sum(1 for c in report['checks'] if c['status'] == 'error')
    warnings = sum(1 for c in report['checks'] if c['status'] == 'warning')

    if errors > 0:
        report['overall_status'] = 'error'
    elif warnings > 0:
        report['overall_status'] = 'warning'
    else:
        report['overall_status'] = 'ok'

    return report


def main():
    """Main entry point."""
    print("=" * 60)
    print("VM-ERA GPU Verification")
    print("=" * 60)
    print()

    report = run_full_debug()

    print("\nSummary:")
    print("-" * 40)
    for check in report['checks']:
        status_icon = {
            'ok': '[OK]',
            'warning': '[WARN]',
            'error': '[ERROR]'
        }.get(check['status'], '[?]')

        print(f"  {status_icon} {check['name']}: {check['message']}")

    print()
    print(f"Overall Status: {report['overall_status'].upper()}")
    print("=" * 60)

    # Exit code
    if report['overall_status'] == 'error':
        sys.exit(1)
    elif report['overall_status'] == 'warning':
        sys.exit(0)  # Warning but still usable
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
