/* ============================================ */
/* BANTU HALII - MEDIA UPLOAD HANDLER */
/* static/js/upload.js */
/* ============================================ */

// Upload state
const uploadState = {
    maxImageSize: 10 * 1024 * 1024,  // 10MB
    maxVideoSize: 100 * 1024 * 1024, // 100MB
    maxAudioSize: 20 * 1024 * 1024,  // 20MB
    maxDocumentSize: 50 * 1024 * 1024, // 50MB
    allowedImageTypes: ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp', 'image/svg+xml'],
    allowedVideoTypes: ['video/mp4', 'video/webm', 'video/avi', 'video/mov', 'video/quicktime'],
    allowedAudioTypes: ['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/webm', 'audio/aac', 'audio/mp4'],
    allowedDocumentTypes: [
        'application/pdf', 
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-powerpoint',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'text/plain',
        'text/csv',
        'application/rtf'
    ],
    uploadQueue: [],
    isUploading: false
};

// Handle file select from input
function handleFileSelect(event) {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    
    for (const file of files) {
        if (validateFile(file)) {
            addFileToUploadQueue(file);
        }
    }
    
    // Reset input
    event.target.value = '';
    
    // Start upload if not already uploading
    if (!uploadState.isUploading) {
        processUploadQueue();
    }
}

// Validate file before upload
function validateFile(file) {
    // Check file type
    const fileType = getFileCategory(file);
    
    if (fileType === 'unknown') {
        showToast(`File type not supported: ${file.name}`, 'error');
        return false;
    }
    
    // Check file size
    const sizeLimits = {
        'image': uploadState.maxImageSize,
        'video': uploadState.maxVideoSize,
        'audio': uploadState.maxAudioSize,
        'document': uploadState.maxDocumentSize
    };
    
    const maxSize = sizeLimits[fileType] || uploadState.maxImageSize;
    
    if (file.size > maxSize) {
        showToast(`File too large: ${file.name}. Maximum size is ${formatFileSize(maxSize)}`, 'error');
        return false;
    }
    
    // Check specific type restrictions
    if (fileType === 'image' && !uploadState.allowedImageTypes.includes(file.type)) {
        showToast(`Image type not supported: ${file.type}`, 'error');
        return false;
    }
    
    if (fileType === 'video' && !uploadState.allowedVideoTypes.includes(file.type)) {
        showToast(`Video type not supported: ${file.type}`, 'error');
        return false;
    }
    
    if (fileType === 'audio' && !uploadState.allowedAudioTypes.includes(file.type)) {
        showToast(`Audio type not supported: ${file.type}`, 'error');
        return false;
    }
    
    return true;
}

// Get file category
function getFileCategory(file) {
    if (file.type.startsWith('image/')) return 'image';
    if (file.type.startsWith('video/')) return 'video';
    if (file.type.startsWith('audio/')) return 'audio';
    if (uploadState.allowedDocumentTypes.includes(file.type)) return 'document';
    
    // Check by extension
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'].includes(ext)) return 'image';
    if (['mp4', 'webm', 'avi', 'mov', 'mkv'].includes(ext)) return 'video';
    if (['mp3', 'wav', 'ogg', 'aac', 'm4a'].includes(ext)) return 'audio';
    if (['pdf', 'doc', 'docx', 'txt', 'xls', 'xlsx', 'ppt', 'pptx', 'csv'].includes(ext)) return 'document';
    
    return 'unknown';
}

// Add file to upload queue with preview
function addFileToUploadQueue(file) {
    uploadState.uploadQueue.push({
        file: file,
        status: 'pending',
        progress: 0,
        preview: null
    });
    
    // Show preview
    showUploadPreview(file);
}

