import { http } from './http'

export function fetchGitPlatforms() {
  return http.get('/devops/git-platforms')
}

export function createGitPlatform(data) {
  return http.post('/devops/git-platforms', data)
}

export function updateGitPlatform(id, data) {
  return http.put(`/devops/git-platforms/${id}`, data)
}

export function deleteGitPlatform(id) {
  return http.delete(`/devops/git-platforms/${id}`)
}

export function testGitPlatformConnection(id) {
  return http.post(`/devops/git-platforms/${id}/test`)
}

export function fetchDevopsRepositories() {
  return http.get('/devops/repositories')
}

export function createDevopsRepository(data) {
  return http.post('/devops/repositories', data)
}

export function updateDevopsRepository(id, data) {
  return http.put(`/devops/repositories/${id}`, data)
}

export function deleteDevopsRepository(id) {
  return http.delete(`/devops/repositories/${id}`)
}

export function fetchJenkinsJobs() {
  return http.get('/devops/jenkins-jobs')
}

export function fetchJenkinsBuilds(params = {}) {
  return http.get('/devops/jenkins-builds', { params })
}

export function createJenkinsBuild(data) {
  return http.post('/devops/jenkins-builds', data)
}

export function createJenkinsJob(data) {
  return http.post('/devops/jenkins-jobs', data)
}

export function updateJenkinsJob(id, data) {
  return http.put(`/devops/jenkins-jobs/${id}`, data)
}

export function deleteJenkinsJob(id) {
  return http.delete(`/devops/jenkins-jobs/${id}`)
}

export function fetchDevopsCommits(params = {}) {
  return http.get('/devops/commits', { params })
}

export function fetchDevopsCommit(id) {
  return http.get(`/devops/commits/${id}`)
}

export function ingestDevopsCommit(data) {
  return http.post('/devops/commits', data)
}

export function markDevopsCommitReviewed(id, data) {
  return http.post(`/devops/commits/${id}/reviewed`, data)
}

export function fetchCodeReviewTasks(params = {}) {
  return http.get('/devops/review-tasks', { params })
}

export function fetchWorkItemReviews() {
  return http.get('/devops/work-item-reviews')
}

export function decideWorkItemReview(id, data) {
  return http.post(`/devops/work-item-reviews/${id}/decision`, data)
}
