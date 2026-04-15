document.addEventListener('DOMContentLoaded', function() {
    if (typeof io === 'undefined') return;

    const socket = io();

    socket.on('connect', () => {
        console.log('Socket.IO connected');
        if (window.GROUP_ID) {
            socket.emit('join_group', { group_id: window.GROUP_ID });
        }
        const indicator = document.getElementById('live-indicator');
        if (indicator) indicator.style.display = 'flex';
    });
    
    socket.on('disconnect', () => {
        const indicator = document.getElementById('live-indicator');
        if (indicator) indicator.style.display = 'none';
    });

    socket.on('task_update', (data) => {
        const action = data.action;
        
        if (action === 'created' || action === 'updated') {
            // For complex UI rendering without a reactive frontend framework, 
            // swapping the inner HTML selectively via AJAX is smooth and prevents full page reload
            fetch(window.location.href)
            .then(res => res.text())
            .then(html => {
                const doc = new DOMParser().parseFromString(html, "text/html");
                const newViews = doc.getElementById('views-container');
                const oldViews = document.getElementById('views-container');
                
                if (newViews && oldViews) {
                    oldViews.innerHTML = newViews.innerHTML;
                    
                    // Re-init SortableJS after DOM injection
                    if (window.Sortable && window.CURRENT_ROLE && ['admin', 'editor'].includes(window.CURRENT_ROLE)) {
                        ['todo', 'in_progress', 'done'].forEach(status => {
                            const list = document.getElementById(`col-${status}`);
                            if(list) {
                                new Sortable(list, {
                                    group: 'tasks',
                                    animation: 150,
                                    ghostClass: 'sortable-ghost',
                                    onEnd: function(evt) {
                                        const itemEl = evt.item;
                                        const newStatus = evt.to.getAttribute('data-status');
                                        const oldStatus = evt.from.getAttribute('data-status');
                                        const taskId = itemEl.getAttribute('data-id');
                                        
                                        if (newStatus !== oldStatus) {
                                            document.getElementById(`count-${newStatus}`).innerText = parseInt(document.getElementById(`count-${newStatus}`).innerText) + 1;
                                            document.getElementById(`count-${oldStatus}`).innerText = parseInt(document.getElementById(`count-${oldStatus}`).innerText) - 1;
                                            
                                            fetch(`/groups/${window.GROUP_ID}/tasks/${taskId}`, {
                                                method: 'PATCH',
                                                headers: {
                                                    'Content-Type': 'application/json',
                                                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
                                                },
                                                body: JSON.stringify({ status: newStatus })
                                            });
                                        }
                                    }
                                });
                            }
                        });
                    }
                }
                
                ['todo', 'in_progress', 'done'].forEach(status => {
                    const countEl = document.getElementById(`count-${status}`);
                    const newCountEl = doc.getElementById(`count-${status}`);
                    if (countEl && newCountEl) {
                        countEl.innerText = newCountEl.innerText;
                    }
                });
            });
            
        } else if (action === 'deleted') {
            const listRow = document.getElementById(`list-task-${data.task_id}`);
            if (listRow) {
                listRow.style.transition = 'opacity 0.3s ease';
                listRow.style.opacity = '0';
                setTimeout(() => listRow.remove(), 300);
            }
            
            const kanbanCard = document.getElementById(`kanban-task-${data.task_id}`);
            if (kanbanCard) {
                kanbanCard.style.transition = 'opacity 0.3s ease';
                kanbanCard.style.opacity = '0';
                setTimeout(() => kanbanCard.remove(), 300);
            }
        }
    });

    socket.on('time_update', (data) => {
        // Show subtle toast if logged by someone else
        if (window.CURRENT_USER_ID && data.log_owner_id !== window.CURRENT_USER_ID) {
            window.showToast(`${data.log_owner_name} logged time on a task`, "info");
        }
        
        // Find list row text and update
        const listTimeEl = document.getElementById(`list-task-time-${data.task_id}`);
        if (listTimeEl) {
            const loggedText = listTimeEl.querySelector('.logged-text');
            if (loggedText) loggedText.textContent = `${data.total_time_formatted} logged`;
            
            // Variance color logic
            if (data.time_variance_minutes && data.time_variance_minutes < 0) {
                listTimeEl.style.color = 'var(--color-danger)';
            } else {
                listTimeEl.style.color = 'var(--color-text-secondary)';
            }
        }
        
        // Find kanban card and update
        const kanbanTimeEl = document.getElementById(`kanban-time-${data.task_id}`);
        if (kanbanTimeEl) {
            const loggedText = kanbanTimeEl.querySelector('.logged-text');
            if (loggedText) loggedText.textContent = `${data.total_time_formatted} logged`;
            
            if (data.time_variance_minutes && data.time_variance_minutes < 0) {
                kanbanTimeEl.style.color = 'var(--color-danger)';
            } else {
                kanbanTimeEl.style.color = 'var(--color-text-secondary)';
            }
            
            // Update progress bar
            if (data.estimated_minutes) {
                const pct = (data.total_time_logged / data.estimated_minutes) * 100;
                let displayPct = pct > 100 ? 100 : pct;
                const fillEl = kanbanTimeEl.querySelector('.progress-fill');
                if (fillEl) {
                    fillEl.style.width = `${displayPct}%`;
                    fillEl.style.background = pct > 100 ? 'var(--color-danger)' : 'var(--color-success)';
                }
            }
        }
    });

    socket.on('presence_update', (data) => {
        const onlineIds = data.online_user_ids || [];
        
        // Update presence dots
        document.querySelectorAll('.presence-dot-status').forEach(el => {
            const userId = parseInt(el.getAttribute('data-user-id'));
            if (onlineIds.includes(userId)) {
                el.classList.remove('offline');
            } else {
                el.classList.add('offline');
            }
        });
        
        // Update general member count badge if present
        const badge = document.getElementById('online-count-badge');
        if (badge) {
            badge.style.display = 'inline-flex';
            badge.textContent = `${onlineIds.length} online`;
        }
    });

    socket.on('activity_update', (data) => {
        const act = data.activity;
        const conf = data.config;
        
        // Setup Toast
        if (window.CURRENT_USER_ID != act.user_id) {
            window.showToast(`${act.username} ${conf.label}`, "info");
        }
        
        // 1. Dashboard Feed Update
        const dashFeed = document.getElementById('dashboard-feed-container');
        if (dashFeed) {
            const emptyEl = document.getElementById('dashboard-empty-feed');
            if (emptyEl) emptyEl.remove();
            
            const entryHTML = `
                <div class="dashboard-activity-entry" style="padding: 12px 16px; border-bottom: 1px solid var(--color-border); display: flex; gap: 12px; animation: slideInTop 0.3s ease-out;">
                    <div class="activity-${conf.color}" style="width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 2px;">
                        <i data-lucide="${conf.icon}" style="width: 12px;"></i>
                    </div>
                    <div>
                        <p style="font-size: 0.85rem; margin-bottom: 4px; line-height: 1.4;">
                            <span style="font-weight: 600;">${act.username}</span> ${conf.label}
                        </p>
                        <p class="timestamp" data-time="${act.created_at}" style="font-size: 0.7rem; color: var(--color-text-muted);">just now</p>
                    </div>
                </div>
            `;
            
            dashFeed.insertAdjacentHTML('afterbegin', entryHTML);
            lucide.createIcons();
            
            if (dashFeed.children.length > 10) {
                dashFeed.removeChild(dashFeed.lastElementChild);
            }
        }
        
        // 2. Main Timeline Activity Update
        const timeline = document.getElementById('feed-container');
        if (timeline) {
            const emptyEl = timeline.querySelector('.empty-state');
            if (emptyEl) emptyEl.remove();
            
            const html = `
                <div class="timeline-entry" data-id="${act.id}" style="position: relative; z-index: 1; display: flex; gap: 16px; margin-bottom: 24px; animation: slideInTop 0.3s ease-out;">
                    <div class="activity-${conf.color}" style="width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; box-shadow: 0 0 0 4px var(--color-bg); position: relative; z-index: 2;">
                        <i data-lucide="${conf.icon}" style="width: 16px; height: 16px;"></i>
                    </div>
                    
                    <div class="card" style="flex: 1;">
                        <div class="card-body" style="padding: 16px;">
                            <div style="display: flex; justify-content: space-between; gap: 16px; align-items: start;">
                                <div>
                                    <div style="margin-bottom: 4px; font-size: 0.95rem;">
                                        <span style="font-weight: 600; color: var(--color-text-primary);">${act.username}</span>
                                        <span style="color: var(--color-text-secondary);"> ${conf.label}</span>
                                    </div>
                                    ${act.description ? `<div style="font-weight: 500; font-size: 0.95rem; color: var(--color-text-primary);">${act.description}</div>` : ''}
                                </div>
                                <div class="timestamp" data-time="${act.created_at}" style="font-size: 0.8rem; color: var(--color-text-muted); white-space: nowrap; padding-top: 2px;">
                                    just now
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            timeline.insertAdjacentHTML('afterbegin', html);
            lucide.createIcons();
        }
    });
});
