import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Backtest from '../views/Backtest.vue'
import Ma120Backtest from '../views/Ma120Backtest.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: Home },
    { path: '/backtest', name: 'backtest', component: Backtest },
    { path: '/ma120', name: 'ma120', component: Ma120Backtest },
  ],
})

export default router
