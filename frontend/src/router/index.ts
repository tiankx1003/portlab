import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Backtest from '../views/Backtest.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: Home },
    { path: '/backtest', name: 'backtest', component: Backtest },
  ],
})

export default router
