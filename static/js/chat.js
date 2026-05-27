/* ============================================ */
/* BANTU HALII - CHAT FUNCTIONALITY */
/* static/js/chat.js */
/* ============================================ */

// Chat State
const chatState = {
    currentRoomId: null,
    currentRoomName: '',
    currentRoomPic: '',
    currentRoomType: '',
    currentPage: 1,
    hasMoreMessages: true,
    isLoadingMessages: false,
    replyingTo: null,
    contextMessageId: null,
    searchResults: [],
    currentSearchIndex: -1,
    isRecording: false,
    mediaRecorder: null,
    recordingTimer: null,
    recordingStartTime: null,
    selectedUsers: new Set(),
    selectedGroupMembers: new Set(),
    pendingFiles: [],
    typingTimeout: null,
    lastMessageDate: null,
    unreadCount: 0
};

// Initialize chat on page load
document.addEventListener('DOMContentLoaded', function() {
    initChat();
});

// Initialize chat
function initChat() {
    // Get current room from page data
    if (typeof currentRoomId !== 'undefined' && currentRoomId) {
        openChat(currentRoomId, currentRoomName || '', currentRoomPic || '', currentRoomType || 'direct');
    }
    
    // Setup Socket.IO event listeners
    if (typeof socket !== 'undefined' && socket) {
        socket.on('new_message', handleNewMessage);
        socket.on('message_edited', handleMessageEdited);
        socket.on('message_deleted', handleMessageDeleted);
        socket.on('user_typing', handleUserTyping);
        socket.on('user_stopped_typing', handleUserStoppedTyping);
        socket.on('message_reaction', handleMessageReaction);
        socket.on('message_pinned', handleMessagePinned);
        socket.on('user_joined_room', handleUserJoinedRoom);
        socket.on('user_left_room', handleUserLeftRoom);
        socket.on('messages_read', handleMessagesRead);
        socket.on('message_delivered', handleMessageDelivered);
        socket.on('room_updated', handleRoomUpdated);
        socket.on('member_promoted', handleMemberPromoted);
        socket.on('admin_demoted', handleAdminDemoted);
        socket.on('member_muted', handleMemberMuted);
        socket.on('member_removed', handleMemberRemoved);
        socket.on('error', handleSocketError);
    }
    
    // Setup scroll listener for infinite scroll
    const messagesContainer = document.getElementById('messages-container');
    if (messagesContainer) {
        messagesContainer.addEventListener('scroll', handleMessagesScroll);
    }
    
    // Load initial data
    loadChats();
    updateUnreadCounts();
    
    // Setup file paste handler
    document.addEventListener('paste', handleFilePaste);
    
    // Setup drag and drop
    const chatMain = document.getElementById('chat-main');
    if (chatMain) {
        chatMain.addEventListener('dragover', handleDragOver);
        chatMain.addEventListener('drop', handleDrop);
    }
}

// ============================================
// CHAT NAVIGATION
// ============================================

// Open a chat room
function openChat(roomId, roomName, roomPic, roomType) {
    if (chatState.currentRoomId === roomId) return;
    
    // Leave previous room
    if (chatState.currentRoomId && socket) {
        socket.emit('leave_room', { room_id: chatState.currentRoomId });
    }
    
    // Update state
    chatState.currentRoomId = roomId;
    chatState.currentRoomName = roomName;
    chatState.currentRoomPic = roomPic;
    chatState.currentRoomType = roomType;
    chatState.currentPage = 1;
    chatState.hasMoreMessages = true;
    chatState.replyingTo = null;
    chatState.lastMessageDate = null;
    
    // Update UI
    updateChatHeader(roomName, roomPic, roomType);
    loadMessages();
    cancelReply();
    hideRoomInfo();
    
    // Join socket room
    if (socket) {
        socket.emit('join_room', { room_id: roomId });
    }
    
    // Update active chat in sidebar
    document.querySelectorAll('.chat-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.roomId == roomId) {
            item.classList.add('active');
            item.classList.remove('unread');
            const badge = item.querySelector('.unread-badge');
            if (badge) badge.remove();
        }
    });
    
    // Show chat main on mobile
    if (window.innerWidth < 768) {
        document.getElementById('chat-sidebar').style.display = 'none';
        document.getElementById('chat-main').style.display = 'flex';
    }
    
    // Focus message input
    setTimeout(() => {
        const input = document.getElementById('message-input');
        if (input) input.focus();
    }, 300);
    
    // Load room info in background
    loadRoomInfo(roomId);
}

