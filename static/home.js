const { createApp } = Vue;

    createApp({
      data() {
        const root = document.getElementById('app');
        return {
          roleValue: root.dataset.role || '',
          nameValue: root.dataset.name || '',
          // admin lists
          students: [],
          companies: [],
          employees: [],
          pendingJobs: [],
          approvedStudents: [],
          approvedCompanies: [],
          approvedEmployees: [], // NEW
          // student data
          studentProfile: { cgpa: '', branch: '', passing_year: '' },
          jobs: [],
          myApplications: [],
          applyForm: { education: '' },
          applyingJobId: null,
          applyingJobTitle: null,
          viewingInterview: null,
          // company data
          companyJobs: [],
          currentApplicants: [],
          currentViewingJobId: null,
          newJob: { title: '', description: '', cgpa: '', branch: '', year: '', deadline: '' },
          interviewForm: { date: '', time: '', location: '', applicationId: null },
          // notifications
          notifications: [],
          unreadCount: 0,
          showNotifications: false,

          employeePower: 'full',
          pollHandle: null
        }
      },

      mounted() {
        this.startRealtime();

        if (this.roleValue === 'employee') this.loadAdmin();
        if (this.roleValue === 'student') { this.loadJobs(); this.loadMyApplications(); }
        if (this.roleValue === 'company') this.loadCompanyJobs();

        this.fetchMe();

        this.applyModal = new bootstrap.Modal(document.getElementById('applyModal'));
        this.applicantsModal = new bootstrap.Modal(document.getElementById('applicantsModal'));
        this.interviewModal = new bootstrap.Modal(document.getElementById('interviewModal'));
        this.studentInterviewModal = new bootstrap.Modal(document.getElementById('studentInterviewModal'));
      },

      unmounted() {
        clearInterval(this.pollHandle);
      },

      computed: {
        canApprove() { return this.employeePower === 'full' || this.employeePower === 'approve'; },
        canBlock() { return this.employeePower === 'full' || this.employeePower === 'block'; },
        canDelete() { return this.employeePower === 'full'; }
      },

      methods: {
        startRealtime() {
          this.refreshAll();
          this.pollHandle = setInterval(() => this.refreshAll(), 6000);
        },

        async refreshAll() {
          try {
            if (this.roleValue === 'employee') await this.loadAdmin();
            if (this.roleValue === 'student') { await this.loadJobs(); await this.loadMyApplications(); }
            if (this.roleValue === 'company') await this.loadCompanyJobs();
            await this.loadNotifications();
          } catch (err) {}
        },

        async fetchMe() {
          try {
            const r = await fetch('/api/me');
            if (!r.ok) return;
            const d = await r.json();
            if (d && d.power) this.employeePower = d.power;
            if (d && d.name) this.nameValue = d.name;
            
            if (this.roleValue === 'student') {
              this.studentProfile.cgpa = d.cgpa || '';
              this.studentProfile.branch = d.branch || '';
              this.studentProfile.passing_year = d.passing_year || '';
            }
          } catch (err) {}
        },

        async loadNotifications() {
          try {
            const r = await fetch('/api/notifications');
            if (!r.ok) return;
            const list = await r.json();
            this.notifications = list || [];
            this.unreadCount = this.notifications.filter(x => !x.read).length;
          } catch (err) {}
        },

        toggleNotifications() {
          this.showNotifications = !this.showNotifications;
          if (this.showNotifications) this.loadNotifications();
        },

        async markNotificationRead(id) {
          try {
            const res = await fetch('/api/read_notification', {
              method: 'POST', headers: {'Content-Type':'application/json'},
              body: JSON.stringify({id: id})
            });
            if (res.ok) {
              this.notifications = this.notifications.map(n => n.id === id ? {...n, read:true} : n);
              this.unreadCount = this.notifications.filter(x => !x.read).length;
            }
          } catch (err) {}
        },

        // --- ADMIN METHODS ---
        async loadAdmin() {
          try {
            const [sRes, cRes, eRes, pjRes, asRes, acRes, aeRes] = await Promise.allSettled([
              fetch('/api/students'), fetch('/api/companies'), fetch('/api/employees'),
              fetch('/api/pending_jobs'), fetch('/api/students_approved'), fetch('/api/companies_approved'),
              fetch('/api/employees_approved')
            ]);
            this.students = sRes.status === 'fulfilled' && sRes.value.ok ? await sRes.value.json() : [];
            this.companies = cRes.status === 'fulfilled' && cRes.value.ok ? await cRes.value.json() : [];
            this.employees = eRes.status === 'fulfilled' && eRes.value.ok ? await eRes.value.json() : [];
            this.pendingJobs = pjRes.status === 'fulfilled' && pjRes.value.ok ? await pjRes.value.json() : [];
            this.approvedStudents = asRes.status === 'fulfilled' && asRes.value.ok ? await asRes.value.json() : [];
            this.approvedCompanies = acRes.status === 'fulfilled' && acRes.value.ok ? await acRes.value.json() : [];
            this.approvedEmployees = aeRes.status === 'fulfilled' && aeRes.value.ok ? await aeRes.value.json() : []; // Properly assigns the new data
          } catch (err) {}
        },

        async updateEmployeePower(id, power) {
          try {
            const res = await fetch('/api/update_employee_power', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ id: id, power: power })
            });
            if (res.ok) {
              alert('Employee power updated successfully!');
              await this.loadAdmin();
            } else {
              alert('Failed to update power.');
            }
          } catch (err) {
            alert('Network error.');
          }
        },

        async approveUser(role, id) {
          if (!confirm('Approve this user?')) return;
          try {
            const res = await fetch('/api/approve_user', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({role: role, id: id}) });
            if (res.ok) await this.loadAdmin();
          } catch (err) {}
        },

        async rejectUser(role, id) {
          if (!confirm('Reject this user?')) return;
          try {
            const res = await fetch('/api/reject_user', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({role: role, id: id}) });
            if (res.ok) await this.loadAdmin();
          } catch (err) {}
        },

        async blockUser(role, id) {
          if (!confirm('Block this user?')) return;
          try {
            const res = await fetch('/api/block_user', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({role: role, id: id}) });
            if (res.ok) await this.loadAdmin();
          } catch (err) {}
        },

        async unblockUser(role, id) {
          if (!confirm("Unblock this user?")) return;
          try {
            const res = await fetch("/api/unblock_user", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ role: role, id: id }) });
            if (res.ok) await this.loadAdmin();
          } catch (err) {}
        },

        async deleteUser(role, id) {
          if (!confirm('Delete this user permanently?')) return;
          try {
            const res = await fetch('/api/delete_user', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({role: role, id: id}) });
            if (res.ok) await this.loadAdmin();
          } catch (err) {}
        },

        async approveJob(id) {
          if (!confirm('Approve this job?')) return;
          try {
            const res = await fetch('/api/approve_job', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id:id}) });
            if (res.ok) await this.loadAdmin();
          } catch (err) {}
        },

        async rejectJob(id) {
          if (!confirm('Reject this job?')) return;
          try {
            const res = await fetch('/api/reject_job', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id:id}) });
            if (res.ok) await this.loadAdmin();
          } catch (err) {}
        },

        openSearch() {
          const q = prompt('Search student by name');
          if (!q) return;
          fetch(`/api/search_students?q=${encodeURIComponent(q)}`).then(r => r.json()).then(d => {
            if (!d || d.length===0) return alert('No results');
            alert('Found: ' + d.map(x => `${x.id} — ${x.name} <${x.email}>`).join('\n'));
          }).catch(()=> alert('Search failed'));
        },

        // --- STUDENT METHODS ---
        async updateProfile() {
          try {
            const res = await fetch('/api/update_profile', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(this.studentProfile)
            });
            const result = await res.json();
            if (res.ok) alert(result.message);
            else alert('Failed to update profile.');
          } catch (err) {
            alert('Network error.');
          }
        },

        async exportCSV() {
          try {
            const res = await fetch('/api/export_csv', { method: 'POST' });
            const data = await res.json();
            alert(data.message); // Tells the user to check their notifications
          } catch (err) {
            alert("Failed to start export.");
          }
        },

        async loadJobs() {
          try { this.jobs = await (await fetch('/api/jobs')).json(); } 
          catch (err) {}
        },
        hasApplied(jobId) {
          return this.myApplications.some(a => a.job_id === jobId && a.status !== 'withdrawn');
        },

        openApply(jobId) {
          const job = this.jobs.find(j => j.id == jobId) || {};
          this.applyingJobId = jobId;
          this.applyingJobTitle = job.title || '';
          this.applyForm.education = '';
          const f = this.$refs?.cvfile;
          if (f) f.value = null;
          this.applyModal.show();
        },

        async submitApplication() {
          try {
            const fileInput = document.querySelector('#applyModal input[type=file]') || this.$refs.cvfile;
            const file = fileInput?.files?.[0];
            if (!this.applyingJobId) return alert('Job not selected');
            if (!this.applyForm.education) return alert('Add your education');
            if (!file) return alert('Attach your CV');

            const fd = new FormData();
            fd.append('job_id', this.applyingJobId);
            fd.append('education', this.applyForm.education);
            fd.append('cv', file);

            const res = await fetch('/api/apply_job', { method: 'POST', body: fd });
            const result = await res.json();
            if (!res.ok) throw new Error(result.message || 'Apply failed');

            alert(result.message || 'Applied');
            this.applyModal.hide();
            await this.loadMyApplications();
          } catch (err) { alert(err.message || 'Failed to apply'); }
        },

        async loadMyApplications() {
          try { this.myApplications = await (await fetch('/api/my_applications')).json(); } 
          catch (err) {}
        },

        async withdrawApplication(id) {
          if (!confirm('Withdraw application?')) return;
          try {
            await fetch('/api/withdraw_application', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: id }) });
            await this.loadMyApplications();
          } catch (err) {}
        },

        viewInterview(interviewData) {
          this.viewingInterview = interviewData;
          this.studentInterviewModal.show();
        },

        // --- COMPANY METHODS ---
        async loadCompanyJobs() {
          try { this.companyJobs = await (await fetch('/api/company_jobs')).json(); } 
          catch (err) {}
        },

        async postJob() {
          if (!this.newJob.title || !this.newJob.description) return alert('Fill job title & description');
          try {
            await fetch('/api/post_job', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.newJob) });
            this.newJob = { title: '', description: '', cgpa: '', branch: '', year: '', deadline: '' };
            await this.loadCompanyJobs();
          } catch (err) { alert('Failed to post job.'); }
        },

        async deleteJob(id) {
          if (!confirm('Delete this job?')) return;
          try {
            await fetch('/api/delete_job', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: id }) });
            await this.loadCompanyJobs();
          } catch (err) {}
        },

        async openApplicants(jobId) {
          try {
            this.currentViewingJobId = jobId;
            const res = await fetch(`/api/job_applicants?job_id=${jobId}`);
            this.currentApplicants = await res.json();
            this.applicantsModal.show();
          } catch (err) {}
        },

        async approveApplicant(appId) {
          if (!confirm('Shortlist this applicant?')) return;
          try {
            await fetch('/api/approve_application', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: appId }) });
            await this.openApplicants(this.currentViewingJobId);
          } catch (err) {}
        },

        async rejectApplicant(appId) {
          if (!confirm('Reject this applicant?')) return;
          try {
            await fetch('/api/reject_application', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: appId }) });
            await this.openApplicants(this.currentViewingJobId);
          } catch (err) {}
        },

        openInterviewModal(appId) {
          this.interviewForm = { date: '', time: '', location: '', applicationId: appId };
          this.applicantsModal.hide(); 
          this.interviewModal.show();
        },

        async submitInterview() {
          if (!this.interviewForm.date || !this.interviewForm.time || !this.interviewForm.location) {
            return alert("Please fill out all interview details.");
          }
          try {
            const res = await fetch('/api/schedule_interview', {
              method: 'POST', 
              headers: { 'Content-Type': 'application/json' }, 
              body: JSON.stringify({ 
                application_id: this.interviewForm.applicationId,
                date: this.interviewForm.date,
                time: this.interviewForm.time,
                location: this.interviewForm.location
              }) 
            });
            if (res.ok) {
              this.interviewModal.hide();
              await this.openApplicants(this.currentViewingJobId);
            }
          } catch (err) {}
        },

        async selectStudent(appId) {
          if (!confirm('Officially hire and select this student?')) return;
          try {
            const res = await fetch('/api/select_student', { 
              method: 'POST', 
              headers: { 'Content-Type': 'application/json' }, 
              body: JSON.stringify({ id: appId }) 
            });
            if (res.ok) {
              await this.openApplicants(this.currentViewingJobId);
            }
          } catch (err) {}
        },

        logout() { window.location.href = '/logout'; }
      }
    }).mount('#app');