// Show upload preview
function showUploadPreview(file) {
    const container = document.createElement('div');
    container.className = 'upload-preview-item';
    container.id = `upload-${file.name.replace(/[^a-zA-Z0-9]/g, '_')}`;
    
    const fileType = getFileCategory(file);
    const progressId = `progress-${Date.now()}`;
    
    if (fileType === 'image') {
        const reader = new FileReader();
        reader.onload = function(e) {
            container.innerHTML = `
                <div class="preview-thumbnail">
                    <img src="${e.target.result}" alt="${file.name}">
                </div>
                <div class="preview-info">
                    <span class="preview-name">${file.name}</span>
                    <span class="preview-size">${formatFileSize(file.size)}</span>
                    <div class="progress-bar" id="${progressId}">
                        <div class="progress-fill" style="width: 0%"></div>
                    </div>
                </div>
                <button class="preview-remove" onclick="cancelUpload('${file.name}')">×</button>
            `;
        };
        reader.readAsDataURL(file);
    } else {
        const icons = {
            'video': 'fa-video',
            'audio': 'fa-music',
            'document': 'fa-file'
        };
        
        container.innerHTML = `
            <div class="preview-thumbnail file-icon">
                <i class="fas ${icons[fileType] || 'fa-file'}"></i>
            </div>
            <div class="preview-info">
                <span class="preview-name">${file.name}</span>
                <span class="preview-size">${formatFileSize(file.size)}</span>
                <div class="progress-bar" id="${progressId}">
                    <div class="progress-fill" style="width: 0%"></div>
                </div>
            </div>
            <button class="preview-remove" onclick="cancelUpload('${file.name}')">×</button>
        `;
    }
    
    // Add to preview area
    const previewArea = document.getElementById('upload-previews');
    if (previewArea) {
        previewArea.appendChild(container);
        previewArea.style.display = 'flex';
    }
}

// Process upload queue
async function processUploadQueue() {
    if (uploadState.isUploading || uploadState.uploadQueue.length === 0) return;
    
    uploadState.isUploading = true;
    
    while (uploadState.uploadQueue.length > 0) {
        const item = uploadState.uploadQueue[0];
        item.status = 'uploading';
        
        try {
            const result = await uploadFile(item.file, (progress) => {
                item.progress = progress;
                updateProgress(item.file.name, progress);
            });
            
            if (result.success) {
                item.status = 'completed';
                item.result = result;
                
                // Send message with media
                if (chatState.currentRoomId) {
                    sendMediaMessage(result);
                }
                
                // Remove from queue
                uploadState.uploadQueue.shift();
                removePreview(item.file.name);
            } else {
                throw new Error(result.error || 'Upload failed');
            }
        } catch (error) {
            item.status = 'failed';
            item.error = error.message;
            showToast(`Failed to upload ${item.file.name}: ${error.message}`, 'error');
            updateProgressError(item.file.name);
            
            // Remove failed item after delay
            setTimeout(() => {
                uploadState.uploadQueue.shift();
                removePreview(item.file.name);
            }, 3000);
            break;
        }
    }
    
    uploadState.isUploading = false;
}

// Upload single file
function uploadFile(file, onProgress) {
    return new Promise((resolve, reject) => {
        const formData = new FormData();
        formData.append('file', file);
        
        const xhr = new XMLHttpRequest();
        
        xhr.upload.addEventListener('progress', function(e) {
            if (e.lengthComputable) {
                const progress = Math.round((e.loaded / e.total) * 100);
                onProgress(progress);
            }
        });
        
        xhr.addEventListener('load', function() {
            if (xhr.status === 200 || xhr.status === 201) {
                try {
                    const response = JSON.parse(xhr.responseText);
                    resolve(response);
                } catch (e) {
                    reject(new Error('Invalid server response'));
                }
            } else if (xhr.status === 413) {
                reject(new Error('File too large'));
            } else {
                try {
                    const response = JSON.parse(xhr.responseText);
                    reject(new Error(response.error || 'Upload failed'));
                } catch (e) {
                    reject(new Error(`Upload failed with status ${xhr.status}`));
                }
            }
        });
        
        xhr.addEventListener('error', function() {
            reject(new Error('Network error during upload'));
        });
        
        xhr.addEventListener('abort', function() {
            reject(new Error('Upload cancelled'));
        });
        
        xhr.open('POST', '/upload/media', true);
        xhr.send(formData);
        
        // Store XHR for cancellation
        file._xhr = xhr;
    });
}

