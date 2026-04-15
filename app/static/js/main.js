// Initialize Lucide icons on page load
document.addEventListener("DOMContentLoaded", () => {
    lucide.createIcons();
    setupMobileSidebar();
    
    // Auto-remove standard flashed messages after 3s
    const toasts = document.querySelectorAll('.toast');
    toasts.forEach(toast => {
        setTimeout(() => {
            // CSS animation handles fading out, we just remove from DOM after
            setTimeout(() => toast.remove(), 500); 
        }, 3000);
    });
});

// Toast notification helper
window.showToast = function(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const content = document.createElement('div');
    content.className = 'toast-content';
    content.textContent = message;
    
    toast.appendChild(content);
    container.appendChild(toast);
    
    setTimeout(() => {
        setTimeout(() => toast.remove(), 500);
    }, 3000);
};

// Mobile sidebar toggle
function setupMobileSidebar() {
    const toggleBtn = document.getElementById('mobile-menu-toggle');
    const closeBtn = document.getElementById('sidebar-close');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    
    if (!toggleBtn || !closeBtn || !sidebar || !overlay) return;
    
    function openSidebar() {
        sidebar.classList.add('open');
        overlay.classList.add('open');
    }
    
    function closeSidebar() {
        sidebar.classList.remove('open');
        overlay.classList.remove('open');
    }
    
    toggleBtn.addEventListener('click', openSidebar);
    closeBtn.addEventListener('click', closeSidebar);
    overlay.addEventListener('click', closeSidebar);
}

// CSRF wrapper logic 
window.getCsrfToken = function() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
};

// Confirm dialog helper for destructive actions
window.confirmAction = function(message) {
    return confirm(message || "Are you sure you want to proceed?");
};

/* ==========================================================================
   MENTOR DASHBOARD JS LOGIC
   ========================================================================== */