// Update chat header
function updateChatHeader(name, pic, type) {
    const headerAvatar = document.querySelector('.chat-header-avatar');
    const headerName = document.querySelector('.chat-header-info h3');
    const headerStatus = document.querySelector('.chat-header-status');
    
    if (headerAvatar) {
        headerAvatar.src = pic || '/static/images/default-group.png';
        headerAvatar.onerror = function() {
            this.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(name[0] || 'C')}&background=4ECDC4&color=fff&size=40`;
        };
    }
    if (headerName) headerName.textContent = name;
    if (headerStatus) headerStatus.textContent = type === 'group' ? 'Loading...' : '';
}

// Toggle sidebar on mobile
function toggleSidebar() {
    const sidebar = document.getElementById('chat-sidebar');
    const main = document.getElementById('chat-main');
    
    if (window.innerWidth < 768) {
        if (sidebar.style.display === 'none') {
            sidebar.style.display = 'flex';
            main.style.display = 'none';
        } else {
            sidebar.style.display = 'none';
            main.style.display = 'flex';
        }
    }
}

// ============================================
// MESSAGE LOADING
// ============================================

// Load messages for current room
function loadMessages(page = 1, append = false) {
    if (!chatState.currentRoomId || chatState.isLoadingMessages) return;
    
    chatState.isLoadingMessages = true;
    const loadingEl = document.getElementById('messages-loading');
    const messagesList = document.getElementById('messages-list');
    
    if (!append) {
        messagesList.innerHTML = '';
        if (loadingEl) loadingEl.style.display = 'flex';
    }
    
    fetch(`/room/${chatState.currentRoomId}/messages?page=${page}&per_page=50`)
        .then(response => response.json())
        .then(data => {
            if (loadingEl) loadingEl.style.display = 'none';
            
            if (data.messages && data.messages.length > 0) {
                // Add date separators
                const messagesWithDates = addDateSeparators(data.messages);
                const messagesHtml = messagesWithDates.reverse().map(msg => renderMessage(msg)).join('');
                
                if (append) {
                    messagesList.insertAdjacentHTML('afterbegin', messagesHtml);
                } else {
                    messagesList.innerHTML = messagesHtml;
                    scrollToBottom(false);
                }
                
                chatState.hasMoreMessages = data.has_next;
                chatState.currentPage = page;
                
                // Mark messages as read
                const messageIds = data.messages
                    .filter(msg => msg.sender_id !== currentUserId && !msg.is_read)
                    .map(msg => msg.id);
                
                if (messageIds.length > 0 && socket) {
                    socket.emit('mark_read', {
                        message_ids: messageIds,
                        room_id: chatState.currentRoomId
                    });
                }
            } else if (!append) {
                messagesList.innerHTML = `
                    <div class="messages-empty">
                        <i class="fas fa-comments"></i>
                        <p>No messages yet. Say hello! 👋</p>
                    </div>
                `;
            }
            
            chatState.isLoadingMessages = false;
        })
        .catch(error => {
            console.error('Error loading messages:', error);
            if (loadingEl) loadingEl.style.display = 'none';
            chatState.isLoadingMessages = false;
        });
}

// Add date separators to messages
function addDateSeparators(messages) {
    let lastDate = null;
    
    return messages.map(msg => {
        const msgDate = new Date(msg.created_at).toLocaleDateString();
        
        if (msgDate !== lastDate) {
            msg.showDate = true;
            lastDate = msgDate;
        }
        
        return msg;
    });
}

// Handle messages scroll for infinite loading
function handleMessagesScroll() {
    const container = document.getElementById('messages-container');
    const scrollBtn = document.getElementById('scroll-bottom-btn');
    
    if (!container) return;
    
    // Load more messages when scrolling to top
    if (container.scrollTop <= 50 && chatState.hasMoreMessages && !chatState.isLoadingMessages) {
        const previousHeight = container.scrollHeight;
        loadMessages(chatState.currentPage + 1, true);
        
        // Maintain scroll position after loading
        setTimeout(() => {
            container.scrollTop = container.scrollHeight - previousHeight;
        }, 100);
    }
    
    // Show/hide scroll to bottom button
    if (scrollBtn) {
        const threshold = container.scrollHeight - container.clientHeight - 100;
        if (container.scrollTop < threshold) {
            scrollBtn.style.display = 'flex';
            // Show unread count
            const badge = document.getElementById('unread-count-badge');
            if (badge && chatState.unreadCount > 0) {
                badge.style.display = 'flex';
                badge.textContent = chatState.unreadCount > 99 ? '99+' : chatState.unreadCount;
            }
        } else {
            scrollBtn.style.display = 'none';
            chatState.unreadCount = 0;
            const badge = document.getElementById('unread-count-badge');
            if (badge) badge.style.display = 'none';
        }
    }
}

// ============================================
// MESSAGE RENDERING
// ============================================

// Render a single message
function renderMessage(msg) {
    const isMine = msg.sender_id === currentUserId;
    const messageDate = new Date(msg.created_at);
    const timeStr = messageDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    let html = '';
    
    // Date separator
    if (msg.showDate) {
        const dateStr = messageDate.toLocaleDateString([], { 
            weekday: 'long', 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric' 
        });
        html += `<div class="message-date-separator"><span>${dateStr}</span></div>`;
    }
    
    html += `<div class="message ${isMine ? 'message-mine' : 'message-other'}" 
                   id="msg-${msg.id}" 
                   data-message-id="${msg.id}">`;
    
    html += `<div class="message-wrapper" oncontextmenu="showContextMenu(event, ${msg.id})">`;
    
    // Sender avatar for others
    if (!isMine && chatState.currentRoomType === 'group') {
        html += `<img src="${escapeHtml(msg.sender_pic || '')}" 
                      alt="${escapeHtml(msg.sender_username)}" 
                      class="message-avatar"
                      onerror="this.src='https://ui-avatars.com/api/?name=${encodeURIComponent(msg.sender_username[0] || 'U')}&background=4ECDC4&color=fff&size=32'">`;
    }
    
    html += `<div class="message-content">`;
    
    // Sender name for groups
    if (!isMine && chatState.currentRoomType === 'group') {
        html += `<span class="message-sender">${escapeHtml(msg.sender_username)}</span>`;
    }
    
    // Reply preview
    if (msg.reply_to_id) {
        html += `<div class="message-reply" onclick="scrollToMessage(${msg.reply_to_id})">
                    <i class="fas fa-reply"></i>
                    <span>Replied to a message</span>
                </div>`;
    }
    
    // Message body based on type
    html += renderMessageBody(msg);
    
    // Message metadata
    html += `<div class="message-meta">
                <span class="message-time">${timeStr}</span>
                ${msg.is_edited ? '<span class="message-edited">edited</span>' : ''}
                ${isMine ? renderMessageStatus(msg) : ''}
            </div>`;
    
    // Reactions
    if (msg.reactions && msg.reactions.length > 0) {
        html += renderReactions(msg);
    }
    
    html += `</div></div></div>`;
    
    return html;
}

// Render message body based on type
function renderMessageBody(msg) {
    let html = '';
    
    switch (msg.message_type) {
        case 'text':
            html += `<div class="message-text">${formatMessageText(escapeHtml(msg.content || ''))}</div>`;
            break;
            
        case 'image':
            html += `<div class="message-media">
                        <img src="${msg.media_url}" 
                             alt="Image" 
                             class="message-image" 
                             loading="lazy"
                             onclick="previewMedia('${msg.media_url}', 'image')">
                    </div>`;
            if (msg.content) {
                html += `<div class="message-text">${formatMessageText(escapeHtml(msg.content))}</div>`;
            }
            break;
            
        case 'video':
            html += `<div class="message-media">
                        <video controls class="message-video" poster="${msg.thumbnail_url || ''}" preload="metadata">
                            <source src="${msg.media_url}" type="video/mp4">
                            Your browser does not support video playback.
                        </video>
                    </div>`;
            if (msg.content) {
                html += `<div class="message-text">${formatMessageText(escapeHtml(msg.content))}</div>`;
            }
            break;
            
        case 'audio':
            html += `<div class="message-media">
                        <audio controls class="message-audio" preload="metadata">
                            <source src="${msg.media_url}" type="audio/mpeg">
                            Your browser does not support audio playback.
                        </audio>
                        ${msg.media_duration ? `<span class="audio-duration">${formatDuration(msg.media_duration)}</span>` : ''}
                    </div>`;
            break;
            
        case 'document':
            html += `<div class="message-media">
                        <a href="${msg.media_url}" target="_blank" class="message-document" download>
                            <i class="fas fa-file"></i>
                            <span>Document</span>
                            ${msg.media_size ? `<span class="doc-size">${formatFileSize(msg.media_size)}</span>` : ''}
                        </a>
                    </div>`;
            if (msg.content) {
                html += `<div class="message-text">${formatMessageText(escapeHtml(msg.content))}</div>`;
            }
            break;
            
        case 'location':
            html += `<div class="message-media">
                        <div class="message-location">
                            <i class="fas fa-map-marker-alt"></i>
                            <span>Shared a location</span>
                        </div>
                    </div>`;
            break;
            
        case 'contact':
            html += `<div class="message-media">
                        <div class="message-contact">
                            <i class="fas fa-user"></i>
                            <span>Shared a contact</span>
                        </div>
                    </div>`;
            break;
            
        case 'sticker':
            html += `<div class="message-media">
                        <img src="${msg.media_url}" alt="Sticker" class="message-sticker">
                    </div>`;
            break;
            
        case 'system':
            html += `<div class="message-text system-message">${escapeHtml(msg.content || '')}</div>`;
            break;
            
        default:
            html += `<div class="message-text">${formatMessageText(escapeHtml(msg.content || ''))}</div>`;
    }
    
    return html;
}

// Render message status icons
function renderMessageStatus(msg) {
    if (msg.is_read) {
        return '<span class="message-status"><i class="fas fa-check-double read"></i></span>';
    } else if (msg.is_delivered) {
        return '<span class="message-status"><i class="fas fa-check"></i></span>';
    } else {
        return '<span class="message-status"><i class="fas fa-clock"></i></span>';
    }
}

// Render reactions
function renderReactions(msg) {
    let html = '<div class="message-reactions">';
    
    // Group reactions by emoji
    const grouped = {};
    msg.reactions.forEach(r => {
        if (!grouped[r.emoji]) grouped[r.emoji] = [];
        grouped[r.emoji].push(r);
    });
    
    Object.entries(grouped).forEach(([emoji, reactions]) => {
        const isMyReaction = reactions.some(r => r.user_id === currentUserId);
        html += `<span class="reaction ${isMyReaction ? 'my-reaction' : ''}" 
                       onclick="toggleReaction(${msg.id}, '${emoji}')"
                       title="${reactions.map(r => r.user_id === currentUserId ? 'You' : 'User').join(', ')}">
                    ${emoji} ${reactions.length > 1 ? reactions.length : ''}
                </span>`;
    });
    
    html += `<button class="add-reaction" onclick="event.stopPropagation(); showReactionPicker(${msg.id})">+</button>`;
    html += '</div>';
    
    return html;
}

// Format message text (links, mentions, etc.)
function formatMessageText(text) {
    // Convert URLs to clickable links
    text = text.replace(
        /(https?:\/\/[^\s]+)/g, 
        '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
    );
    
    // Convert mentions (@username)
    text = text.replace(
        /@(\w+)/g,
        '<span class="mention">@$1</span>'
    );
    
    // Convert bold (*text*)
    text = text.replace(/\*(.+?)\*/g, '<strong>$1</strong>');
    
    // Convert italic (_text_)
    text = text.replace(/_(.+?)_/g, '<em>$1</em>');
    
    // Convert strikethrough (~text~)
    text = text.replace(/~(.+?)~/g, '<del>$1</del>');
    
    // Convert code (`text`)
    text = text.replace(/`(.+?)`/g, '<code>$1</code>');
    
    return text;
}

// ============================================
// SENDING MESSAGES
// ============================================

// Send a message
function sendMessage() {
    const input = document.getElementById('message-input');
    if (!input) return;
    
    const content = input.innerText.trim();
    
    if (!content && chatState.pendingFiles.length === 0) return;
    if (!chatState.currentRoomId) return;
    
    // Handle pending files first
    if (chatState.pendingFiles.length > 0) {
        uploadAndSendFiles(content);
        return;
    }
    
    // Send text message
    const messageData = {
        room_id: chatState.currentRoomId,
        content: content,
        message_type: 'text'
    };
    
    // Add reply info
    if (chatState.replyingTo) {
        messageData.reply_to_id = chatState.replyingTo;
    }
    
    // Send via socket
    if (socket) {
        socket.emit('send_message', messageData);
    }
    
    // Clear input
    input.innerHTML = '';
    cancelReply();
    
    // Stop typing indicator
    if (socket) {
        socket.emit('stop_typing', { room_id: chatState.currentRoomId });
    }
}

// Handle message input keydown
function handleMessageKeydown(event) {
    // Send on Enter (without Shift)
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
    
    // Start typing indicator
    if (socket && chatState.currentRoomId) {
        socket.emit('typing', { room_id: chatState.currentRoomId });
        
        clearTimeout(chatState.typingTimeout);
        chatState.typingTimeout = setTimeout(() => {
            if (socket) {
                socket.emit('stop_typing', { room_id: chatState.currentRoomId });
            }
        }, 3000);
    }
}

// Handle message input for typing indicator
function handleMessageInput() {
    if (socket && chatState.currentRoomId) {
        socket.emit('typing', { room_id: chatState.currentRoomId });
        
        clearTimeout(chatState.typingTimeout);
        chatState.typingTimeout = setTimeout(() => {
            if (socket) {
                socket.emit('stop_typing', { room_id: chatState.currentRoomId });
            }
        }, 2000);
    }
}

// ============================================
// SOCKET EVENT HANDLERS
// ============================================

// Handle incoming new message
function handleNewMessage(data) {
    if (data.room_id === chatState.currentRoomId) {
        const messagesList = document.getElementById('messages-list');
        const isScrolledToBottom = isNearBottom();
        
        // Remove empty state if exists
        const emptyState = messagesList.querySelector('.messages-empty');
        if (emptyState) emptyState.remove();
        
        messagesList.insertAdjacentHTML('beforeend', renderMessage(data));
        
        if (isScrolledToBottom || data.sender_id === currentUserId) {
            scrollToBottom(true);
        } else {
            chatState.unreadCount++;
            updateScrollButton();
        }
        
        // Mark as read if visible
        if (isScrolledToBottom && socket) {
            socket.emit('mark_read', {
                message_ids: [data.id],
                room_id: chatState.currentRoomId
            });
        }
    }
    
    // Update chat list item
    updateChatListItem(data.room_id, data);
    
    // Play sound for incoming messages
    if (data.sender_id !== currentUserId) {
        playMessageSound();
    }
}

// Handle message edited
function handleMessageEdited(data) {
    const messageEl = document.getElementById(`msg-${data.message_id}`);
    if (messageEl) {
        const textEl = messageEl.querySelector('.message-text');
        if (textEl) {
            textEl.innerHTML = formatMessageText(escapeHtml(data.content));
        }
        
        // Add edited indicator
        const metaEl = messageEl.querySelector('.message-meta');
        if (metaEl && !metaEl.querySelector('.message-edited')) {
            metaEl.insertAdjacentHTML('beforeend', '<span class="message-edited">edited</span>');
        }
    }
}

// Handle message deleted
function handleMessageDeleted(data) {
    const messageEl = document.getElementById(`msg-${data.message_id}`);
    if (messageEl) {
        messageEl.querySelector('.message-content').innerHTML = `
            <div class="message-text system-message">
                <i class="fas fa-trash"></i> This message was deleted
            </div>
        `;
    }
}

// Handle user typing
function handleUserTyping(data) {
    if (data.room_id === chatState.currentRoomId && data.user_id !== currentUserId) {
        const indicator = document.getElementById('typing-indicator');
        const text = indicator.querySelector('.typing-text');
        
        if (indicator && text) {
            indicator.style.display = 'flex';
            text.textContent = `${data.username} is typing...`;
            
            // Auto-hide after 3 seconds
            clearTimeout(indicator._timeout);
            indicator._timeout = setTimeout(() => {
                indicator.style.display = 'none';
            }, 3000);
        }
    }
}

// Handle user stopped typing
function handleUserStoppedTyping(data) {
    if (data.room_id === chatState.currentRoomId) {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) {
            indicator.style.display = 'none';
        }
    }
}

// Handle message reaction
function handleMessageReaction(data) {
    const messageEl = document.getElementById(`msg-${data.message_id}`);
    if (messageEl) {
        // Refresh reactions by reloading message
        fetch(`/message/${data.message_id}`)
            .then(response => response.json())
            .then(msg => {
                const contentEl = messageEl.querySelector('.message-content');
                const existingReactions = contentEl.querySelector('.message-reactions');
                if (existingReactions) existingReactions.remove();
                
                if (msg.reactions && msg.reactions.length > 0) {
                    contentEl.insertAdjacentHTML('beforeend', renderReactions(msg));
                }
            });
    }
}

// Handle message pinned
function handleMessagePinned(data) {
    if (data.room_id === chatState.currentRoomId) {
        showToast(`Message ${data.action} by ${data.pinned_by}`, 'info');
    }
}

// Handle user joined room
function handleUserJoinedRoom(data) {
    if (data.room_id === chatState.currentRoomId) {
        const messagesList = document.getElementById('messages-list');
        messagesList.insertAdjacentHTML('beforeend', `
            <div class="message-date-separator">
                <span>${data.username} joined the room</span>
            </div>
        `);
        scrollToBottom(true);
    }
}

// Handle user left room
function handleUserLeftRoom(data) {
    if (data.room_id === chatState.currentRoomId) {
        const messagesList = document.getElementById('messages-list');
        messagesList.insertAdjacentHTML('beforeend', `
            <div class="message-date-separator">
                <span>${data.username} left the room</span>
            </div>
        `);
        scrollToBottom(true);
    }
}

// Handle messages read
function handleMessagesRead(data) {
    if (data.room_id === chatState.currentRoomId) {
        data.message_ids.forEach(msgId => {
            const messageEl = document.getElementById(`msg-${msgId}`);
            if (messageEl) {
                const statusEl = messageEl.querySelector('.message-status');
                if (statusEl) {
                    statusEl.innerHTML = '<i class="fas fa-check-double read"></i>';
                }
            }
        });
    }
}

// Handle message delivered
function handleMessageDelivered(data) {
    const messageEl = document.getElementById(`msg-${data.message_id}`);
    if (messageEl) {
        const statusEl = messageEl.querySelector('.message-status');
        if (statusEl) {
            statusEl.innerHTML = '<i class="fas fa-check"></i>';
        }
    }
}

// Handle room updated
function handleRoomUpdated(data) {
    if (data.id === chatState.currentRoomId) {
        updateChatHeader(data.name, data.room_pic, data.room_type);
    }
}

// Handle socket error
function handleSocketError(data) {
    console.error('Socket error:', data.message);
    showToast(data.message || 'An error occurred', 'error');
}

// ============================================
// UTILITY FUNCTIONS
// ============================================

// Scroll to bottom of messages
function scrollToBottom(smooth = true) {
    const container = document.getElementById('messages-container');
    if (container) {
        if (smooth) {
            container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
        } else {
            container.scrollTop = container.scrollHeight;
        }
    }
}

// Check if user is near the bottom of messages
function isNearBottom() {
    const container = document.getElementById('messages-container');
    if (!container) return true;
    
    const threshold = 100;
    return container.scrollHeight - container.scrollTop - container.clientHeight < threshold;
}

// Update scroll to bottom button
function updateScrollButton() {
    const scrollBtn = document.getElementById('scroll-bottom-btn');
    const badge = document.getElementById('unread-count-badge');
    
    if (scrollBtn) {
        scrollBtn.style.display = 'flex';
        if (badge && chatState.unreadCount > 0) {
            badge.style.display = 'flex';
            badge.textContent = chatState.unreadCount > 99 ? '99+' : chatState.unreadCount;
        }
    }
}

// Scroll to a specific message
function scrollToMessage(messageId) {
    const messageEl = document.getElementById(`msg-${messageId}`);
    if (messageEl) {
        messageEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        messageEl.style.animation = 'highlight 2s ease';
        setTimeout(() => {
            messageEl.style.animation = '';
        }, 2000);
    }
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Format duration for audio/video
function formatDuration(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// Play message sound
function playMessageSound() {
    try {
        const audio = new Audio('/static/sounds/message.mp3');
        audio.volume = 0.3;
        audio.play().catch(() => {}); // Ignore autoplay restrictions
    } catch (e) {
        // Ignore audio errors
    }
}

// Show toast notification
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <div class="toast-content">
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ============================================
// MODAL FUNCTIONS
// ============================================

function showNewChatModal() {
    document.getElementById('new-chat-modal').style.display = 'flex';
}

function showNewGroupModal() {
    document.getElementById('new-group-modal').style.display = 'flex';
}

function showContactsModal() {
    document.getElementById('contacts-modal').style.display = 'flex';
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

// Close modals on outside click
window.addEventListener('click', function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = 'none';
    }
});

// ============================================
// MESSAGE ACTIONS
// ============================================

// Show context menu
function showContextMenu(event, messageId) {
    event.preventDefault();
    chatState.contextMessageId = messageId;
    
    const menu = document.getElementById('context-menu');
    menu.style.display = 'block';
    menu.style.left = event.pageX + 'px';
    menu.style.top = event.pageY + 'px';
    
    // Hide menu on click outside
    setTimeout(() => {
        document.addEventListener('click', hideContextMenu, { once: true });
    }, 0);
}

function hideContextMenu() {
    document.getElementById('context-menu').style.display = 'none';
    chatState.contextMessageId = null;
}

// Reply to message
function replyToMessage() {
    if (!chatState.contextMessageId) return;
    
    chatState.replyingTo = chatState.contextMessageId;
    
    // Show reply preview
    const messageEl = document.getElementById(`msg-${chatState.contextMessageId}`);
    if (messageEl) {
        const username = messageEl.querySelector('.message-sender')?.textContent || 'Message';
        const content = messageEl.querySelector('.message-text')?.textContent || '';
        
        document.getElementById('reply-username').textContent = username;
        document.getElementById('reply-message').textContent = content.substring(0, 100);
        document.getElementById('reply-preview').style.display = 'flex';
    }
    
    hideContextMenu();
    document.getElementById('message-input')?.focus();
}

// Cancel reply
function cancelReply() {
    chatState.replyingTo = null;
    document.getElementById('reply-preview').style.display = 'none';
}

// Copy message
function copyMessage() {
    if (!chatState.contextMessageId) return;
    
    const messageEl = document.getElementById(`msg-${chatState.contextMessageId}`);
    if (messageEl) {
        const content = messageEl.querySelector('.message-text')?.textContent || '';
        navigator.clipboard.writeText(content).then(() => {
            showToast('Message copied to clipboard', 'success');
        });
    }
    
    hideContextMenu();
}

// Delete message
function deleteMessage() {
    if (!chatState.contextMessageId) return;
    
    if (confirm('Are you sure you want to delete this message?')) {
        fetch(`/message/${chatState.contextMessageId}/delete`, { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const messageEl = document.getElementById(`msg-${chatState.contextMessageId}`);
                    if (messageEl) {
                        messageEl.querySelector('.message-content').innerHTML = `
                            <div class="message-text system-message">
                                <i class="fas fa-trash"></i> This message was deleted
                            </div>
                        `;
                    }
                    showToast('Message deleted', 'info');
                } else {
                    showToast(data.error || 'Failed to delete message', 'error');
                }
            });
    }
    
    hideContextMenu();
}

// Pin message
function pinMessage() {
    if (!chatState.contextMessageId) return;
    
    fetch(`/message/${chatState.contextMessageId}/pin`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showToast(`Message ${data.action}`, 'success');
            } else {
                showToast(data.error || 'Failed to pin message', 'error');
            }
        });
    
    hideContextMenu();
}

// Star message
function starMessage() {
    if (!chatState.contextMessageId) return;
    showToast('Message starred', 'success');
    hideContextMenu();
}

// Forward message
function forwardMessage() {
    if (!chatState.contextMessageId) return;
    showToast('Select a chat to forward to', 'info');
    hideContextMenu();
}

// Toggle reaction
function toggleReaction(messageId, emoji) {
    fetch(`/message/${messageId}/react`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ emoji: emoji })
    })
    .then(response => response.json())
    .then(data => {
        if (!data.success) {
            showToast(data.error || 'Failed to update reaction', 'error');
        }
    });
}

// Show reaction picker
function showReactionPicker(messageId) {
    const commonEmojis = ['👍', '❤️', '😂', '😮', '😢', '🙏', '👏', '🔥', '🎉', '💯'];
    
    const picker = document.createElement('div');
    picker.className = 'reaction-picker';
    picker.innerHTML = commonEmojis.map(emoji => 
        `<span class="reaction-option" onclick="toggleReaction(${messageId}, '${emoji}'); this.parentElement.remove();">${emoji}</span>`
    ).join('');
    
    // Position near the message
    const messageEl = document.getElementById(`msg-${messageId}`);
    if (messageEl) {
        const rect = messageEl.getBoundingClientRect();
        picker.style.position = 'fixed';
        picker.style.top = (rect.top - 50) + 'px';
        picker.style.left = rect.left + 'px';
        picker.style.zIndex = '3000';
    }
    
    document.body.appendChild(picker);
    
    // Remove on click outside
    setTimeout(() => {
        document.addEventListener('click', function removePicker() {
            if (picker.parentElement) picker.remove();
            document.removeEventListener('click', removePicker);
        });
    }, 0);
}

// ============================================
// FILE HANDLING
// ============================================

function handleFilePaste(event) {
    const items = event.clipboardData?.items;
    if (!items) return;
    
    for (const item of items) {
        if (item.type.startsWith('image/')) {
            event.preventDefault();
            const file = item.getAsFile();
            addPendingFile(file);
        }
    }
}

function handleDragOver(event) {
    event.preventDefault();
    event.stopPropagation();
}

function handleDrop(event) {
    event.preventDefault();
    event.stopPropagation();
    
    const files = event.dataTransfer?.files;
    if (files) {
        for (const file of files) {
            addPendingFile(file);
        }
    }
}

function addPendingFile(file) {
    chatState.pendingFiles.push(file);
    showFilePreview(file);
}

function showFilePreview(file) {
    const input = document.getElementById('message-input');
    if (!input) return;
    
    const reader = new FileReader();
    reader.onload = function(e) {
        const preview = document.createElement('div');
        preview.className = 'file-preview';
        
        if (file.type.startsWith('image/')) {
            preview.innerHTML = `<img src="${e.target.result}" alt="Preview" class="preview-image">`;
        } else {
            preview.innerHTML = `
                <div class="preview-file">
                    <i class="fas fa-file"></i>
                    <span>${file.name}</span>
                </div>
            `;
        }
        
        preview.innerHTML += `<button class="remove-preview" onclick="removePendingFile('${file.name}', this.parentElement)">×</button>`;
        input.parentElement.insertBefore(preview, input);
    };
    reader.readAsDataURL(file);
}

function removePendingFile(fileName, element) {
    chatState.pendingFiles = chatState.pendingFiles.filter(f => f.name !== fileName);
    element.remove();
}

function uploadAndSendFiles(content) {
    // This will be implemented in upload.js
    if (typeof uploadFiles === 'function') {
        uploadFiles(chatState.pendingFiles, content, chatState.currentRoomId, chatState.replyingTo);
        chatState.pendingFiles = [];
        document.querySelectorAll('.file-preview').forEach(el => el.remove());
        document.getElementById('message-input').innerHTML = '';
        cancelReply();
    }
}

// ============================================
// CHAT LIST MANAGEMENT
// ============================================

function loadChats() {
    fetch('/api/rooms')
        .then(response => response.json())
        .then(rooms => {
            updateChatList(rooms);
        })
        .catch(error => console.error('Error loading chats:', error));
}

function updateChatList(rooms) {
    const chatList = document.getElementById('chat-list');
    if (!chatList) return;
    
    if (rooms.length === 0) {
        chatList.innerHTML = `
            <div class="chat-empty">
                <i class="fas fa-comments"></i>
                <h3>No Conversations Yet</h3>
                <p>Start a new chat or join a group to begin connecting!</p>
            </div>
        `;
        return;
    }
    
    chatList.innerHTML = rooms.map(room => createChatListItem(room)).join('');
}

function createChatListItem(room) {
    const lastMessage = room.last_message;
    const timeStr = lastMessage ? formatTime(lastMessage.created_at) : '';
    const preview = lastMessage 
        ? (lastMessage.sender_id === currentUserId ? 'You: ' : '') + (lastMessage.content?.substring(0, 50) || '[Media]')
        : 'No messages yet';
    
    return `
        <div class="chat-item ${room.id === chatState.currentRoomId ? 'active' : ''} ${room.unread_count > 0 ? 'unread' : ''}"
             data-room-id="${room.id}"
             data-room-type="${room.room_type}"
             data-room-name="${escapeHtml(room.name)}"
             data-unread="${room.unread_count}"
             onclick="openChat(${room.id}, '${escapeHtml(room.name)}', '${room.room_pic || ''}', '${room.room_type}')">
            <div class="chat-item-avatar">
                <img src="${room.room_pic || '/static/images/default-group.png'}" 
                     alt="${escapeHtml(room.name)}"
                     onerror="this.src='https://ui-avatars.com/api/?name=${encodeURIComponent(room.name[0] || 'C')}&background=4ECDC4&color=fff&size=50'">
                ${room.room_type === 'group' ? '<span class="group-badge"><i class="fas fa-users"></i></span>' : ''}
            </div>
            <div class="chat-item-content">
                <div class="chat-item-header">
                    <h4 class="chat-item-name">${escapeHtml(room.name)}</h4>
                    <span class="chat-item-time">${timeStr}</span>
                </div>
                <div class="chat-item-preview">
                    <span class="last-message">${escapeHtml(preview)}</span>
                    ${room.unread_count > 0 ? `<span class="unread-badge">${room.unread_count > 99 ? '99+' : room.unread_count}</span>` : ''}
                </div>
            </div>
        </div>
    `;
}

function updateChatListItem(roomId, messageData) {
    const item = document.querySelector(`.chat-item[data-room-id="${roomId}"]`);
    if (item) {
        const preview = item.querySelector('.last-message');
        const time = item.querySelector('.chat-item-time');
        
        if (preview) {
            const prefix = messageData.sender_id === currentUserId ? 'You: ' : '';
            preview.textContent = prefix + (messageData.content?.substring(0, 50) || '[Media]');
        }
        if (time) {
            time.textContent = formatTime(messageData.created_at);
        }
        
        // Move to top
        item.parentElement.prepend(item);
    }
}

function filterChats() {
    const query = document.getElementById('chat-search')?.value.toLowerCase() || '';
    document.querySelectorAll('.chat-item').forEach(item => {
        const name = item.dataset.roomName?.toLowerCase() || '';
        item.style.display = name.includes(query) ? '' : 'none';
    });
}

function switchChatTab(tab) {
    document.querySelectorAll('.chat-tab').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');
    
    document.querySelectorAll('.chat-item').forEach(item => {
        const unread = parseInt(item.dataset.unread || '0');
        const type = item.dataset.roomType;
        
        switch (tab) {
            case 'all':
                item.style.display = '';
                break;
            case 'unread':
                item.style.display = unread > 0 ? '' : 'none';
                break;
            case 'groups':
                item.style.display = type === 'group' ? '' : 'none';
                break;
        }
    });
}

function updateUnreadCounts() {
    fetch('/notifications/unread_count')
        .then(response => response.json())
        .then(data => {
            const badge = document.getElementById('notification-badge');
            if (badge) {
                if (data.count > 0) {
                    badge.style.display = 'flex';
                    badge.textContent = data.count > 99 ? '99+' : data.count;
                } else {
                    badge.style.display = 'none';
                }
            }
        });
}

function formatTime(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return Math.floor(diff / 60000) + 'm';
    if (diff < 86400000) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    if (diff < 604800000) return Math.floor(diff / 86400000) + 'd';
    return date.toLocaleDateString();
}

// ============================================
// ROOM INFO
// ============================================

function showRoomInfo(roomId) {
    const sidebar = document.getElementById('info-sidebar');
    sidebar.style.display = 'block';
    loadRoomInfo(roomId);
}

function hideRoomInfo() {
    document.getElementById('info-sidebar').style.display = 'none';
}

function loadRoomInfo(roomId) {
    fetch(`/api/room/${roomId}/info`)
        .then(response => response.json())
        .then(data => {
            const content = document.getElementById('info-content');
            if (content) {
                content.innerHTML = renderRoomInfo(data);
            }
        });
}

function renderRoomInfo(room) {
    return `
        <div class="room-info-header">
            <img src="${room.room_pic || '/static/images/default-group.png'}" 
                 alt="${escapeHtml(room.name)}" 
                 class="room-info-avatar"
                 onerror="this.src='https://ui-avatars.com/api/?name=${encodeURIComponent(room.name[0] || 'R')}&background=4ECDC4&color=fff&size=100'">
            <h3>${escapeHtml(room.name)}</h3>
            <p>${room.description || 'No description'}</p>
        </div>
        <div class="room-info-section">
            <h4>Members (${room.member_count})</h4>
            <div class="room-members-list">
                ${room.members?.map(member => `
                    <div class="room-member-item">
                        <img src="${member.profile_pic || ''}" 
                             alt="${escapeHtml(member.username)}"
                             onerror="this.src='https://ui-avatars.com/api/?name=${encodeURIComponent(member.username[0] || 'U')}&background=4ECDC4&color=fff&size=40'">
                        <div class="member-info">
                            <span>${escapeHtml(member.username)}</span>
                            <span class="member-role">${member.role}</span>
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
        <div class="room-info-section">
            <h4>Shared Media</h4>
            <p class="text-muted">Media shared in this room will appear here</p>
        </div>
        <div class="room-info-actions">
            ${room.my_permissions?.is_admin ? `
                <button class="btn btn-outline btn-block" onclick="showRoomSettings(${room.id})">
                    <i class="fas fa-cog"></i> Room Settings
                </button>
            ` : ''}
            <button class="btn btn-outline btn-block" onclick="leaveRoom(${room.id})">
                <i class="fas fa-sign-out-alt"></i> Leave Room
            </button>
        </div>
    `;
}

// ============================================
// VOICE/VIDEO CALLS
// ============================================

function startCall(callType, roomId, userId) {
    if (!socket) return;
    
    if (userId) {
        socket.emit('voice_call_start', {
            receiver_id: userId,
            call_type: callType,
            room_id: roomId
        });
    }
    
    showToast(`Starting ${callType} call...`, 'info');
}

// ============================================
// SEARCH
// ============================================

function toggleSearchMessages() {
    const searchBar = document.getElementById('message-search');
    if (searchBar.style.display === 'none') {
        searchBar.style.display = 'flex';
        document.getElementById('message-search-input')?.focus();
    } else {
        searchBar.style.display = 'none';
        clearSearchHighlights();
    }
}

function searchMessages() {
    const query = document.getElementById('message-search-input')?.value.toLowerCase();
    if (!query) {
        clearSearchHighlights();
        return;
    }
    
    const messages = document.querySelectorAll('.message-text');
    chatState.searchResults = [];
    chatState.currentSearchIndex = -1;
    
    messages.forEach((el, index) => {
        const text = el.textContent.toLowerCase();
        if (text.includes(query)) {
            chatState.searchResults.push(el);
        }
    });
    
    document.getElementById('search-count').textContent = 
        `${chatState.searchResults.length} result${chatState.searchResults.length !== 1 ? 's' : ''}`;
    
    if (chatState.searchResults.length > 0) {
        navigateSearch('down');
    }
}

function navigateSearch(direction) {
    if (chatState.searchResults.length === 0) return;
    
    clearSearchHighlights();
    
    if (direction === 'down') {
        chatState.currentSearchIndex = (chatState.currentSearchIndex + 1) % chatState.searchResults.length;
    } else {
        chatState.currentSearchIndex = chatState.currentSearchIndex <= 0 
            ? chatState.searchResults.length - 1 
            : chatState.currentSearchIndex - 1;
    }
    
    const element = chatState.searchResults[chatState.currentSearchIndex];
    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    element.style.backgroundColor = 'rgba(255, 234, 167, 0.5)';
}

function clearSearchHighlights() {
    chatState.searchResults.forEach(el => {
        el.style.backgroundColor = '';
    });
    chatState.searchResults = [];
    chatState.currentSearchIndex = -1;
    document.getElementById('search-count').textContent = '';
}

// ============================================
// VOICE RECORDING
// ============================================

function startRecording() {
    if (!navigator.mediaDevices) {
        showToast('Voice recording is not supported in your browser', 'error');
        return;
    }
    
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            chatState.isRecording = true;
            chatState.mediaRecorder = new MediaRecorder(stream);
            const chunks = [];
            
            chatState.mediaRecorder.ondataavailable = function(e) {
                chunks.push(e.data);
            };
            
            chatState.mediaRecorder.onstop = function() {
                const blob = new Blob(chunks, { type: 'audio/webm' });
                const file = new File([blob], 'voice-message.webm', { type: 'audio/webm' });
                addPendingFile(file);
                
                // Stop all tracks
                stream.getTracks().forEach(track => track.stop());
            };
            
            chatState.mediaRecorder.start();
            chatState.recordingStartTime = Date.now();
            
            // Show recording indicator
            document.getElementById('recording-indicator').style.display = 'block';
            
            // Update recording timer
            chatState.recordingTimer = setInterval(updateRecordingTimer, 1000);
        })
        .catch(error => {
            console.error('Recording error:', error);
            showToast('Failed to start recording', 'error');
        });
}

function stopRecording() {
    if (!chatState.isRecording || !chatState.mediaRecorder) return;
    
    chatState.isRecording = false;
    chatState.mediaRecorder.stop();
    
    clearInterval(chatState.recordingTimer);
    document.getElementById('recording-indicator').style.display = 'none';
}

function cancelRecording() {
    if (!chatState.isRecording || !chatState.mediaRecorder) return;
    
    chatState.isRecording = false;
    chatState.mediaRecorder.stop();
    
    clearInterval(chatState.recordingTimer);
    document.getElementById('recording-indicator').style.display = 'none';
}

function sendRecording() {
    stopRecording();
    // File will be sent via addPendingFile
    setTimeout(sendMessage, 500);
}

function updateRecordingTimer() {
    const elapsed = Math.floor((Date.now() - chatState.recordingStartTime) / 1000);
    const mins = Math.floor(elapsed / 60);
    const secs = elapsed % 60;
    document.getElementById('recording-time').textContent = 
        `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

// ============================================
// MEDIA PREVIEW
// ============================================

function previewMedia(url, type) {
    const modal = document.getElementById('media-preview-modal');
    const preview = document.getElementById('media-preview');
    
    if (type === 'image') {
        preview.innerHTML = `<img src="${url}" alt="Preview" style="max-width: 100%; max-height: 70vh;">`;
    } else if (type === 'video') {
        preview.innerHTML = `
            <video controls style="max-width: 100%; max-height: 70vh;">
                <source src="${url}" type="video/mp4">
            </video>
        `;
    }
    
    modal.style.display = 'flex';
}

function downloadMedia() {
    const preview = document.getElementById('media-preview');
    const img = preview.querySelector('img');
    const video = preview.querySelector('video source');
    
    const url = img?.src || video?.src;
    if (url) {
        window.open(url, '_blank');
    }
}

// ============================================
// KEYBOARD SHORTCUTS
// ============================================

document.addEventListener('keydown', function(event) {
    // Escape to close modals
    if (event.key === 'Escape') {
        hideContextMenu();
        cancelReply();
        hideRoomInfo();
        document.querySelectorAll('.modal').forEach(m => m.style.display = 'none');
        document.getElementById('message-search').style.display = 'none';
        clearSearchHighlights();
    }
    
    // Ctrl+F for search in chat
    if ((event.ctrlKey || event.metaKey) && event.key === 'f') {
        if (chatState.currentRoomId) {
            event.preventDefault();
            toggleSearchMessages();
        }
    }
    
    // Ctrl+N for new chat
    if ((event.ctrlKey || event.metaKey) && event.key === 'n') {
        event.preventDefault();
        showNewChatModal();
    }
});
