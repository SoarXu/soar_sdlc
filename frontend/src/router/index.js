import { createRouter, createWebHistory } from 'vue-router'

import MainLayout from '../layout/MainLayout.vue'
import DashboardView from '../views/DashboardView.vue'
import LoginView from '../views/LoginView.vue'
import ProgramsView from '../views/ProgramsView.vue'
import ProjectsView from '../views/ProjectsView.vue'

const routes = [
  { path: '/login', name: 'login', component: LoginView },
  {
    path: '/',
    component: MainLayout,
    children: [
      { path: '', name: 'dashboard', component: DashboardView },
      { path: 'programs', name: 'programs', component: ProgramsView },
      { path: 'projects', name: 'projects', component: ProjectsView }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