// Send message with uploaded media
function sendMediaMessage(uploadResult) {
    if (!socket || !chatState.currentRoomId) return;
    
    const messageData = {
        room_id: chatState.currentRoomId,
        content: document.getElementById('message-input')?.innerText.trim() || '',
        message_type: uploadResult.media_type || 'image',
        media_url: uploadResult.url,
        media_type: uploadResult.media_type,
        media_public_id: uploadResult.public_id,
        thumbnail_url: uploadResult.thumbnail_url || null,
        media_size: uploadResult.file_size,
        media_duration: uploadResult.duration || null,
        media_width: uploadResult.width || null,
        media_height: uploadResult.height || null
    };
    
    if (chatState.replyingTo) {
        messageData.reply_to_id = chatState.replyingTo;
    }
    
    socket.emit('send_message', messageData);
    
    // Clear input
    const input = document.getElementById('message-input');
    if (input) input.innerHTML = '';
    
    cancelReply();
}

// Upload multiple files at once
function uploadFiles(files, content, roomId, replyToId) {
    files.forEach(file => {
        addFileToUploadQueue(file);
    });
    
    if (!uploadState.isUploading) {
        processUploadQueue();
    }
}

// Update progress bar
function updateProgress(fileName, progress) {
    const safeId = fileName.replace(/[^a-zA-Z0-9]/g, '_');
    const previewItem = document.getElementById(`upload-${safeId}`);
    if (previewItem) {
        const progressFill = previewItem.querySelector('.progress-fill');
        if (progressFill) {
            progressFill.style.width = progress + '%';
        }
    }
}

// Update progress error state
function updateProgressError(fileName) {
    const safeId = fileName.replace(/[^a-zA-Z0-9]/g, '_');
    const previewItem = document.getElementById(`upload-${safeId}`);
    if (previewItem) {
        const progressBar = previewItem.querySelector('.progress-bar');
        if (progressBar) {
            progressBar.classList.add('error');
        }
        const progressFill = previewItem.querySelector('.progress-fill');
        if (progressFill) {
            progressFill.style.backgroundColor = '#FF6B6B';
        }
    }
}

// Cancel upload
function cancelUpload(fileName) {
    const item = uploadState.uploadQueue.find(item => item.file.name === fileName);
    if (item && item.file._xhr) {
        item.file._xhr.abort();
    }
    
    uploadState.uploadQueue = uploadState.uploadQueue.filter(item => item.file.name !== fileName);
    removePreview(fileName);
}

// Remove preview element
function removePreview(fileName) {
    const safeId = fileName.replace(/[^a-zA-Z0-9]/g, '_');
    const previewItem = document.getElementById(`upload-${safeId}`);
    if (previewItem) {
        previewItem.style.opacity = '0';
        previewItem.style.transition = 'opacity 0.3s ease';
        setTimeout(() => previewItem.remove(), 300);
    }
    
    // Hide preview area if empty
    const previewArea = document.getElementById('upload-previews');
    if (previewArea && uploadState.uploadQueue.length === 0) {
        setTimeout(() => {
            if (previewArea.children.length === 0) {
                previewArea.style.display = 'none';
            }
        }, 400);
    }
}

// ============================================
// PROFILE PICTURE UPLOAD
// ============================================

function uploadProfilePicture(file) {
    return new Promise((resolve, reject) => {
        const formData = new FormData();
        formData.append('profile_pic', file);
        
        fetch('/upload/profile_pic', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                resolve(data);
            } else {
                reject(new Error(data.error || 'Upload failed'));
            }
        })
        .catch(error => reject(error));
    });
}

// ============================================
// DRAG AND DROP ZONE
// ============================================

