/**
 * VM-ERA APK Upload Hook
 * =======================
 * Handles APK file upload and analysis.
 */
import { useState, useCallback } from 'react';

const API_BASE = 'http://localhost:5001/api';

export function useAPKUpload(getToken) {
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const uploadAPK = useCallback(async (file) => {
    if (!file) throw new Error('No file provided');

    setUploading(true);
    setError(null);
    setResult(null);

    try {
      const token = getToken();
      if (!token) {
        throw new Error('Authentication required');
      }

      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(`${API_BASE}/apk/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Upload failed');
      }

      if (!data.ok) {
        throw new Error(data.error || 'Analysis failed');
      }

      setResult(data);
      return data;

    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setUploading(false);
    }
  }, [getToken]);

  const clearResult = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  return {
    uploadAPK,
    uploading,
    result,
    error,
    clearResult
  };
}

export default useAPKUpload;