document.addEventListener("DOMContentLoaded", function() {
    // 1. Expandable Table Rows
    const projectRows = document.querySelectorAll('.project-row');
    projectRows.forEach(row => {
        row.addEventListener('click', function(e) {
            if (e.target.closest('button') || e.target.closest('a')) return;
            
            const targetId = this.dataset.target;
            const previewRow = document.getElementById(targetId);
            if (!previewRow) return;

            const isExpanded = this.classList.contains('expanded');
            
            // Close all
            document.querySelectorAll('.project-row.expanded').forEach(r => r.classList.remove('expanded'));
            document.querySelectorAll('.expanded-preview').forEach(p => p.style.display = 'none');
            // Reset arrows if there are any
            document.querySelectorAll('.expand-icon').forEach(i => i.style.transform = 'rotate(0deg)');
            
            if (!isExpanded) {
                this.classList.add('expanded');
                previewRow.style.display = 'table-row';
                const icon = this.querySelector('.expand-icon');
                if (icon) icon.style.transform = 'rotate(180deg)';
            }
        });
    });

    // 2. Filter Buttons
    const filterBtns = document.querySelectorAll('.filter-btn');
    filterBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            filterBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            const filterValue = this.dataset.filter;
            const allPairs = document.querySelectorAll('.project-row-group');
            
            allPairs.forEach(pair => {
                const mainRow = pair.querySelector('.project-row');
                const rowHealth = mainRow.dataset.health;
                
                if (filterValue === 'all' || filterValue === rowHealth) {
                    pair.style.display = '';
                } else {
                    pair.style.display = 'none';
                    // Hide expanded row if filtering out
                    const preview = pair.querySelector('.expanded-preview');
                    if (preview && preview.style.display === 'table-row') {
                        mainRow.classList.remove('expanded');
                        preview.style.display = 'none';
                    }
                }
            });
        });
    });

    // 3. Create Student Group Submit
    const createStudentGroupBtn = document.getElementById('create-student-group-submit');
    if (createStudentGroupBtn) {
        createStudentGroupBtn.addEventListener('click', function() {
            const name = document.getElementById('sg-name').value;
            const desc = document.getElementById('sg-desc').value;
            const emailsText = document.getElementById('sg-emails').value;
            const emails = emailsText.split('\n').map(e => e.trim()).filter(e => e);
            
            if (!name) {
                alert('Project Name is required.');
                return;
            }
            
            createStudentGroupBtn.disabled = true;
            createStudentGroupBtn.innerHTML = '<i data-lucide="loader-2" class="animate-spin"></i> Creating...';
            if (window.lucide) window.lucide.createIcons();
            
            fetch('/mentor/groups/create-student-group', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.getCsrfToken()
                },
                body: JSON.stringify({
                    project_name: name,
                    description: desc,
                    student_emails: emails
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    const resDiv = document.getElementById('create-group-result');
                    resDiv.style.display = 'block';
                    resDiv.innerHTML = `
                        <div class="toast toast-success" style="position:static; margin-bottom: 10px; width: 100%;">
                            <div class="toast-content" style="color:var(--color-navy)">
                                <strong>Group created!</strong> ${data.students_added} students added.<br>
                                Invite code: <strong>${data.invite_code}</strong>
                            </div>
                        </div>
                    `;
                    if (data.students_not_found && data.students_not_found.length > 0) {
                        resDiv.innerHTML += `
                            <div class="toast toast-warning" style="position:static; width: 100%;">
                                <div class="toast-content" style="color:var(--color-navy); font-size:12px;">
                                    <strong>Note:</strong> The following emails were not found (they need to register first):<br>
                                    ${data.students_not_found.join('<br>')}
                                </div>
                            </div>
                        `;
                    }
                    setTimeout(() => window.location.reload(), 2500);
                } else {
                    alert(data.error || 'Failed to create group');
                    createStudentGroupBtn.disabled = false;
                    createStudentGroupBtn.textContent = 'Create Group';
                }
            })
            .catch(err => {
                console.error(err);
                alert('An error occurred');
                createStudentGroupBtn.disabled = false;
                createStudentGroupBtn.textContent = 'Create Group';
            });
        });
    }

    // 4. Auto Refresh Endpoints (Every 5 minutes)
    const isMentorDashboard = window.location.pathname.includes('/mentor/dashboard');
    if (isMentorDashboard) {
        setInterval(() => {
            fetch('/mentor/dashboard/stats')
            .then(res => res.json())
            .then(data => {
                if (data.success && data.stats) {
                    data.stats.forEach(stat => {
                        const row = document.querySelector(`.project-row[data-group-id="${stat.group_id}"]`);
                        if(row) {
                            // Update score
                            const scoreEl = row.querySelector('.health-score');
                            if(scoreEl) {
                                scoreEl.textContent = stat.health_score;
                                scoreEl.style.color = stat.health_color;
                            }
                            
                            // Update status text
                            const statusEl = row.querySelector('.health-status');
                            if(statusEl) {
                                statusEl.textContent = stat.health_status;
                                statusEl.style.color = stat.health_color;
                            }
                            
                            // Update tasks
                            const tasksEl = row.querySelector('.tasks-count');
                            if(tasksEl) {
                                tasksEl.textContent = `${stat.completed_tasks} / ${stat.total_tasks}`;
                            }
                            const overdueEl = row.querySelector('.tasks-overdue');
                            if(overdueEl) {
                                if(stat.overdue_count > 0) {
                                    overdueEl.textContent = `${stat.overdue_count} overdue`;
                                    overdueEl.style.display = 'block';
                                } else {
                                    overdueEl.style.display = 'none';
                                }
                            }
                            
                            // Update last active
                            const activeEl = row.querySelector('.last-active');
                            if(activeEl) {
                                activeEl.textContent = stat.last_activity_relative;
                            }
                        }
                    });
                }
            })
            .catch(err => console.log('Auto-refresh stats failed', err));
        }, 5 * 60 * 1000); // 5 minutes
    }
});