// Create drop zone overlay
function createDropZone() {
    const dropZone = document.createElement('div');
    dropZone.className = 'drop-zone-overlay';
    dropZone.id = 'drop-zone-overlay';
    dropZone.innerHTML = `
        <div class="drop-zone-content">
            <i class="fas fa-cloud-upload-alt"></i>
            <h3>Drop files to upload</h3>
            <p>Images, videos, audio, and documents</p>
        </div>
    `;
    document.body.appendChild(dropZone);
    
    return dropZone;
}

// Initialize drop zone
const dropZone = createDropZone();

document.addEventListener('dragover', function(event) {
    event.preventDefault();
    event.stopPropagation();
    dropZone.style.display = 'flex';
});

document.addEventListener('dragleave', function(event) {
    event.preventDefault();
    event.stopPropagation();
    if (event.target === document.body) {
        dropZone.style.display = 'none';
    }
});

document.addEventListener('drop', function(event) {
    event.preventDefault();
    event.stopPropagation();
    dropZone.style.display = 'none';
    
    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
        for (const file of files) {
            if (validateFile(file)) {
                addFileToUploadQueue(file);
            }
        }
        
        if (!uploadState.isUploading) {
            processUploadQueue();
        }
    }
});

// ============================================
// CLIPBOARD PASTE HANDLER
// ============================================

document.addEventListener('paste', function(event) {
    const items = event.clipboardData?.items;
    if (!items) return;
    
    for (const item of items) {
        if (item.type.startsWith('image/')) {
            event.preventDefault();
            
            const file = item.getAsFile();
            if (file && validateFile(file)) {
                addFileToUploadQueue(file);
                
                if (!uploadState.isUploading) {
                    processUploadQueue();
                }
            }
            break;
        }
    }
});

// ============================================
// FILE COMPRESSION FOR IMAGES
// ============================================

function compressImage(file, maxWidth = 1920, maxHeight = 1080, quality = 0.85) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        
        reader.onload = function(e) {
            const img = new Image();
            
            img.onload = function() {
                const canvas = document.createElement('canvas');
                let width = img.width;
                let height = img.height;
                
                // Calculate new dimensions
                if (width > maxWidth) {
                    height = (maxWidth / width) * height;
                    width = maxWidth;
                }
                if (height > maxHeight) {
                    width = (maxHeight / height) * width;
                    height = maxHeight;
                }
                
                canvas.width = width;
                canvas.height = height;
                
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);
                
                canvas.toBlob(
                    (blob) => {
                        const compressedFile = new File([blob], file.name, {
                            type: 'image/jpeg',
                            lastModified: Date.now()
                        });
                        resolve(compressedFile);
                    },
                    'image/jpeg',
                    quality
                );
            };
            
            img.onerror = function() {
                reject(new Error('Failed to load image for compression'));
            };
            
            img.src = e.target.result;
        };
        
        reader.onerror = function() {
            reject(new Error('Failed to read file'));
        };
        
        reader.readAsDataURL(file);
    });
}

// ============================================
// VIDEO THUMBNAIL GENERATION
// ============================================

function generateVideoThumbnail(file, seekTime = 1) {
    return new Promise((resolve, reject) => {
        const video = document.createElement('video');
        video.preload = 'metadata';
        video.muted = true;
        video.playsInline = true;
        
        video.onloadeddata = function() {
            video.currentTime = seekTime;
        };
        
        video.onseeked = function() {
            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            
            const ctx = canvas.getContext('2d');
            ctx.drawImage(video, 0, 0);
            
            canvas.toBlob((blob) => {
                const thumbnailFile = new File([blob], 'thumbnail.jpg', {
                    type: 'image/jpeg',
                    lastModified: Date.now()
                });
                URL.revokeObjectURL(video.src);
                resolve(thumbnailFile);
            }, 'image/jpeg', 0.8);
        };
        
        video.onerror = function() {
            URL.revokeObjectURL(video.src);
            reject(new Error('Failed to generate video thumbnail'));
        };
        
        video.src = URL.createObjectURL(file);
    });
}

// Export for use in chat.js
window.uploadFiles = uploadFiles;
window.validateFile = validateFile;
window.getFileCategory = getFileCategory;
window.formatFileSize = formatFileSize;
