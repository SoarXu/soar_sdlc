import { createRouter, createWebHistory } from 'vue-router'

import MainLayout from '../layout/MainLayout.vue'
import AdminView from '../views/AdminView.vue'
import BugDetailView from '../views/BugDetailView.vue'
import BugsView from '../views/BugsView.vue'
import ChangePasswordView from '../views/ChangePasswordView.vue'
import DashboardView from '../views/DashboardView.vue'
import ExceptionRulesView from '../views/ExceptionRulesView.vue'
import DevopsView from '../views/DevopsView.vue'
import IterationsView from '../views/IterationsView.vue'
import IterationDetailView from '../views/IterationDetailView.vue'
import LoginView from '../views/LoginView.vue'
import ProgramsView from '../views/ProgramsView.vue'
import ProjectDetailView from '../views/ProjectDetailView.vue'
import ProjectsView from '../views/ProjectsView.vue'
import RequirementDetailView from '../views/RequirementDetailView.vue'
import RequirementsView from '../views/RequirementsView.vue'
import RolesView from '../views/RolesView.vue'
import TaskDetailView from '../views/TaskDetailView.vue'
import TasksView from '../views/TasksView.vue'
import TestCaseDetailView from '../views/TestCaseDetailView.vue'
import TestsView from '../views/TestsView.vue'
import WorkflowView from '../views/WorkflowView.vue'

const routes = [
  { path: '/login', name: 'login', component: LoginView },
  { path: '/change-password', name: 'change-password', component: ChangePasswordView },
  {
    path: '/',
    component: MainLayout,
    children: [
      { path: '', name: 'dashboard', component: DashboardView },
      { path: 'admin', name: 'admin', component: AdminView },
      { path: 'programs', name: 'programs', component: ProgramsView },
      { path: 'projects', name: 'projects', component: ProjectsView },
      { path: 'projects/:id', name: 'project-detail', component: ProjectDetailView },
      { path: 'requirements/:id', name: 'requirement-detail', component: RequirementDetailView },
      { path: 'tasks/:id', name: 'task-detail', component: TaskDetailView },
      { path: 'test-cases/:id', name: 'test-case-detail', component: TestCaseDetailView },
      { path: 'bugs/:id', name: 'bug-detail', component: BugDetailView },
      { path: 'iterations', name: 'iterations', component: IterationsView },
      { path: 'iterations/:id', name: 'iteration-detail', component: IterationDetailView },
      { path: 'requirements', name: 'requirements', component: RequirementsView },
      { path: 'tasks', name: 'tasks', component: TasksView },
      { path: 'tests', name: 'tests', component: TestsView },
      { path: 'bugs', name: 'bugs', component: BugsView },
      { path: 'devops', name: 'devops', component: DevopsView },
      { path: 'roles', name: 'roles', component: RolesView },
      { path: 'workflow', name: 'workflow', component: WorkflowView },
      { path: 'exception-rules', name: 'exception-rules', component: ExceptionRulesView }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const token = localStorage.getItem('access_token')
  if (to.name === 'login') {
    return token ? { name: 'dashboard' } : true
  }
  if (to.name === 'change-password') {
    return token ? true : { name: 'login', query: { redirect: to.fullPath } }
  }
  if (!token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (localStorage.getItem('must_change_password') === 'true') {
    return { name: 'change-password', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
