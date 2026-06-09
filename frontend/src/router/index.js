import { createRouter, createWebHistory } from 'vue-router'

import MainLayout from '../layout/MainLayout.vue'
import DashboardView from '../views/DashboardView.vue'
import IterationsView from '../views/IterationsView.vue'
import LoginView from '../views/LoginView.vue'
import ProgramsView from '../views/ProgramsView.vue'
import ProjectsView from '../views/ProjectsView.vue'
import RequirementsView from '../views/RequirementsView.vue'
import TasksView from '../views/TasksView.vue'

const routes = [
  { path: '/login', name: 'login', component: LoginView },
  {
    path: '/',
    component: MainLayout,
    children: [
      { path: '', name: 'dashboard', component: DashboardView },
      { path: 'programs', name: 'programs', component: ProgramsView },
      { path: 'projects', name: 'projects', component: ProjectsView },
      { path: 'iterations', name: 'iterations', component: IterationsView },
      { path: 'requirements', name: 'requirements', component: RequirementsView },
      { path: 'tasks', name: 'tasks', component: TasksView }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
