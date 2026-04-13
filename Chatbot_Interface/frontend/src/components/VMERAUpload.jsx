/**
 * VM-ERA APK Upload Component
 * ============================
 * Cyber-Security themed drag-and-drop upload zone for APK files.
 * Features:
 * - Drag-and-drop with visual feedback
 * - Real-time progress animation
 * - File validation
 */
import React, { useState, useCallback } from 'react';

export default function VMERAUpload({ onUpload, disabled = false }) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);

  const handleUpload = useCallback(async (file) => {
    if (!file) return;

    // Validate file type
    if (!file.name.toLowerCase().endsWith('.apk')) {
      setError('Only APK files are supported');
      return;
    }

    // Validate file size (max 100MB)
    if (file.size > 100 * 1024 * 1024) {
      setError('File size must be under 100MB');
      return;
    }

    setError(null);
    setIsUploading(true);

    try {
      await onUpload(file);
    } catch (err) {
      setError(err.message || 'Upload failed');
    } finally {
      setIsUploading(false);
    }
  }, [onUpload]);

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDragIn = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsDragging(true);
    }
  }, []);

  const handleDragOut = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (disabled || isUploading) return;

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      handleUpload(files[0]);
    }
  }, [disabled, isUploading, handleUpload]);

  const handleFileInput = useCallback((e) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleUpload(files[0]);
    }
  }, [handleUpload]);

  return (
    <div className="vmera-upload">
      <div
        className={`upload-zone ${isDragging ? 'dragging' : ''} ${isUploading ? 'uploading' : ''}`}
        onDragEnter={handleDragIn}
        onDragLeave={handleDragOut}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        {/* Animated border gradient */}
        <div className="upload-zone-border" />

        <div className="upload-content">
          {isUploading ? (
            <>
              <div className="upload-spinner">
                <div className="spinner-ring" />
                <div className="spinner-ring" />
                <div className="spinner-ring" />
              </div>
              <p className="upload-text">Analyzing APK...</p>
            </>
          ) : (
            <>
              <div className="upload-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                  <polyline points="17,8 12,3 7,8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
              </div>
              <p className="upload-title">Drop APK file here</p>
              <p className="upload-subtitle">or click to browse</p>
              <p className="upload-hint">Maximum file size: 100MB</p>
            </>
          )}
        </div>

        <input
          type="file"
          accept=".apk"
          onChange={handleFileInput}
          disabled={disabled || isUploading}
          className="file-input"
          id="apk-file-input"
        />
        <label htmlFor="apk-file-input" className="file-input-label" />
      </div>

      {error && (
        <div className="upload-error">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
